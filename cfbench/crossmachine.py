"""Cross-machine comparison tables derived from other derived tables (no measurement).

- `crossmachine_gzip_gap`: cf's ratio vs zlib in raw and gzip framing at the paper level, one-shot,
  per machine, variant and corpus, with the gap gzip minus raw and each machine's hardware-CRC
  determination for zlib and the subject from `subjects.lock.json`. zlib is 1.00x in both framings,
  so a negative gap is cf's gzip penalty beyond zlib's.
- `crossmachine_sleep_check`: the last trajectory round's cf ratio against the perf session's cf
  ratio for the same build, corpus, framing, level and mode, with the trajectory session's wall
  span. Agreement within `perf.agreement_tolerance` means an interruption during the trajectory
  stage did not move the ratio by more than run-to-run noise is allowed to.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from cfbench import cleanflate_src, config, paths, provenance, rawio, trajectory

SCRIPT = "cfbench.crossmachine"
GAP_COLUMNS = ["machine", "variant", "subject", "corpus", "level", "mode", "ratio_raw", "ratio_gzip",
               "gap_gzip_minus_raw", "zlib_hw_crc", "zlib_hw_crc_method", "subject_hw_crc"]  # fmt: skip
SLEEP_COLUMNS = ["machine", "corpus", "framing", "level", "mode", "trajectory_round", "trajectory_ratio",
                 "perf_ratio", "rel_diff", "tolerance", "verdict", "session", "session_span_h"]  # fmt: skip
PENDING_PERF = "no perf aggregates: run `make perf` on M-A and M-B"
PENDING_TRAJ = (
    "no trajectory or perf aggregates: run `make trajectory` and `make perf` on M-A and M-B"
)
SUBJECT = {"generic": "cf", "native": "cf@native"}
WITHIN, OUTSIDE = "within tolerance", "outside tolerance"


def _f(s: str) -> float | None:
    return provenance.to_float(s) if s not in (None, "") else None


def hw_crc(lock: dict, machine: str, build: str) -> tuple[str, str]:
    """('yes'/'no'/'unknown'/'not recorded', method) for one build on one machine."""
    b = lock.get("machines", {}).get(machine, {}).get("builds", {}).get(build)
    if b is None:
        return "not recorded", ""
    hw = b.get("hw_crc") or {}
    c = hw.get("compiled_in")
    state = "unknown" if c is None else ("yes" if c else "no")
    if c and hw.get("runtime_dispatch"):
        state += " (runtime dispatch)"
    return state, "+".join(hw.get("method") or [])


def gap_rows(aggs: list[dict], lock: dict, cfg: dict) -> list[dict]:
    p = cfg["paper"]
    level, mode = str(p["figure_level"]), p["figure_mode"]
    index = {(r["machine"], r["variant"], r["subject"], r["corpus"], r["level"], r["framing"], r["mode"]): r
             for r in aggs}  # fmt: skip
    out = []
    for machine in sorted({r["machine"] for r in aggs}):
        for variant, subject in SUBJECT.items():
            for corpus in cfg["perf"]["corpora"]:
                raw = index.get((machine, variant, subject, corpus, level, "raw", mode))
                gz = index.get((machine, variant, subject, corpus, level, "gzip", mode))
                if not raw or not gz:
                    continue
                r_raw, r_gz = _f(raw["ratio_vs_zlib"]), _f(gz["ratio_vs_zlib"])
                zstate, zmethod = hw_crc(lock, machine, "zlib")
                sstate, _ = hw_crc(lock, machine, subject)
                out.append({"machine": machine, "variant": variant, "subject": subject, "corpus": corpus,
                            "level": int(level), "mode": mode, "ratio_raw": r_raw, "ratio_gzip": r_gz,
                            "gap_gzip_minus_raw": None if r_raw is None or r_gz is None else r_gz - r_raw,
                            "zlib_hw_crc": zstate, "zlib_hw_crc_method": zmethod,
                            "subject_hw_crc": sstate})  # fmt: skip
    return out


def session_spans() -> dict[str, tuple[str, float]]:
    """{machine: (session id, hours from the session start to its newest raw file)} for trajectory."""
    newest: dict[str, tuple[str, str]] = {}
    for p in rawio.list_raw(trajectory.CATEGORY, kind=trajectory.KIND):
        d = rawio.load_raw(p)
        if not d.get("session"):
            continue
        m = d["machine"]
        if m not in newest or d["timestamp"] > newest[m][1]:
            newest[m] = (d["session"], d["timestamp"])
    out = {}
    for m, (session, end) in newest.items():
        start = session.rsplit("-", 1)[-1]
        t0 = datetime.strptime(start, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        t1 = datetime.strptime(end, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        out[m] = (session, (t1 - t0).total_seconds() / 3600)
    return out


def sleep_rows(
    traj: list[dict], aggs: list[dict], spans: dict, cfg: dict, last_round: int
) -> list[dict]:
    p = cfg["paper"]
    level, mode, tol = (
        str(p["trajectory_level"]),
        p["trajectory_mode"],
        cfg["perf"]["agreement_tolerance"],
    )
    perf = {(r["machine"], r["corpus"], r["framing"]): r for r in aggs
            if r["variant"] == "generic" and r["subject"] == "cf" and r["level"] == level and r["mode"] == mode}  # fmt: skip
    out = []
    for r in traj:
        if r["round"] != str(last_round) or r["level"] != level or r["mode"] != mode:
            continue
        q = perf.get((r["machine"], r["corpus"], r["framing"]))
        t, pr = _f(r["ratio_vs_zlib"]), _f(q["ratio_vs_zlib"]) if q else None
        if t is None or pr is None:
            continue
        d = (t - pr) / pr
        session, span = spans.get(r["machine"], ("", None))
        out.append({"machine": r["machine"], "corpus": r["corpus"], "framing": r["framing"], "level": int(level),
                    "mode": mode, "trajectory_round": last_round, "trajectory_ratio": t, "perf_ratio": pr,
                    "rel_diff": d, "tolerance": tol, "verdict": WITHIN if abs(d) <= tol else OUTSIDE,
                    "session": session, "session_span_h": span})  # fmt: skip
    return sorted(out, key=lambda x: (x["machine"], x["corpus"], x["framing"]))


def _raw_paths(*sides: dict) -> list[Path]:
    return sorted({paths.ROOT / e["path"] for s in sides for e in s["raw_files"]})


def _lock(lock_path: Path | None = None) -> dict:
    p = lock_path or paths.ROOT / "subjects.lock.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def derive(cfg: dict | None = None, lock_path: Path | None = None) -> None:
    cfg = cfg or config.load_config("full")
    try:
        aggs, aside = provenance.read_table("perf_aggregates")
    except FileNotFoundError:
        aggs, aside = [], {"pending": PENDING_PERF, "raw_files": []}
    if aside.get("pending") or not aggs:
        provenance.write_table("crossmachine_gzip_gap", GAP_COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING_PERF)  # fmt: skip
        provenance.write_table("crossmachine_sleep_check", SLEEP_COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING_TRAJ)  # fmt: skip
        return
    provenance.write_table("crossmachine_gzip_gap", GAP_COLUMNS, gap_rows(aggs, _lock(lock_path), cfg),
                           script=SCRIPT, raw_files=_raw_paths(aside))  # fmt: skip
    try:
        traj, tside = provenance.read_table("trajectory")
    except FileNotFoundError:
        traj, tside = [], {"pending": PENDING_TRAJ, "raw_files": []}
    if tside.get("pending") or not traj:
        provenance.write_table("crossmachine_sleep_check", SLEEP_COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING_TRAJ)  # fmt: skip
        return
    last = max(r["round"] for r in cleanflate_src.rounds()["rounds"])
    rows = sleep_rows(traj, aggs, session_spans(), cfg, last)
    provenance.write_table("crossmachine_sleep_check", SLEEP_COLUMNS, rows, script=SCRIPT,
                           raw_files=_raw_paths(aside, tside))  # fmt: skip


def main() -> int:
    derive()
    print("crossmachine: crossmachine_gzip_gap, crossmachine_sleep_check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
