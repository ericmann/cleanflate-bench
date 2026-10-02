"""Similarity measurements. Subcommands write raw `similarity` documents (machine `any`)."""

import argparse
import hashlib
import sys
from importlib import metadata
from pathlib import Path

from cfbench import config, decomp_paths, env, paths, rawio, sources
from cfbench.similarity import comments, identifiers, pairs

TOOL_PACKAGES = ["tree-sitter", "tree-sitter-rust", "tree-sitter-c"]


def tool_versions() -> dict:
    return {name: metadata.version(name) for name in TOOL_PACKAGES}


def _rel(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


def subject_files(subject: str) -> list[dict]:
    """Decompression-path files with SHA-256, paths relative to the subject's source root."""
    root = sources.source_root(subject)
    out = []
    for f in decomp_paths.files(subject):
        try:
            rel = _rel(f, root)
        except ValueError:
            rel = f.as_posix()
        out.append({"path": rel, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    return out


def ngram_payload(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load_config("full")
    plist = pairs.load_pairs(cfg)
    subjects = sorted({s for p in plist for s in (p["left"], p["right"])})
    paths_by = {s: decomp_paths.files(s) for s in subjects}
    streams = {s: pairs.file_token_lists(paths_by[s]) for s in subjects}
    results = []
    for p in plist:
        results.append(
            {**p, "results": pairs.compare_pair(streams[p["left"]], streams[p["right"]], cfg)}
        )
    return {
        "kind": "ngram",
        "ngram_min": cfg["similarity"]["ngram_min"],
        "ngram_max": cfg["similarity"]["ngram_max"],
        "pairs": results,
        "files": {s: subject_files(s) for s in subjects},
        "tokens": {s: sum(len(t) for t in streams[s]) for s in subjects},
        "tools": tool_versions(),
    }


def cmd_ngram() -> Path:
    payload = ngram_payload()
    return rawio.write_raw(
        "similarity",
        payload,
        machine="any",
        profile="full",
        script="cfbench.similarity.run ngram",
        environment=env.capture_environment(),
    )


def identifiers_payload(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load_config("full")
    min_len = identifiers.min_ident_len(cfg)
    excl = identifiers.load_exclusions()
    excluded = excl["rfc"] | excl["language"]
    plist = pairs.load_pairs(cfg)
    subjects = sorted({s for p in plist for s in (p["left"], p["right"])})
    ids = {s: identifiers.collect(decomp_paths.files(s), min_len, excluded) for s in subjects}
    # post-hoc sensitivity analysis: the same sets minus the extended list (never the T1 claim)
    extra = identifiers.load_posthoc()
    extended = excluded | extra["rfc"] | extra["language"]
    filtered = {s: {n for n in v if n not in extended} for s, v in ids.items()}
    results = [
        {
            **p,
            **identifiers.compare(ids[p["left"]], ids[p["right"]]),
            **identifiers.compare(filtered[p["left"]], filtered[p["right"]], "_filtered"),
        }
        for p in plist
    ]
    text = identifiers.exclusions_path().read_bytes()
    posthoc = identifiers.posthoc_path().read_bytes()
    return {
        "kind": "identifiers",
        "min_ident_len": min_len,
        "exclusions": {
            "sha256": hashlib.sha256(text).hexdigest(),
            "rfc_names": len(excl["rfc"]),
            "language_names": len(excl["language"]),
        },
        "exclusions_posthoc": {
            "sha256": hashlib.sha256(posthoc).hexdigest(),
            "rfc_names": len(extra["rfc"]),
            "language_names": len(extra["language"]),
        },
        "identifier_counts": {s: len(v) for s, v in ids.items()},
        "identifier_counts_filtered": {s: len(v) for s, v in filtered.items()},
        "pairs": results,
        "files": {s: subject_files(s) for s in subjects},
        "tools": tool_versions(),
    }


def comments_payload(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load_config("full")
    n = cfg["similarity"]["comment_ngram"]
    plist = pairs.load_pairs(cfg)
    subjects = sorted({s for p in plist for s in (p["left"], p["right"])})
    sets, counts = {}, {}
    for s in subjects:
        sets[s], counts[s] = comments.comment_shingles(decomp_paths.files(s), n)
    results = [{**p, **comments.compare(sets[p["left"]], sets[p["right"]])} for p in plist]
    return {
        "kind": "comments",
        "comment_ngram": n,
        "comment_counts": counts,
        "pairs": results,
        "files": {s: subject_files(s) for s in subjects},
        "tools": tool_versions(),
    }


def cmd_identifiers() -> Path:
    payload = identifiers_payload()
    # published copy of the exclusion list, byte for byte
    out = paths.RESULTS / "similarity_identifier_exclusions.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(identifiers.exclusions_path().read_bytes())
    out_posthoc = paths.RESULTS / "similarity_identifier_exclusions_posthoc.txt"
    out_posthoc.write_bytes(identifiers.posthoc_path().read_bytes())
    return rawio.write_raw(
        "similarity",
        payload,
        machine="any",
        profile="full",
        script="cfbench.similarity.run identifiers",
        environment=env.capture_environment(),
    )


def cmd_comments() -> Path:
    return rawio.write_raw(
        "similarity",
        comments_payload(),
        machine="any",
        profile="full",
        script="cfbench.similarity.run comments",
        environment=env.capture_environment(),
    )


COMMANDS = {"ngram": cmd_ngram, "identifiers": cmd_identifiers, "comments": cmd_comments}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=sorted(COMMANDS))
    a = ap.parse_args(argv)
    print(COMMANDS[a.cmd]())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
