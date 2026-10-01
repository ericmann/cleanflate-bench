"""Which source files make up each subject's decompression path (shared by LOC and similarity)."""

import sys
from pathlib import Path

from cfbench import config, sources

SUBJECTS = ["cf", "zlib", "zng", "zrs", "mox"]


class StaleManifest(RuntimeError):
    pass


def spec(subject: str) -> dict:
    return config.load_toml("decomp_paths.toml")[subject]


def _glob(root: Path, pattern: str) -> set[Path]:
    """Files matching a glob. A trailing `/**` means everything below (3.12 `**` yields only dirs)."""
    if pattern.endswith("/**"):
        pattern += "/*"
    return {p for p in root.glob(pattern) if p.is_file()}


def _expand(root: Path, patterns: list[str], subject: str) -> set[Path]:
    out: set[Path] = set()
    for pat in patterns:
        hits = _glob(root, pat)
        if not hits:
            raise StaleManifest(f"{subject}: include glob {pat!r} matches nothing under {root}")
        out |= hits
    return out


def resolve(subject: str, roots: list[Path], spec_: dict) -> list[Path]:
    """Apply a spec to explicit roots: roots[0] for `include`, roots[1:] for `extra_include`."""
    files = _expand(roots[0], spec_["include"], subject)
    if spec_.get("extra_include"):
        if len(roots) < 2:
            raise StaleManifest(f"{subject}: extra_include needs an extra root")
        files |= _expand(roots[1], spec_["extra_include"], subject)
    excluded: set[Path] = set()
    for root in roots:
        for pat in spec_.get("exclude", []):
            excluded |= _glob(root, pat)
    return sorted(files - excluded)


def files(subject: str, metadata: dict | None = None) -> list[Path]:
    """Sorted, de-duplicated decompression-path files for a subject. Stale globs raise."""
    root = sources.source_root(subject, metadata)
    roots = [root, *sources.extra_roots(subject, metadata)]
    return resolve(subject, roots, spec(subject))


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "list" or argv[1] not in SUBJECTS:
        print(f"usage: cfbench.decomp_paths list <{'|'.join(SUBJECTS)}>", file=sys.stderr)
        return 2
    root = sources.source_root(argv[1])
    for p in files(argv[1]):
        print(p.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
