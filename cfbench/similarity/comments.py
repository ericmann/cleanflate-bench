"""Comment word n-gram overlap (SPEC 3.8)."""

import re
from pathlib import Path

from cfbench.similarity import ngram, tokens

_WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> list[str]:
    """Lowercase alphanumeric runs; comment markers and punctuation vanish."""
    return _WORD.findall(text.lower())


def comment_shingles(files: list[Path], n: int) -> tuple[set[tuple], int]:
    """(word n-grams over every comment, number of comments). N-grams never span two comments."""
    out: set[tuple] = set()
    count = 0
    for f in files:
        for _line, text in tokens.comments(f):
            count += 1
            out |= ngram.shingles(words(text), n)
    return out, count


def compare(left: set[tuple], right: set[tuple]) -> dict:
    return {
        "jaccard": ngram.jaccard(left, right),
        "containment": ngram.containment(left, right),
        "size_left": len(left),
        "size_right": len(right),
    }
