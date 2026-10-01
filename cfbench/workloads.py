"""Benchmark workloads: corpus files compressed by stock zlib (SPEC 3.2) plus tiny prefixes."""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from cfbench import cleanflate_src, config, paths


class WorkloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Workload:
    id: str
    corpus: str
    file: str
    level: int
    framing: str
    orig_path: Path
    path: Path
    orig_len: int
    len: int | None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["orig_path"] = str(self.orig_path)
        d["path"] = str(self.path)
        return d


def workloads_dir() -> Path:
    return paths.DATA / "workloads"


def manifest_path() -> Path:
    return paths.DATA / "manifests" / "workloads.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class _Input:
    id: str
    corpus: str
    file: str
    orig_path: Path
    orig_len: int
    src_path: Path
    src_sha: str
    prefix: int | None


def _inputs(cfg: dict) -> list[_Input]:
    """Every selected input: corpus files plus tiny prefixes (tiny is always included)."""
    perf = cfg["perf"]
    wanted = set(perf["files"])
    out = []
    for corpus in perf["corpora"]:
        for name, path, sha, nbytes in cleanflate_src.corpus_files(corpus):
            if wanted and f"{corpus}/{name}" not in wanted:
                continue
            orig = workloads_dir() / corpus / name / "orig"
            out.append(_Input(f"{corpus}/{name}", corpus, name, orig, nbytes, path, sha, None))
    for src in perf["tiny"]["sources"]:
        corpus, name = src.split("/", 1)
        files = {n: (p, s, b) for n, p, s, b in cleanflate_src.corpus_files(corpus)}
        path, sha, size = files[name]
        for prefix in perf["tiny"]["prefix_bytes"]:
            tid = f"{corpus}-{name}-{prefix}"
            orig = workloads_dir() / "tiny" / tid / "orig"
            out.append(
                _Input(f"tiny/{tid}", "tiny", tid, orig, min(prefix, size), path, sha, prefix)
            )
    return out


def list_workloads(cfg: dict) -> list[Workload]:
    perf = cfg["perf"]
    result = []
    for i in _inputs(cfg):
        for level in perf["levels"]:
            for framing in perf["framings"]:
                p = i.orig_path.parent / f"l{level}.{framing}"
                size = p.stat().st_size if p.exists() else None
                result.append(
                    Workload(
                        i.id, i.corpus, i.file, level, framing, i.orig_path, p, i.orig_len, size
                    )
                )
    return sorted(result, key=lambda w: (w.id, w.level, w.framing))


def load_manifest() -> dict | None:
    p = manifest_path()
    return json.loads(p.read_text()) if p.exists() else None


def _key(e: dict) -> tuple:
    return (e["id"], e["level"], e["framing"])


def zlib_compress(orig: Path, level: int, framing: str, out: Path) -> None:
    exe = paths.ROOT / "target" / "release" / "cfb-zlib"
    if not exe.exists():
        raise WorkloadError("cfb-zlib is not built: run `make subjects`")
    res = subprocess.run(
        [
            str(exe),
            "compress",
            "--level",
            str(level),
            "--framing",
            framing,
            "--input",
            str(orig),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ok = res.returncode == 0 and json.loads(res.stdout).get("ok")
    if not ok:
        raise WorkloadError(f"compress failed for {orig} l{level} {framing}: {res.stdout}")


def zlib_version() -> str:
    exe = paths.ROOT / "target" / "release" / "cfb-zlib"
    out = subprocess.run([str(exe), "info"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["impl_version"]


def _prepare_origs(cfg: dict) -> None:
    for i in _inputs(cfg):
        data = _verified_bytes(i.src_path, i.src_sha)
        if i.prefix is not None:
            data = data[: i.prefix]
        i.orig_path.parent.mkdir(parents=True, exist_ok=True)
        if not i.orig_path.exists() or i.orig_path.read_bytes() != data:
            i.orig_path.write_bytes(data)


def _verified_bytes(path: Path, sha: str) -> bytes:
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise WorkloadError(f"{path}: SHA-256 differs from corpus SOURCES.json")
    return data


def _entry(w: Workload) -> dict:
    return {
        "id": w.id,
        "corpus": w.corpus,
        "level": w.level,
        "framing": w.framing,
        "input_sha256": sha256_file(w.orig_path),
        "input_len": w.orig_len,
        "path": str(w.path.relative_to(paths.DATA)),
        "sha256": sha256_file(w.path),
        "len": w.path.stat().st_size,
    }


def generate(cfg: dict | None = None, compressor=None, write_manifest: bool = False) -> list[dict]:
    cfg = cfg or config.load_config()
    compressor = compressor or zlib_compress
    _prepare_origs(cfg)
    manifest = load_manifest()
    known = {_key(e): e for e in (manifest or {}).get("entries", [])}
    entries = []
    for w in list_workloads(cfg):
        want = known.get((w.id, w.level, w.framing))
        if w.path.exists():
            e = _entry(w)
            if want and want["sha256"] != e["sha256"]:
                raise WorkloadError(f"refusing to overwrite {w.path}: hash differs from manifest")
        else:
            compressor(w.orig_path, w.level, w.framing, w.path)
            e = _entry(w)
            if want and want["sha256"] != e["sha256"]:
                w.path.unlink()
                raise WorkloadError(f"{w.path}: regenerated stream differs from manifest")
        entries.append(e)
    if write_manifest:
        if cfg["perf"]["files"]:
            raise WorkloadError("--write-manifest needs the full profile (no files filter)")
        write(entries)
    return entries


def write(entries: list[dict]) -> None:
    doc = {
        "zlib_version": zlib_version(),
        "generated_by": "cfbench.workloads",
        "entries": sorted(entries, key=_key),
    }
    p = manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, sort_keys=True, indent=1) + "\n")


def verify(cfg: dict | None = None) -> list[str]:
    cfg = cfg or config.load_config()
    manifest = load_manifest()
    if manifest is None:
        return [f"{manifest_path()} is missing"]
    known = {_key(e): e for e in manifest["entries"]}
    problems = []
    for w in list_workloads(cfg):
        want = known.get((w.id, w.level, w.framing))
        if want is None:
            problems.append(f"{w.id} l{w.level} {w.framing}: not in manifest")
        elif not w.path.exists():
            problems.append(f"{w.path}: missing")
        elif sha256_file(w.path) != want["sha256"]:
            problems.append(f"{w.path}: SHA-256 differs from manifest")
    return problems


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["generate", "verify"])
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "generate":
            entries = generate(write_manifest=a.write_manifest)
            print(f"{len(entries)} workload streams ready")
            return 0
        problems = verify()
    except (WorkloadError, cleanflate_src.SourceError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("workloads verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
