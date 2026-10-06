"""Subject pairs (controls and tests) and token n-gram similarity over decompression paths."""

from pathlib import Path

from cfbench import config
from cfbench.similarity import ngram, tokens

LANGUAGE = {"cf": "rust", "zrs": "rust", "mox": "rust", "zlib": "c", "zng": "c"}
ROLES = ("negative", "positive", "test")
REFERENCE = "reference"


def _key(p: dict) -> tuple[str, str]:
    return p["left"], p["right"]


def reference_pairs(cfg: dict | None = None) -> list[dict]:
    """The reference pairs (added after the pre-registered analysis), in config order."""
    cfg = cfg or config.load_config("full")
    out = []
    for p in cfg["similarity"].get("reference_pairs", []):
        if p["role"] != REFERENCE:
            raise ValueError(f"reference pair with role {p['role']!r}")
        out.append({"left": p["left"], "right": p["right"], "role": REFERENCE})
    return out


def reference_labels(cfg: dict | None = None) -> list[str]:
    return [f"{p['left']}-{p['right']}" for p in reference_pairs(cfg)]


def load_pairs(cfg: dict | None = None, reference: bool = False) -> list[dict]:
    """The configured pairs: {left, right, role, cross_language}.

    With `reference`, the reference pairs follow; one that is already a pre-registered pair keeps
    its pre-registered role and is measured once.
    """
    cfg = cfg or config.load_config("full")
    out = []
    for p in cfg["similarity"]["pairs"]:
        if p["role"] not in ROLES:
            raise ValueError(f"unknown pair role {p['role']!r}")
        out.append(
            {
                "left": p["left"],
                "right": p["right"],
                "role": p["role"],
                "cross_language": LANGUAGE[p["left"]] != LANGUAGE[p["right"]],
            }
        )
    if reference:
        seen = {_key(p) for p in out}
        for p in reference_pairs(cfg):
            if _key(p) not in seen:
                seen.add(_key(p))
                out.append({**p, "cross_language": LANGUAGE[p["left"]] != LANGUAGE[p["right"]]})
    return out


def file_token_lists(files: list[Path]) -> list[list[str]]:
    """Normalised token stream per file, in file order."""
    return [[t.norm for t in tokens.tokenize(f)] for f in files]


def shingle_union(token_lists: list[list[str]], n: int) -> set[tuple]:
    """Union of per-file n-grams; no n-gram spans a file boundary."""
    out: set[tuple] = set()
    for toks in token_lists:
        out |= ngram.shingles(toks, n)
    return out


def compare_pair(
    left: list[list[str]], right: list[list[str]], cfg: dict | None = None
) -> list[dict]:
    """One result row for every n in ngram_min..ngram_max."""
    cfg = cfg or config.load_config("full")
    sim = cfg["similarity"]
    rows = []
    for n in range(sim["ngram_min"], sim["ngram_max"] + 1):
        a, b = shingle_union(left, n), shingle_union(right, n)
        rows.append(
            {
                "n": n,
                "jaccard": ngram.jaccard(a, b),
                "containment": ngram.containment(a, b),
                "size_left": len(a),
                "size_right": len(b),
            }
        )
    return rows
