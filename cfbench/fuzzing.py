"""Run the differential fuzz targets for a CPU budget and archive their corpora (SPEC 3.6 and 4).

`make fuzz` runs the full budget (a human step). `make fuzz-smoke` runs `fuzz.smoke_seconds` on one
job and writes to the gitignored smoke tree. Each target gets a raw document of kind `fuzz` in
`correctness/<machine>` plus a `<timestamp>-fuzz-<target>.tar.gz` of its minimized corpus and
artifacts, recorded by path and SHA-256.
"""

import hashlib
import re
import subprocess
import sys
import tarfile
from pathlib import Path

from cfbench import config, env, machine, malformed, paths, rawio, workloads

KIND = "fuzz"
SCRIPT = "cfbench.fuzzing"
FUZZ_DIR = paths.ROOT / "fuzz"
SEED_LEVEL = 6
FRAMING_BYTE = {"raw": 0, "zlib": 1, "gzip": 2}
MOX_FRAMINGS = ("raw", "zlib")

_EXECUTED = re.compile(r"^stat::number_of_executed_units:\s*(\d+)", re.MULTILINE)
_HASH_LINE = re.compile(r"^#(\d+)\b", re.MULTILINE)
_COV = re.compile(r"cov:\s*(\d+)\s+ft:\s*(\d+)")
_EXEC_S = re.compile(r"exec/s:\s*(\d+)")
_FORK_CRASH = re.compile(r"oom/timeout/crash:\s*(\d+)/(\d+)/(\d+)")
_ARTIFACT = re.compile(r"Test unit written to (\S+)")


def parse_libfuzzer(text: str) -> dict:
    """Execution count, exec/s, coverage and divergence artifacts from a libFuzzer log."""
    m = _EXECUTED.findall(text)
    hashes = _HASH_LINE.findall(text)
    executed = int(m[-1]) if m else (int(hashes[-1]) if hashes else None)
    cov = _COV.findall(text)
    speeds = _EXEC_S.findall(text)
    forks = _FORK_CRASH.findall(text)
    artifacts = sorted(set(_ARTIFACT.findall(text)))
    crashes = int(forks[-1][2]) if forks else 0
    return {
        "executed": executed,
        "exec_per_s": int(speeds[-1]) if speeds else None,
        "cov": int(cov[-1][0]) if cov else None,
        "ft": int(cov[-1][1]) if cov else None,
        "divergences": max(crashes, len(artifacts)),
        "artifacts": artifacts,
    }


def seconds_per_job(cfg: dict, profile: str) -> int:
    """Wall-clock seconds each job runs: the CPU budget split across jobs, or the smoke length."""
    f = cfg["fuzz"]
    if profile != "full":
        return int(f["smoke_seconds"])
    return int(f["budget_cpu_hours"] * 3600 / f["jobs"])


def run_argv(target: str, cfg: dict, profile: str) -> list[str]:
    f = cfg["fuzz"]
    return ["cargo", "+nightly", "fuzz", "run", target, "--", f"-fork={f['jobs']}",
            "-ignore_crashes=1", f"-max_total_time={seconds_per_job(cfg, profile)}",
            f"-seed={f['seed']}"]  # fmt: skip


def seed_bytes(target: str, framing: str, data: bytes) -> bytes | None:
    """The framing byte followed by the stream; None when the target cannot take the framing."""
    if target.endswith("_mox") and framing not in MOX_FRAMINGS:
        return None
    return bytes([FRAMING_BYTE[framing]]) + data


def seed_inputs(cfg: dict, clone: Path | None = None) -> list[tuple[str, str, Path]]:
    """(name, framing, path) for every level-6 workload stream and every malformed file."""
    out = []
    for w in workloads.list_workloads(cfg):
        if w.level == SEED_LEVEL and w.path.exists():
            out.append((f"wl_{w.id.replace('/', '_')}_{w.framing}", w.framing, w.path))
    root = malformed.malformed_dir(clone)
    for rel in malformed.list_files(root):
        out.append((f"mal_{rel.replace('/', '_')}", malformed.framing_of(rel), root / rel))
    return out


def write_seeds(cfg: dict, targets: list[str], corpus_root: Path, clone: Path | None = None) -> int:
    """Write the prefixed seeds into `<corpus_root>/<target>/`; returns the files written."""
    n = 0
    inputs = seed_inputs(cfg, clone)
    for t in targets:
        d = corpus_root / t
        d.mkdir(parents=True, exist_ok=True)
        for name, framing, path in inputs:
            data = seed_bytes(t, framing, path.read_bytes())
            if data is not None:
                (d / name).write_bytes(data)
                n += 1
    return n


def count_files(d: Path) -> int:
    return sum(1 for p in d.rglob("*") if p.is_file()) if d.is_dir() else 0


def archive(target: str, corpus: Path, artifacts: Path, dest: Path) -> dict:
    """tar.gz the minimized corpus and the artifacts; returns path, sha256 and size."""
    with tarfile.open(dest, "w:gz") as tar:
        for base, label in ((corpus, "corpus"), (artifacts, "artifacts")):
            if base.is_dir():
                tar.add(base, arcname=f"{target}/{label}")
    return {"path": dest.relative_to(paths.ROOT).as_posix() if dest.is_relative_to(paths.ROOT) else dest.as_posix(),
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "bytes": dest.stat().st_size}  # fmt: skip


def run_target(target: str, cfg: dict, profile: str, runner=subprocess.run) -> dict:
    corpus = FUZZ_DIR / "corpus" / target
    artifacts = FUZZ_DIR / "artifacts" / target
    before = count_files(artifacts)
    argv = run_argv(target, cfg, profile)
    res = runner(
        argv, cwd=paths.ROOT, capture_output=True, text=True, errors="replace", check=False
    )
    stats = parse_libfuzzer(res.stdout + "\n" + res.stderr)
    stats["divergences"] = max(stats["divergences"], count_files(artifacts) - before)
    seeds = count_files(corpus)
    runner(["cargo", "+nightly", "fuzz", "cmin", target], cwd=paths.ROOT, capture_output=True,
           text=True, errors="replace", check=False)  # fmt: skip
    mach = machine.detect_machine()
    dest = rawio.blob_path("correctness", mach, profile, f"fuzz-{target}.tar.gz")
    arc = archive(target, corpus, artifacts, dest)
    return {
        "kind": KIND,
        "target": target,
        "argv": argv,
        "exit_code": res.returncode,
        "jobs": cfg["fuzz"]["jobs"],
        "seconds_per_job": seconds_per_job(cfg, profile),
        "cpu_hours": cfg["fuzz"]["jobs"] * seconds_per_job(cfg, profile) / 3600,
        "seed": cfg["fuzz"]["seed"],
        "stats": stats,
        "corpus_files_before_cmin": seeds,
        "corpus_files_after_cmin": count_files(corpus),
        "artifact_files": count_files(artifacts),
        "archive": arc,
    }


def run(profile: str | None = None) -> list[Path]:
    profile = profile or "full"
    cfg = config.load_config(profile)
    targets = cfg["fuzz"]["targets"]
    write_seeds(cfg, targets, FUZZ_DIR / "corpus")
    out = []
    for t in targets:
        payload = run_target(t, cfg, profile)
        out.append(
            rawio.write_raw(
                "correctness",
                payload,
                machine=machine.detect_machine(),
                profile=profile,
                script=SCRIPT,
                environment=env.capture_environment(),
            )
        )
        stats = payload["stats"]
        print(f"{t}: {stats['executed']} execs, {stats['divergences']} divergences -> {out[-1]}")
    return out


def main(argv: list[str]) -> int:
    import os

    cmd = argv[0] if argv else "run"
    if cmd != "run":
        print("usage: cfbench.fuzzing run", file=sys.stderr)
        return 2
    profile = os.environ.get("CFB_PROFILE") or "full"
    run("full" if profile == "full" else "quick")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
