"""Pinned downloads: every file is checked against a SHA-256 recorded in config/."""

import hashlib
import shutil
import tarfile
import urllib.request
from pathlib import Path

from cfbench import paths


class DownloadError(RuntimeError):
    pass


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "cfbench"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def downloads_dir() -> Path:
    return paths.THIRD_PARTY / "downloads"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, sha256: str, dest_dir: Path | None = None) -> Path:
    dest_dir = dest_dir or downloads_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / url.rstrip("/").rsplit("/", 1)[-1]
    if dest.exists() and sha256 and sha256_file(dest) == sha256:
        return dest
    data = _fetch_bytes(url)
    got = hashlib.sha256(data).hexdigest()
    if not sha256:
        raise DownloadError(f"no sha256 pinned for {url}; computed {got}")
    if got != sha256:
        raise DownloadError(f"sha256 mismatch for {url}: pinned {sha256}, got {got}")
    dest.write_bytes(data)
    return dest


def extract(tarball: Path, dest: Path) -> Path:
    """Extract into dest, stripping the archive's single top-level directory."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(tarball) as tf:
        for m in tf.getmembers():
            parts = Path(m.name).parts[1:]
            if not parts or ".." in parts:
                continue
            m.name = str(Path(*parts))
            tf.extract(m, dest, filter="data")
    return dest
