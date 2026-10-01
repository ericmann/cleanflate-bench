"""Exact-match identifier overlap, excluding RFC-mandated and language/std names (SPEC 3.8)."""

import re
from pathlib import Path

from cfbench import config, paths
from cfbench.similarity import tokens

ID_NODES = {"identifier", "field_identifier", "type_identifier"}
_LANGUAGE_HEADER = re.compile(r"^#\s*language\s*$")
_RFC_HEADER = re.compile(r"^#\s*rfc\s*$")


def normalize(name: str) -> str:
    """Lowercase and drop underscores so snake_case and camelCase compare equal."""
    return name.lower().replace("_", "")


def exclusions_path() -> Path:
    return paths.CONFIG / "rfc_identifiers.txt"


def parse_exclusions(text: str) -> dict[str, set[str]]:
    """{'rfc': normalised names, 'language': normalised names} from rfc_identifiers.txt."""
    section = "rfc"
    out: dict[str, set[str]] = {"rfc": set(), "language": set()}
    for line in text.splitlines():
        stripped = line.strip()
        if _LANGUAGE_HEADER.match(stripped):
            section = "language"
            continue
        if _RFC_HEADER.match(stripped):
            section = "rfc"
            continue
        name = stripped.split("#", 1)[0].strip()
        if name:
            out[section].add(normalize(name))
    return out


def load_exclusions() -> dict[str, set[str]]:
    return parse_exclusions(exclusions_path().read_text(encoding="utf-8"))


def collect(files: list[Path], min_len: int, excluded: set[str]) -> set[str]:
    """Normalised identifiers of length >= min_len, minus the excluded names."""
    found: set[str] = set()
    for f in files:
        for t in tokens.tokenize(f):
            if t.kind == "ID" and t.node in ID_NODES:
                n = normalize(t.text)
                if len(n) >= min_len and n not in excluded:
                    found.add(n)
    return found


def compare(left: set[str], right: set[str]) -> dict:
    shared = left & right
    union = left | right
    return {
        "ident_jaccard": len(shared) / len(union) if union else 0.0,
        "ident_match_rate_left": len(shared) / len(left) if left else 0.0,
        "ident_match_rate_right": len(shared) / len(right) if right else 0.0,
        "size_left": len(left),
        "size_right": len(right),
        "shared": sorted(shared),
    }


def min_ident_len(cfg: dict | None = None) -> int:
    return (cfg or config.load_config("full"))["similarity"]["min_ident_len"]
