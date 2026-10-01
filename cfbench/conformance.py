"""Conformance of every subject over cleanflate's generated corpus and the workloads (SPEC 3.6)."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from cfbench import cleanflate_src, config, env, machine, provenance, rawio, subjects, workloads

SUMMARY_COLUMNS = ["machine", "subject", "streams", "passed", "failed", "unsupported", "pass_rate"]
DISAGREEMENT_COLUMNS = ["machine", "entry", "framing", "subject", "outcome", "error"]
PENDING = "no conformance run; run make conformance"
ORACLE_CMD = [
    "cargo",
    "run",
    "--release",
    "--locked",
    "-q",
    "-p",
    "oracle",
    "--",
    "generate",
    "--tier",
    "full",
]


@dataclass(frozen=True)
class Job:
    id: str
    source: str  # generated or workload
    path: Path
    framing: str
    dictionary: Path | None
    expected_sha256: str
    expected_len: int


class ConformanceError(RuntimeError):
    pass


def generate_corpus(clone: Path | None = None, runner=None) -> None:
    """Generate cleanflate's corpus inside its clone, then insist the clone is still pristine."""
    clone = clone or cleanflate_src.clone_path()
    run = runner or (lambda cmd, cwd: subprocess.run(cmd, cwd=cwd, check=False).returncode)
    rc = run(ORACLE_CMD, clone)
    if rc != 0:
        raise ConformanceError(
            "oracle generate failed (with --locked): blocker, the clone must not be edited"
        )
    problems = cleanflate_src.pristine_check(clone)
    if problems:
        raise ConformanceError(
            "cleanflate clone is not pristine after generate: " + "; ".join(problems)
        )


def manifest_jobs(manifest: dict, clone: Path) -> list[Job]:
    jobs = []
    for e in manifest["entries"]:
        d = e.get("dictionary")
        jobs.append(
            Job(
                id=e["id"],
                source="generated",
                path=clone / "testdata" / "generated" / e["path"],
                framing=e["framing"],
                dictionary=clone / d["input"] if d else None,
                expected_sha256=e["input_sha256"],
                expected_len=e["input_len"],
            )
        )
    return jobs


def workload_jobs(cfg: dict) -> list[Job]:
    jobs = []
    sums: dict[Path, str] = {}
    for w in workloads.list_workloads(cfg):
        if w.orig_path not in sums:
            sums[w.orig_path] = hashlib.sha256(w.orig_path.read_bytes()).hexdigest()
        jobs.append(
            Job(
                id=f"{w.id}/l{w.level}.{w.framing}",
                source="workload",
                path=w.path,
                framing=w.framing,
                dictionary=None,
                expected_sha256=sums[w.orig_path],
                expected_len=w.orig_len,
            )
        )
    return jobs


def all_jobs(cfg: dict | None = None, clone: Path | None = None) -> list[Job]:
    cfg = cfg or config.load_config("full")
    clone = clone or cleanflate_src.clone_path()
    manifest = json.loads((clone / "testdata" / "MANIFEST.json").read_text())
    return manifest_jobs(manifest, clone) + workload_jobs(cfg)


def judge(job: Job, caps: dict, result: dict | None) -> tuple[str, str]:
    """(outcome, error): `unsupported` when the subject lacks the framing or dictionary."""
    if job.framing not in caps["framings"] or (job.dictionary and not caps["dictionary"]):
        return "unsupported", ""
    if result is None:
        return "fail", "no result"
    if not result["ok"]:
        return "fail", f"{result.get('error_kind')}: {result.get('error')}"
    if result["sha256"] != job.expected_sha256 or result["produced"] != job.expected_len:
        return (
            "fail",
            f"output mismatch (produced {result['produced']} bytes, expected {job.expected_len})",
        )
    return "pass", ""


def decode_argv(cmd: list[str], job: Job, in_chunk: int, out_chunk: int) -> list[str]:
    argv = [
        *cmd, "decode", "--framing", job.framing, "--mode", "stream", "--input", str(job.path),
        "--in-chunk", str(in_chunk), "--out-chunk", str(out_chunk),
    ]  # fmt: skip
    if job.dictionary:
        argv += ["--dictionary", str(job.dictionary)]
    return argv


def run_decode(argv: list[str]) -> dict | None:
    out = subprocess.run(argv, capture_output=True, text=True, check=False)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None


def run_all(cfg: dict, jobs: list[Job], runner=run_decode) -> dict:
    perf = cfg["perf"]
    ids = cfg["conformance"]["subjects"]
    cmds = {s: subjects.command(s) for s in ids}
    caps = {}
    for s in ids:
        info = json.loads(
            subprocess.run([*cmds[s], "info"], capture_output=True, text=True, check=True).stdout
        )
        caps[s] = {"framings": info["framings"], "dictionary": info["dictionary"]}
    rows = []
    for job in jobs:
        outcomes, errors = {}, {}
        for s in ids:
            res = None
            if job.framing in caps[s]["framings"] and not (
                job.dictionary and not caps[s]["dictionary"]
            ):
                res = runner(
                    decode_argv(cmds[s], job, perf["large_in_chunk"], perf["large_out_chunk"])
                )
            outcome, err = judge(job, caps[s], res)
            outcomes[s] = outcome
            if err:
                errors[s] = err
        rows.append(
            {
                "id": job.id,
                "source": job.source,
                "framing": job.framing,
                "dictionary": bool(job.dictionary),
                "expected_len": job.expected_len,
                "outcomes": outcomes,
                "errors": errors,
            }
        )
    return {"kind": "conformance", "subjects": ids, "capabilities": caps, "jobs": rows}


def summary_rows(payload: dict, machine_id: str) -> list[dict]:
    rows = []
    for s in payload["subjects"]:
        c = Counter(j["outcomes"][s] for j in payload["jobs"])
        supported = c["pass"] + c["fail"]
        rows.append(
            {
                "machine": machine_id, "subject": s, "streams": len(payload["jobs"]),
                "passed": c["pass"], "failed": c["fail"], "unsupported": c["unsupported"],
                "pass_rate": c["pass"] / supported if supported else None,
            }
        )  # fmt: skip
    return rows


def disagreement_rows(payload: dict, machine_id: str) -> list[dict]:
    """Every failure, plus any subject whose outcome differs from the majority of supported subjects."""
    rows = []
    for j in payload["jobs"]:
        supported = {s: o for s, o in j["outcomes"].items() if o != "unsupported"}
        if not supported:
            continue
        modal = Counter(supported.values()).most_common(1)[0][0]
        for s, o in sorted(supported.items()):
            if o != "pass" or o != modal:
                rows.append(
                    {
                        "machine": machine_id,
                        "entry": j["id"],
                        "framing": j["framing"],
                        "subject": s,
                        "outcome": o,
                        "error": j["errors"].get(s, ""),
                    }
                )
    return rows


def derive() -> None:
    script = "cfbench.conformance"
    files = rawio.list_raw("correctness", kind="conformance")
    if not files:
        for name, cols in (
            ("conformance", SUMMARY_COLUMNS),
            ("conformance_disagreements", DISAGREEMENT_COLUMNS),
        ):
            provenance.write_table(name, cols, [], script=script, raw_files=[], pending=PENDING)
        return
    newest = {}
    for p in files:
        d = rawio.load_raw(p)
        if d["machine"] not in newest or d["timestamp"] > newest[d["machine"]][1]["timestamp"]:
            newest[d["machine"]] = (p, d)
    summary, dis, raw = [], [], []
    for m, (p, d) in sorted(newest.items()):
        raw.append(p)
        summary += summary_rows(d["payload"], m)
        dis += disagreement_rows(d["payload"], m)
    provenance.write_table("conformance", SUMMARY_COLUMNS, summary, script=script, raw_files=raw)
    provenance.write_table(
        "conformance_disagreements", DISAGREEMENT_COLUMNS, dis, script=script, raw_files=raw
    )


def run() -> Path:
    cfg = config.load_config("full")
    generate_corpus()
    payload = run_all(cfg, all_jobs(cfg))
    return rawio.write_raw(
        "correctness",
        payload,
        machine=machine.detect_machine(),
        profile="full",
        script="cfbench.conformance",
        environment=env.capture_environment(),
    )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "run"
    try:
        if cmd == "run":
            print(run())
        if cmd in ("run", "derive"):
            derive()
        elif cmd != "run":
            print("usage: cfbench.conformance [run|derive]", file=sys.stderr)
            return 2
    except ConformanceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
