"""Similarity measurements. Subcommands write raw `similarity` documents (machine `any`)."""

import argparse
import hashlib
import sys
from importlib import metadata
from pathlib import Path

from cfbench import config, decomp_paths, env, rawio, sources
from cfbench.similarity import pairs

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


COMMANDS = {"ngram": cmd_ngram}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=sorted(COMMANDS))
    a = ap.parse_args(argv)
    print(COMMANDS[a.cmd]())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
