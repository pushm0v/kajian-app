"""Loads Qwen3-ASR-1.7B once at startup directly via vLLM's native model
support, and exposes both a batch transcribe(...) call (for the existing
/transcribe endpoint) and a streaming session API (for /transcribe/stream).

Calls vllm.LLM(...) directly rather than going through the `qwen_asr`
package's Qwen3ASRModel wrapper. `qwen_asr` ships its own out-of-tree
vLLM model registration (qwen_asr.core.vllm_backend.qwen3_asr) written
against pre-native vLLM (0.14.0, its own pinned version) — vLLM itself
absorbed Qwen3-ASR as a first-party model (same architecture name,
Qwen3ASRForConditionalGeneration) starting at v0.16.0, and `qwen_asr`'s
custom registration was never updated to match. That version skew between
qwen_asr's hand-rolled model code and whatever vLLM version is actually
installed is what caused a reproducible segfault deep in the audio
encoder's attention path during engine startup — enforce_eager, the
attention backend choice, and a numpy/numba pin were all ruled out first.
Calling vllm.LLM(...) directly lets vLLM use its own actively-maintained
native implementation instead.

The prompt format, streaming prefix-rollback strategy, and output parsing
below are ported from qwen_asr's wrapper (qwen_asr/inference/qwen3_asr.py,
qwen_asr/inference/utils.py — both Apache-2.0, Alibaba Qwen team) so
behavior matches what that library produced, just without depending on it
for the actual model load/generate calls.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import numpy as np

from . import config

logger = logging.getLogger("kajian_asr")

_ASR_TEXT_TAG = "<asr_text>"
_LANG_PREFIX = "language "

# Canonical language names Qwen3-ASR's prompt format expects (the model was
# trained to emit/accept these exact strings after "language "). Keyed by
# the ISO-639-1-ish code the app's locale ids normalize to.
LANGUAGE_NAMES_BY_CODE = {
    "zh": "Chinese", "yue": "Cantonese", "en": "English", "ar": "Arabic",
    "de": "German", "fr": "French", "es": "Spanish", "pt": "Portuguese",
    "id": "Indonesian", "it": "Italian", "ko": "Korean", "ru": "Russian",
    "th": "Thai", "vi": "Vietnamese", "ja": "Japanese", "tr": "Turkish",
    "hi": "Hindi", "ms": "Malay", "nl": "Dutch", "sv": "Swedish",
    "da": "Danish", "fi": "Finnish", "pl": "Polish", "cs": "Czech",
    "fil": "Filipino", "fa": "Persian", "el": "Greek", "hu": "Hungarian",
    "mk": "Macedonian", "ro": "Romanian",
}


def _detect_and_fix_repetitions(text: str, threshold: int = 20) -> str:
    def fix_char_repeats(s: str, thresh: int) -> str:
        res = []
        i, n = 0, len(s)
        while i < n:
            count = 1
            while i + count < n and s[i + count] == s[i]:
                count += 1
            if count > thresh:
                res.append(s[i])
            else:
                res.append(s[i:i + count])
            i += count
        return "".join(res)

    def fix_pattern_repeats(s: str, thresh: int, max_len: int = 20) -> str:
        n = len(s)
        min_repeat_chars = thresh * 2
        if n < min_repeat_chars:
            return s
        i = 0
        result = []
        while i <= n - min_repeat_chars:
            found = False
            for k in range(1, max_len + 1):
                if i + k * thresh > n:
                    break
                pattern = s[i:i + k]
                valid = True
                for rep in range(1, thresh):
                    start_idx = i + rep * k
                    if s[start_idx:start_idx + k] != pattern:
                        valid = False
                        break
                if valid:
                    total_rep = thresh
                    end_index = i + thresh * k
                    while end_index + k <= n and s[end_index:end_index + k] == pattern:
                        total_rep += 1
                        end_index += k
                    result.append(pattern)
                    result.append(fix_pattern_repeats(s[end_index:], thresh, max_len))
                    i = n
                    found = True
                    break
            if found:
                break
            result.append(s[i])
            i += 1
        if not found:
            result.append(s[i:])
        return "".join(result)

    fixed = fix_char_repeats(text, threshold)
    return fix_pattern_repeats(fixed, threshold)


def _parse_asr_output(raw: str, user_language: str | None = None) -> tuple[str, str]:
    """Parses Qwen3-ASR's raw decoded output into (language, text).

    Ported from qwen_asr.inference.utils.parse_asr_output. Cases:
      - With tag: "language Chinese<asr_text>...."
      - No tag: treat whole string as text.
      - "language None<asr_text>": empty/silent audio -> ("", "")
      - If user_language was forced in the prompt, raw is text-only.
    """
    if raw is None:
        return "", ""
    s = str(raw).strip()
    if not s:
        return "", ""

    s = _detect_and_fix_repetitions(s)

    if user_language:
        return user_language, s

    if _ASR_TEXT_TAG not in s:
        return "", s.strip()

    meta_part, text_part = s.split(_ASR_TEXT_TAG, 1)
    meta_lower = meta_part.lower()

    if "language none" in meta_lower:
        t = text_part.strip()
        return ("", t) if t else ("", "")

    lang = ""
    for line in meta_part.splitlines():
        line = line.strip()
        if line.lower().startswith(_LANG_PREFIX):
            val = line[len(_LANG_PREFIX):].strip()
            if val:
                lang = val[:1].upper() + val[1:].lower()
            break

    return lang, text_part.strip()


@dataclass
class StreamingState:
    """Mutable per-connection streaming decode state.

    Ported from qwen_asr.inference.qwen3_asr.ASRStreamingState.
    """

    prompt_raw: str
    force_language: str | None
    chunk_size_samples: int
    unfixed_chunk_num: int
    unfixed_token_num: int

    chunk_id: int = 0
    buffer: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))
    audio_accum: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))
    text: str = ""
    _raw_decoded: str = ""


class AsrModel:
    """Thread-safe wrapper around a single loaded Qwen3-ASR vLLM instance.

    A lock serializes calls into the model. vLLM batches internally, but a
    homelab box serving one app's traffic doesn't need concurrent generate()
    calls from multiple threads on one engine.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._tokenizer = None
        self._sampling_params = None

    def load(self) -> None:
        if self._model is not None:
            return
        self._log_gpu_diagnostics()
        logger.info(
            "Loading %s via vLLM (gpu_memory_utilization=%.2f, enforce_eager=%s, "
            "mm_encoder_attn_backend=%s) ...",
            config.MODEL_ID, config.GPU_MEMORY_UTILIZATION, config.ENFORCE_EAGER,
            config.MM_ENCODER_ATTN_BACKEND or "(vllm default)",
        )
        # Imported lazily so config-only tooling doesn't need vllm/transformers
        # installed (e.g. this module is imported by tests that mock it out).
        from transformers import AutoTokenizer  # noqa: PLC0415
        from vllm import LLM, SamplingParams  # noqa: PLC0415

        llm_kwargs = {}
        if config.MM_ENCODER_ATTN_BACKEND:
            llm_kwargs["mm_encoder_attn_backend"] = config.MM_ENCODER_ATTN_BACKEND

        self._model = LLM(
            model=config.MODEL_ID,
            gpu_memory_utilization=config.GPU_MEMORY_UTILIZATION,
            enforce_eager=config.ENFORCE_EAGER,
            **llm_kwargs,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(config.MODEL_ID)
        self._sampling_params = SamplingParams(temperature=0.0, max_tokens=4096)
        logger.info("Model loaded.")

    def _log_gpu_diagnostics(self) -> None:
        """Logs GPU visibility/memory *before* vLLM touches anything.

        vLLM/CUDA failures can crash the whole process with no Python
        traceback at all (a hard segfault/abort, not a catchable
        exception) — if that happens, these lines are the only signal
        we'll have about whether the GPU was even visible going in.
        """
        try:
            import torch  # noqa: PLC0415 - only needed for this diagnostic
            logger.info("torch.cuda.is_available() = %s", torch.cuda.is_available())
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    free, total = torch.cuda.mem_get_info(i)
                    logger.info(
                        "GPU %d: %s, total=%.1fGB, free=%.1fGB",
                        i, props.name, total / 1e9, free / 1e9,
                    )
        except Exception:  # noqa: BLE001 - diagnostics must never block loading
            logger.exception("GPU diagnostic check itself failed")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        # vLLM always targets CUDA for this model; kept as a property (not a
        # hardcoded string in main.py) so /health stays a single source of
        # truth if that ever changes.
        return "cuda"

    def normalize_language(self, locale_id: str | None) -> str | None:
        """Maps a BCP-47 locale (e.g. "id_ID") to the canonical language
        name Qwen3-ASR's prompt format expects (e.g. "Indonesian"). Returns
        None (auto-detect) if the locale is missing or unrecognized."""
        if not locale_id:
            return None
        code = locale_id.split("_")[0].split("-")[0].lower()
        return LANGUAGE_NAMES_BY_CODE.get(code)

    def _build_prompt(self, force_language: str | None) -> str:
        messages = [
            {"role": "system", "content": ""},
            {"role": "user", "content": [{"type": "audio", "audio": ""}]},
        ]
        prompt = self._tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False,
        )
        if force_language:
            prompt += f"language {force_language}{_ASR_TEXT_TAG}"
        return prompt

    def transcribe_chunk(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None,
    ) -> str:
        """Transcribes a single bounded audio clip (< ~20 minutes, per the
        model's documented limit — callers should chunk well below that).

        `sample_rate` must already be config.TARGET_SAMPLE_RATE (16kHz) —
        this method does no resampling, matching the rest of the pipeline
        which decodes straight to 16kHz (see audio.py).

        Returns the transcribed text, stripped. Empty string for silence.
        """
        if self._model is None:
            raise RuntimeError("AsrModel.load() must be called before use")

        prompt = self._build_prompt(language)
        request = {"prompt": prompt, "multi_modal_data": {"audio": [audio.astype(np.float32, copy=False)]}}

        with self._lock:
            [output] = self._model.generate([request], sampling_params=self._sampling_params, use_tqdm=False)
        raw_text = output.outputs[0].text
        _, text = _parse_asr_output(raw_text, user_language=language)
        return text

    def new_streaming_state(self, language: str | None = None) -> StreamingState:
        """Starts a new incremental-decoding session for one live connection.

        Returned state is only safe to use from a single caller at a time —
        each WebSocket connection gets its own via this method.
        """
        if self._model is None:
            raise RuntimeError("AsrModel.load() must be called before use")
        chunk_size_samples = max(1, int(round(config.STREAM_CHUNK_SIZE_SEC * config.TARGET_SAMPLE_RATE)))
        return StreamingState(
            prompt_raw=self._build_prompt(language),
            force_language=language,
            chunk_size_samples=chunk_size_samples,
            unfixed_chunk_num=config.STREAM_UNFIXED_CHUNK_NUM,
            unfixed_token_num=config.STREAM_UNFIXED_TOKEN_NUM,
        )

    def _decode_prefix(self, state: StreamingState) -> str:
        """Rolls back the last `unfixed_token_num` tokens from the
        previously accumulated decode, to reduce boundary jitter between
        chunks. Widens the rollback if it lands mid-codepoint (the decoder
        emits U+FFFD for a truncated multi-byte sequence)."""
        if state.chunk_id < state.unfixed_chunk_num:
            return ""
        ids = self._tokenizer.encode(state._raw_decoded)
        k = state.unfixed_token_num
        while True:
            end_idx = max(0, len(ids) - k)
            prefix = self._tokenizer.decode(ids[:end_idx]) if end_idx > 0 else ""
            if "�" not in prefix:
                return prefix
            if end_idx == 0:
                return ""
            k += 1

    def _streaming_step(self, state: StreamingState, audio_chunk: np.ndarray) -> None:
        if state.audio_accum.shape[0] == 0:
            state.audio_accum = audio_chunk
        else:
            state.audio_accum = np.concatenate([state.audio_accum, audio_chunk], axis=0)

        prefix = self._decode_prefix(state)
        prompt = state.prompt_raw + prefix
        request = {"prompt": prompt, "multi_modal_data": {"audio": [state.audio_accum]}}

        outputs = self._model.generate([request], sampling_params=self._sampling_params, use_tqdm=False)
        gen_text = outputs[0].outputs[0].text

        state._raw_decoded = prefix + gen_text
        _, state.text = _parse_asr_output(state._raw_decoded, user_language=state.force_language)
        state.chunk_id += 1

    def streaming_transcribe(self, pcm16k: np.ndarray, state: StreamingState) -> str:
        """Feeds another slice of 16kHz mono audio into `state`.

        Returns the *cumulative* transcript so far (state.text), not just
        the new text since the last call — the caller is responsible for
        diffing against what it already sent the client, if needed.
        """
        x = np.asarray(pcm16k)
        if x.ndim != 1:
            x = x.reshape(-1)
        x = (x.astype(np.float32) / 32768.0) if x.dtype == np.int16 else x.astype(np.float32, copy=False)

        with self._lock:
            if x.shape[0] > 0:
                state.buffer = np.concatenate([state.buffer, x], axis=0)
            while state.buffer.shape[0] >= state.chunk_size_samples:
                chunk = state.buffer[:state.chunk_size_samples]
                state.buffer = state.buffer[state.chunk_size_samples:]
                self._streaming_step(state, chunk)
        return state.text

    def finish_streaming(self, state: StreamingState) -> str:
        """Flushes any buffered tail audio and returns the final cumulative
        transcript for this session. Call once when the client stops
        streaming (end of recording, or the connection closes)."""
        with self._lock:
            if state.buffer.shape[0] > 0:
                tail = state.buffer
                state.buffer = np.zeros((0,), dtype=np.float32)
                self._streaming_step(state, tail)
        return state.text


# Module-level singleton, initialized at FastAPI startup (see main.py).
model = AsrModel()
