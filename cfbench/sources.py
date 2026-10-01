"""Locations of subject source trees (for LOC, unsafe scans and provenance)."""

import json
import subprocess
from pathlib import Path

from cfbench import config, paths


class SourceMissing(RuntimeError):
    pass


def package_dirs(metadata: dict) -> dict[str, Path]:
    """Map package name to its directory from `cargo metadata` output."""
    return {p["name"]: Path(p["manifest_path"]).parent for p in metadata["packages"]}


def cargo_metadata() -> dict:
    out = subprocess.run(
        ["cargo", "metadata", "--format-version", "1", "--locked"],
        cwd=paths.ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def _pkg(name: str, metadata: dict | None) -> Path:
    dirs = package_dirs(metadata or cargo_metadata())
    if name not in dirs or not dirs[name].is_dir():
        raise SourceMissing(f"crate {name} not found: run `cargo fetch`")
    return dirs[name]


def _need(path: Path, target: str) -> Path:
    if not path.is_dir():
        raise SourceMissing(f"{path} is missing: run `make {target}`")
    return path


def source_root(subject: str, metadata: dict | None = None) -> Path:
    subj = config.load_toml("subjects.toml")
    if subject == "cf":
        return _need(paths.THIRD_PARTY / "cleanflate" / "crates" / "cleanflate", "fetch")
    if subject in ("zlib", "zng"):
        v = subj[subject]["version"]
        name = "zlib" if subject == "zlib" else "zlib-ng"
        return _need(paths.THIRD_PARTY / "src" / f"{name}-{v}", "c-subjects")
    if subject == "zrs":
        return _pkg(subj["zrs"]["core_crate"], metadata)
    if subject == "mox":
        return _pkg(subj["mox"]["crate"], metadata)
    raise ValueError(f"no source root for subject {subject!r}")


def extra_roots(subject: str, metadata: dict | None = None) -> list[Path]:
    if subject == "zrs":
        return [_pkg(config.load_toml("subjects.toml")["zrs"]["crate"], metadata)]
    return []
