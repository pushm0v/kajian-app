#!/usr/bin/env python3
"""Compare two (or more) self-hosted ASR backends on the same audio.

Fires each audio file at every backend's ``POST /transcribe`` endpoint and
reports, per model:

  * latency      — client wall-clock round-trip (includes upload + network)
  * server time  — pure inference time reported by the backend (processing_ms)
  * xRealtime    — audio_seconds / inference_seconds (higher = faster; >1 means
                   faster than real time)
  * WER / CER    — word / character error rate, ONLY when you provide reference
                   ("ground-truth") transcripts (--refs)
  * agreement    — when exactly two backends and no refs, the cross-model WER
                   (how much the two models disagree) as a rough quality proxy

Outputs a Markdown report and a CSV of raw rows. No heavyweight deps — only
``requests``. See README.md in this folder for usage.

Example:
  python compare_backends.py \
    --qwen   http://gpu-box:8000 \
    --whisper http://gpu-box:8001 \
    --audio ./samples --refs ./refs --locale id_ID \
    --repeat 3 --out report.md --csv rows.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import statistics
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency: pip install -r requirements.txt (needs 'requests').")

AUDIO_EXTS = (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".webm", ".mp4")


# ─────────────────────────── text + metrics ───────────────────────────
_ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Fair normalization before scoring: NFC, lowercase, strip Arabic
    harakat/tatweel and punctuation, collapse whitespace. Keeps Latin +
    Arabic letters and digits."""
    text = unicodedata.normalize("NFC", text or "").lower()
    text = _ARABIC_DIACRITICS.sub("", text)
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _edit_distance(ref: list, hyp: list) -> int:
    """Levenshtein distance between two token/char sequences (O(n*m))."""
    n, m = len(ref), len(hyp)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ri = ref[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ri == hyp[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def wer(ref: str, hyp: str) -> float | None:
    r = normalize(ref).split()
    if not r:
        return None
    return _edit_distance(r, normalize(hyp).split()) / len(r)


def cer(ref: str, hyp: str) -> float | None:
    r = list(normalize(ref).replace(" ", ""))
    if not r:
        return None
    return _edit_distance(r, list(normalize(hyp).replace(" ", ""))) / len(r)


# ─────────────────────────── backend I/O ───────────────────────────
@dataclass
class Backend:
    name: str
    url: str

    @property
    def base(self) -> str:
        return self.url.rstrip("/")


@dataclass
class Result:
    backend: str
    file: str
    ok: bool
    wall_ms: float = 0.0
    server_ms: float | None = None
    audio_s: float | None = None
    text: str = ""
    words: int = 0
    chars: int = 0
    segments: int = 0
    model: str = ""
    error: str = ""
    wall_runs: list[float] = field(default_factory=list)

    @property
    def x_realtime(self) -> float | None:
        secs = (self.server_ms / 1000.0) if self.server_ms else (self.wall_ms / 1000.0)
        if not self.audio_s or secs <= 0:
            return None
        return self.audio_s / secs


def wait_healthy(be: Backend, token: str, timeout_s: int) -> bool:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        try:
            r = requests.get(f"{be.base}/health", headers=headers, timeout=10)
            if r.status_code == 200 and r.json().get("status") == "ok":
                info = r.json()
                print(f"  ✓ {be.name}: {info.get('model','?')} on {info.get('device','?')}")
                return True
            last = f"status={r.status_code} body={r.text[:120]}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(2)
    print(f"  ✗ {be.name} not healthy within {timeout_s}s ({last})")
    return False


def transcribe(be: Backend, path: str, locale: str, token: str, timeout_s: int) -> Result:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with open(path, "rb") as f:
            t0 = time.perf_counter()
            resp = requests.post(
                f"{be.base}/transcribe",
                headers=headers,
                data={"locale": locale, "model": ""},
                files={"audio": (os.path.basename(path), f)},
                timeout=timeout_s,
            )
            wall_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code != 200:
            return Result(be.name, path, ok=False,
                          error=f"HTTP {resp.status_code}: {resp.text[:160]}")
        body = resp.json()
        segs = body.get("segments", []) or []
        text = " ".join(s.get("text", "").strip() for s in segs).strip()
        return Result(
            backend=be.name, file=path, ok=True, wall_ms=wall_ms,
            server_ms=body.get("processing_ms"),
            audio_s=body.get("audio_seconds") or _probe_duration(path),
            text=text, words=len(text.split()), chars=len(text),
            segments=len(segs), model=str(body.get("model", "")),
        )
    except Exception as e:  # noqa: BLE001
        return Result(be.name, path, ok=False, error=str(e))


def _probe_duration(path: str) -> float | None:
    """Fallback audio duration via ffprobe if the backend didn't report it."""
    try:
        import subprocess
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True, timeout=30,
        )
        return float(out.stdout.strip())
    except Exception:  # noqa: BLE001
        return None


# ─────────────────────────── run + report ───────────────────────────
def collect_audio(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for p in patterns:
        if os.path.isdir(p):
            for ext in AUDIO_EXTS:
                files += glob.glob(os.path.join(p, f"*{ext}"))
        else:
            files += glob.glob(p)
    return sorted(f for f in dict.fromkeys(files) if f.lower().endswith(AUDIO_EXTS))


def load_reference(refs_dir: str | None, audio_path: str) -> str | None:
    if not refs_dir:
        return None
    stem = os.path.splitext(os.path.basename(audio_path))[0]
    for cand in (f"{stem}.txt", f"{stem}.ref.txt"):
        fp = os.path.join(refs_dir, cand)
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                return f.read()
    return None


def run(backends, files, args) -> list[Result]:
    results: list[Result] = []
    for idx, path in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] {os.path.basename(path)}")
        for be in backends:
            walls: list[float] = []
            final: Result | None = None
            for r_i in range(args.repeat):
                res = transcribe(be, path, args.locale, args.token, args.timeout)
                if not res.ok:
                    final = res
                    break
                walls.append(res.wall_ms)
                final = res
            assert final is not None
            if final.ok:
                # Report best (min) wall latency across repeats; keep all runs.
                final.wall_runs = walls
                final.wall_ms = min(walls)
                tag = f"{final.wall_ms:7.0f}ms wall"
                if final.server_ms is not None:
                    tag += f" · {final.server_ms:6.0f}ms server"
                if final.x_realtime:
                    tag += f" · {final.x_realtime:5.1f}x RT"
                print(f"    {be.name:10s} {tag} · {final.words} words")
            else:
                print(f"    {be.name:10s} ERROR: {final.error}")
            results.append(final)
    return results


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def build_report(backends, files, results, args) -> str:
    by_be: dict[str, list[Result]] = {b.name: [] for b in backends}
    for r in results:
        by_be[r.backend].append(r)

    refs = {f: load_reference(args.refs, f) for f in files}
    have_refs = any(v for v in refs.values())

    lines = ["# ASR backend comparison", ""]
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Files: {len(files)} · Locale: `{args.locale}` · Repeats: {args.repeat}")
    lines.append("- Backends: " + ", ".join(f"**{b.name}** (`{b.url}`)" for b in backends))
    lines.append("")

    # Aggregate table
    lines.append("## Summary")
    lines.append("")
    header = ["Model", "OK", "wall ms (avg)", "server ms (avg)", "×realtime (avg)"]
    if have_refs:
        header += ["WER (avg)", "CER (avg)"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    agg = {}
    for b in backends:
        rs = [r for r in by_be[b.name] if r.ok]
        wall = _mean([r.wall_ms for r in rs])
        server = _mean([r.server_ms for r in rs])
        xrt = _mean([r.x_realtime for r in rs])
        row = [b.name, f"{len(rs)}/{len(files)}",
               f"{wall:.0f}" if wall else "—",
               f"{server:.0f}" if server else "—",
               f"{xrt:.1f}" if xrt else "—"]
        wers = cers = None
        if have_refs:
            wv = [wer(refs[r.file], r.text) for r in rs if refs.get(r.file)]
            cv = [cer(refs[r.file], r.text) for r in rs if refs.get(r.file)]
            wers, cers = _mean(wv), _mean(cv)
            row += [f"{wers*100:.1f}%" if wers is not None else "—",
                    f"{cers*100:.1f}%" if cers is not None else "—"]
        agg[b.name] = dict(wall=wall, server=server, xrt=xrt, wer=wers, cer=cers)
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Winners
    def _best(metric, lower_better):
        vals = [(n, a[metric]) for n, a in agg.items() if a[metric] is not None]
        if not vals:
            return None
        return (min if lower_better else max)(vals, key=lambda kv: kv[1])

    fastest = _best("xrt", lower_better=False)
    most_acc = _best("wer", lower_better=True) if have_refs else None
    lines.append("### Verdict")
    if fastest:
        lines.append(f"- **Fastest:** {fastest[0]} ({fastest[1]:.1f}× realtime).")
    if most_acc:
        lines.append(f"- **Most accurate:** {most_acc[0]} (WER {most_acc[1]*100:.1f}%).")
    if not have_refs and len(backends) == 2:
        a, b = backends
        ra = {r.file: r for r in by_be[a.name] if r.ok}
        rb = {r.file: r for r in by_be[b.name] if r.ok}
        shared = [f for f in files if f in ra and f in rb]
        disagree = _mean([wer(ra[f].text, rb[f].text) for f in shared])
        if disagree is not None:
            lines.append(
                f"- **Model disagreement:** {disagree*100:.1f}% cross-model WER "
                f"({a.name} vs {b.name}). No ground truth supplied, so this is a "
                f"similarity proxy, not accuracy — add `--refs` for real WER.")
    lines.append("")

    # Per-file table
    lines.append("## Per file")
    lines.append("")
    head = ["File", "Model", "wall ms", "server ms", "×RT", "words"]
    if have_refs:
        head += ["WER"]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("|" + "|".join(["---"] * len(head)) + "|")
    for f in files:
        for b in backends:
            r = next((x for x in by_be[b.name] if x.file == f), None)
            if r is None:
                continue
            if not r.ok:
                lines.append(f"| {os.path.basename(f)} | {b.name} | ERROR: {r.error[:40]} | | | |")
                continue
            row = [os.path.basename(f), b.name,
                   f"{r.wall_ms:.0f}",
                   f"{r.server_ms:.0f}" if r.server_ms is not None else "—",
                   f"{r.x_realtime:.1f}" if r.x_realtime else "—",
                   str(r.words)]
            if have_refs:
                w = wer(refs[f], r.text) if refs.get(f) else None
                row.append(f"{w*100:.1f}%" if w is not None else "—")
            lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    if not have_refs:
        lines.append("> Tip: drop `<audiobasename>.txt` ground-truth files in a folder "
                     "and pass `--refs <folder>` to get real WER/CER accuracy numbers.")
    return "\n".join(lines) + "\n"


def write_csv(path, results, refs_dir):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["backend", "file", "ok", "wall_ms", "server_ms", "audio_s",
                    "x_realtime", "words", "chars", "segments", "model", "wer",
                    "cer", "error"])
        for r in results:
            ref = load_reference(refs_dir, r.file) if r.ok else None
            w.writerow([
                r.backend, os.path.basename(r.file), r.ok,
                f"{r.wall_ms:.1f}", "" if r.server_ms is None else r.server_ms,
                "" if r.audio_s is None else r.audio_s,
                "" if r.x_realtime is None else f"{r.x_realtime:.3f}",
                r.words, r.chars, r.segments, r.model,
                "" if not ref else f"{wer(ref, r.text):.4f}",
                "" if not ref else f"{cer(ref, r.text):.4f}",
                r.error,
            ])


def dump_transcripts(out_dir, results):
    os.makedirs(out_dir, exist_ok=True)
    for r in results:
        if not r.ok:
            continue
        stem = os.path.splitext(os.path.basename(r.file))[0]
        with open(os.path.join(out_dir, f"{stem}.{r.backend}.txt"), "w",
                  encoding="utf-8") as f:
            f.write(r.text + "\n")


def parse_args(argv):
    p = argparse.ArgumentParser(description="Compare ASR backends on the same audio.")
    p.add_argument("--qwen", help="Base URL of the Qwen3-ASR backend")
    p.add_argument("--whisper", help="Base URL of the Whisper backend")
    p.add_argument("--backend", action="append", default=[],
                   metavar="NAME=URL", help="Add an arbitrary backend (repeatable)")
    p.add_argument("--audio", nargs="+", required=True,
                   help="Audio files, globs, or a folder of audio")
    p.add_argument("--refs", help="Folder of <audiobasename>.txt ground-truth transcripts")
    p.add_argument("--locale", default="id_ID")
    p.add_argument("--token", default=os.environ.get("ASR_API_TOKEN", ""),
                   help="Bearer token if backends require one")
    p.add_argument("--repeat", type=int, default=1,
                   help="Requests per (file,backend); best wall latency is reported")
    p.add_argument("--timeout", type=int, default=1800, help="Per-request timeout (s)")
    p.add_argument("--health-timeout", type=int, default=120,
                   help="Seconds to wait for each backend to become healthy")
    p.add_argument("--out", default="report.md", help="Markdown report path")
    p.add_argument("--csv", default="rows.csv", help="CSV rows path")
    p.add_argument("--dump", help="Optional folder to write each model's transcript")
    p.add_argument("--skip-health", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    backends: list[Backend] = []
    if args.qwen:
        backends.append(Backend("qwen", args.qwen))
    if args.whisper:
        backends.append(Backend("whisper", args.whisper))
    for spec in args.backend:
        if "=" not in spec:
            sys.exit(f"--backend expects NAME=URL, got: {spec}")
        name, url = spec.split("=", 1)
        backends.append(Backend(name.strip(), url.strip()))
    if not backends:
        sys.exit("No backends. Pass --qwen URL and/or --whisper URL (or --backend NAME=URL).")

    files = collect_audio(args.audio)
    if not files:
        sys.exit(f"No audio files matched: {args.audio}")

    print(f"Backends: {', '.join(b.name for b in backends)} | Files: {len(files)}")
    if not args.skip_health:
        print("Health checks:")
        healthy = [b for b in backends if wait_healthy(b, args.token, args.health_timeout)]
        if len(healthy) != len(backends):
            unhealthy = [b.name for b in backends if b not in healthy]
            print(f"Warning: skipping unhealthy backend(s): {', '.join(unhealthy)}")
        backends = healthy
        if not backends:
            sys.exit("No healthy backends to test.")

    results = run(backends, files, args)

    report = build_report(backends, files, results, args)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    write_csv(args.csv, results, args.refs)
    if args.dump:
        dump_transcripts(args.dump, results)

    print("\n" + report)
    print(f"Report → {args.out} · CSV → {args.csv}")


if __name__ == "__main__":
    main()
