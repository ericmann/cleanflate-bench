"""Token n-gram shingles and set similarity."""

from collections.abc import Iterable
from pathlib import Path

from cfbench.similarity import tokens


def shingles(toks: list, n: int) -> set[tuple]:
    """All n-grams of the normalised token stream. Items may be Tokens or plain strings."""
    norm = [t.norm if hasattr(t, "norm") else t for t in toks]
    return {tuple(norm[i : i + n]) for i in range(len(norm) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def containment(a: set, b: set) -> float:
    """|A intersect B| / min(|A|, |B|)."""
    smaller = min(len(a), len(b))
    return len(a & b) / smaller if smaller else 0.0


def file_shingles(files: Iterable[Path | str], n: int) -> set[tuple]:
    """Union of per-file shingles (n-grams never span two files)."""
    out: set[tuple] = set()
    for f in files:
        out |= shingles(tokens.tokenize(f), n)
    return out


def compare(files_a: Iterable[Path | str], files_b: Iterable[Path | str], n: int) -> dict:
    a, b = file_shingles(files_a, n), file_shingles(files_b, n)
    return {
        "jaccard": jaccard(a, b),
        "containment": containment(a, b),
        "size_a": len(a),
        "size_b": len(b),
    }
