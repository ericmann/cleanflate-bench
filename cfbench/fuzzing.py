"""Run the differential fuzz targets for a CPU budget and archive their corpora (SPEC 3.6 and 4).

`make fuzz` runs the full budget (a human step). `make fuzz-smoke` runs `fuzz.smoke_seconds` on one
job and writes to the gitignored smoke tree. Each target gets a raw document of kind `fuzz` in
`correctness/<machine>` plus a `<timestamp>-fuzz-<target>.tar.gz` of its minimized corpus and
artifacts, recorded by path and SHA-256.
"""

import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from cfbench import (
    config,
    env,
    machine,
    malformed,
    paths,
    provenance,
    rawio,
    subjects,
    workloads,
)

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


def names(d: Path) -> set[str]:
    return {p.name for p in d.iterdir() if p.is_file()} if d.is_dir() else set()


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
    before = names(artifacts)
    argv = run_argv(target, cfg, profile)
    res = runner(
        argv, cwd=paths.ROOT, capture_output=True, text=True, errors="replace", check=False
    )
    stats = parse_libfuzzer(res.stdout + "\n" + res.stderr)
    new_artifacts = sorted(names(artifacts) - before)
    stats["divergences"] = max(stats["divergences"], len(new_artifacts))
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
        "new_artifacts": new_artifacts,
        "archive": arc,
    }


CF_SRC_MARKER = "/crates/cleanflate/src/"
CF_DEFECTS = ("cf-only-reject", "cf-only-accept", "output-differs")
CLASSES = (*CF_DEFECTS, "normalization-gap", "comparator-bug")
STATS_COLUMNS = ["machine", "target", "budget_cpu_hours", "executions", "exec_per_s", "cov_lines_pct",
                 "cov_regions_pct", "divergences", "archive"]  # fmt: skip
DIVERGENCE_COLUMNS = [
    "machine",
    "target",
    "artifact_sha256",
    "classification",
    "outcomes_by_subject",
]
PENDING = "no full fuzz run; run make fuzz on a quiet machine"
FINDINGS_BEGIN = "<!-- fuzz-findings:begin -->"
FINDINGS_END = "<!-- fuzz-findings:end -->"


def coverage_summary(export: dict, marker: str = CF_SRC_MARKER) -> dict:
    """Line, region and function coverage of the files under cleanflate's source path only."""
    tot = {k: [0, 0] for k in ("lines", "regions", "functions")}
    files = 0
    for data in export["data"]:
        for f in data["files"]:
            if marker not in f["filename"]:
                continue
            files += 1
            for k, v in tot.items():
                v[0] += f["summary"][k]["count"]
                v[1] += f["summary"][k]["covered"]
    pct = {k: (100.0 * c / n if n else None) for k, (n, c) in tot.items()}
    return {"cov_lines_pct": pct["lines"], "cov_regions_pct": pct["regions"],
            "cov_functions_pct": pct["functions"], "files": files,
            "lines": tot["lines"], "regions": tot["regions"], "functions": tot["functions"]}  # fmt: skip


def llvm_cov_path(runner=subprocess.run) -> Path:
    """`llvm-cov` from the nightly toolchain's llvm-tools-preview component."""
    sysroot = runner(["rustc", "+nightly", "--print", "sysroot"], capture_output=True, text=True,
                     check=True).stdout.strip()  # fmt: skip
    verbose = runner(
        ["rustc", "+nightly", "-vV"], capture_output=True, text=True, check=True
    ).stdout
    host = next(ln.split(": ", 1)[1] for ln in verbose.splitlines() if ln.startswith("host: "))
    return Path(sysroot) / "lib" / "rustlib" / host / "bin" / "llvm-cov"


def coverage_binary(target: str) -> Path | None:
    """The newest instrumented binary `cargo fuzz coverage` built for the target."""
    found = []
    for base in (paths.ROOT / "target", FUZZ_DIR / "target"):
        found += base.glob(f"*/coverage/*/release/{target}")
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def run_coverage(target: str, runner=subprocess.run) -> dict | None:
    """cf coverage of the target's corpus; None when the tooling is unavailable."""
    corpus = FUZZ_DIR / "corpus" / target
    res = runner(["cargo", "+nightly", "fuzz", "coverage", target, str(corpus)], cwd=paths.ROOT,
                 capture_output=True, text=True, errors="replace", check=False)  # fmt: skip
    binary = coverage_binary(target)
    profdata = FUZZ_DIR / "coverage" / target / "coverage.profdata"
    if res.returncode != 0 or binary is None or not profdata.exists():
        return None
    out = runner([str(llvm_cov_path(runner)), "export", "-summary-only",
                  f"-instr-profile={profdata}", str(binary)], capture_output=True, text=True,
                 check=True)  # fmt: skip
    summary = coverage_summary(json.loads(out.stdout))
    summary["rustc"] = runner(["rustc", "+nightly", "-V"], capture_output=True, text=True,
                              check=True).stdout.strip()  # fmt: skip
    return summary


def target_framing(target: str, first: int) -> str:
    """The framing the first input byte selects (mod 3, or mod 2 for the mox target)."""
    if target.endswith("_mox"):
        return MOX_FRAMINGS[first % 2]
    return ("raw", "zlib", "gzip")[first % 3]


def key_of(outcome: dict) -> tuple:
    """Comparison key: rejection, or acceptance with the output digest; None when unsupported."""
    if outcome["outcome"] == "unsupported":
        return ()
    return (
        ("accept", outcome.get("sha256"))
        if malformed.is_accept(outcome["outcome"])
        else ("reject",)
    )


def classify(outcomes: dict[str, dict]) -> str:
    """Classify one artifact from the harness outcomes of every subject."""
    cf = outcomes["cf"]
    if cf["outcome"] == "error:TrailingData":
        return "normalization-gap"  # the harness decodes with trailing data allowed
    keys = {s: key_of(o) for s, o in outcomes.items() if key_of(o)}
    if len(set(keys.values())) <= 1:
        return "normalization-gap"  # every subject agrees with the harness API: a fuzz-API effect
    others = [k for s, k in keys.items() if s != "cf"]
    kind = "reject" if keys["cf"] == ("reject",) else "accept"
    if len(set(others)) == 1:
        if kind == "reject":
            return "cf-only-reject"
        return "cf-only-accept" if others[0] == ("reject",) else "output-differs"
    modal = max(set(others), key=others.count)
    if keys["cf"] == modal:
        return "comparator-bug"  # a comparator disagrees with cf and the other comparators
    if kind == "reject":
        return "cf-only-reject"
    return "cf-only-accept" if modal == ("reject",) else "output-differs"


def triage(target: str, artifact: Path, cfg: dict, runner=malformed.run_decode) -> dict:
    """Reproduce one artifact across all subjects with `decode --mode oneshot`."""
    raw = artifact.read_bytes()
    framing = target_framing(target, raw[0] if raw else 0)
    outcomes = {}
    with tempfile.TemporaryDirectory() as tmp:
        stream = Path(tmp) / "stream.bin"
        stream.write_bytes(raw[1:])
        for s in cfg["conformance"]["subjects"]:
            cmd = subjects.command(s)
            info = json.loads(
                subprocess.run([*cmd, "info"], capture_output=True, text=True, check=True).stdout
            )
            if framing not in info["framings"]:
                outcomes[s] = {"outcome": "unsupported"}
                continue
            r = runner(
                [*cmd, "decode", "--framing", framing, "--mode", "oneshot", "--input", str(stream)]
            )
            outcomes[s] = {"outcome": malformed.outcome(r), "sha256": r.get("sha256") if r else None,
                           "produced": r.get("produced") if r else None}  # fmt: skip
    return {"artifact": artifact.name, "artifact_sha256": hashlib.sha256(raw).hexdigest(),
            "framing": framing, "classification": classify(outcomes), "outcomes": outcomes}  # fmt: skip


def analyse_target(
    target: str, payload: dict, cfg: dict, runner=subprocess.run, decoder=malformed.run_decode
) -> dict:
    """Coverage of cf and triage of every new artifact for one finished target run."""
    artifacts = FUZZ_DIR / "artifacts" / target
    return {
        "coverage": run_coverage(target, runner),
        "triage": [triage(target, artifacts / n, cfg, decoder) for n in payload["new_artifacts"]],
    }


def outcomes_text(outcomes: dict[str, dict]) -> str:
    return ";".join(f"{s}={o['outcome']}" for s, o in outcomes.items())


def newest_per_target(docs: list[tuple[Path, dict]]) -> dict[tuple[str, str], tuple[Path, dict]]:
    best: dict[tuple[str, str], tuple[Path, dict]] = {}
    for p, d in docs:
        k = (d["machine"], d["payload"]["target"])
        if k not in best or d["timestamp"] > best[k][1]["timestamp"]:
            best[k] = (p, d)
    return best


def stats_rows(best: dict) -> list[dict]:
    rows = []
    for (m, t), (_p, d) in sorted(best.items()):
        pl = d["payload"]
        cov = pl.get("coverage") or {}
        rows.append({"machine": m, "target": t, "budget_cpu_hours": pl["cpu_hours"],
                     "executions": pl["stats"]["executed"], "exec_per_s": pl["stats"]["exec_per_s"],
                     "cov_lines_pct": cov.get("cov_lines_pct"), "cov_regions_pct": cov.get("cov_regions_pct"),
                     "divergences": pl["stats"]["divergences"], "archive": pl["archive"]["path"]})  # fmt: skip
    return rows


def divergence_rows(best: dict) -> list[dict]:
    rows = []
    for (m, t), (_p, d) in sorted(best.items()):
        for x in d["payload"].get("triage", []):
            rows.append({"machine": m, "target": t, "artifact_sha256": x["artifact_sha256"],
                         "classification": x["classification"],
                         "outcomes_by_subject": outcomes_text(x["outcomes"])})  # fmt: skip
    return rows


def cf_defect_block(rows: list[dict]) -> list[str]:
    bad = [r for r in rows if r["classification"] in CF_DEFECTS]
    if not bad:
        return []
    block = ["## Fuzz divergences classified as cf defects", ""]
    for r in bad:
        block.append(f"- {r['machine']} {r['target']} `{r['artifact_sha256'][:12]}`: {r['classification']} "
                     f"({r['outcomes_by_subject']})")  # fmt: skip
    return block


def report(profile: str = "full") -> None:
    """Derive fuzz_stats and fuzz_divergences from raw documents (full), or print them (quick)."""
    files = rawio.list_raw("correctness", profile=profile, kind=KIND)
    docs = [(p, rawio.load_raw(p)) for p in files]
    best = newest_per_target(docs)
    stats, divs = stats_rows(best), divergence_rows(best)
    if profile != "full":
        print(f"smoke fuzz report ({len(best)} target runs, not written to results/)")
        for r in stats:
            print({k: r[k] for k in ("target", "executions", "cov_lines_pct", "divergences")})
        for r in divs:
            print(
                r["target"],
                r["artifact_sha256"][:12],
                r["classification"],
                r["outcomes_by_subject"],
            )
        return
    raw = [p for p, _d in best.values()]
    pending = None if best else PENDING
    provenance.write_table(
        "fuzz_stats", STATS_COLUMNS, stats, script=SCRIPT, raw_files=raw, pending=pending
    )
    provenance.write_table("fuzz_divergences", DIVERGENCE_COLUMNS, divs, script=SCRIPT, raw_files=raw, pending=pending)  # fmt: skip
    malformed.set_findings_block(cf_defect_block(divs), FINDINGS_BEGIN, FINDINGS_END)


def run(profile: str | None = None) -> list[Path]:
    profile = profile or "full"
    cfg = config.load_config(profile)
    targets = cfg["fuzz"]["targets"]
    write_seeds(cfg, targets, FUZZ_DIR / "corpus")
    out = []
    for t in targets:
        payload = run_target(t, cfg, profile)
        payload.update(analyse_target(t, payload, cfg))
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
    profile = "full" if (os.environ.get("CFB_PROFILE") or "full") == "full" else "quick"
    if cmd == "run":
        run(profile)
    elif cmd == "report":
        report(profile)
    else:
        print("usage: cfbench.fuzzing run|report", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
