"""Stub replacement for the real `nagisa` package.

Why this exists: `qwen_asr`'s top-level `__init__.py` unconditionally
imports `qwen3_forced_aligner.py`, which does `import nagisa` at module
level — even though nagisa is only ever *used* for Japanese-specific
tokenization inside `Qwen3ForcedAligner`, a class this backend never
instantiates (our forced-timestamp needs are handled by chunk-based
approximate timestamps instead — see transcription.py's module
docstring for why: the real forced aligner doesn't officially support
Indonesian/Arabic, our actual languages, anyway).

The real `nagisa` package pulls in a prebuilt `dyNET` binary
(`libdynet-*.so`) that crashes with SIGILL (illegal instruction, exit
code 132) on some hosts — confirmed via `dmesg` showing `trap invalid
opcode ... in libdynet-*.so`. This is a well-known class of bug:
dynet's own CMakeLists.txt hardcodes `-march=native`, so its PyPI wheel
only runs correctly on CPUs with the exact instruction set of whatever
machine built it. There's no env var or install flag to fix this in
the real package.

Since nothing in our code path ever calls into nagisa, this stub
satisfies `import nagisa` (and qwen_asr's transitive
`from qwen_asr import Qwen3ASRModel` import) without loading the real,
crashing package at all. If qwen_asr's forced aligner is ever actually
used in the future, calling `nagisa.tagging()` will raise
NotImplementedError immediately, rather than crashing the whole
process — a clear, debuggable failure instead of a silent SIGILL.
"""


class _StubTaggedText:
    words: list = []


def tagging(text: str) -> _StubTaggedText:
    raise NotImplementedError(
        "nagisa is stubbed out in this backend (see stubs/nagisa_stub/) "
        "because the real package's dynet dependency crashes with SIGILL "
        "on some hosts, and this backend never uses Qwen3ForcedAligner's "
        "Japanese-tokenization path. If you need real nagisa "
        "functionality, remove the stub install step from the Dockerfile."
    )
