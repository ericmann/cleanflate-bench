"""Run-to-run agreement of a session's two perf runs (SPEC 3.2: within +-5% median or flagged)."""

import sys
from collections import defaultdict

from cfbench import config, perf_report, provenance, stats

FLAG_COLUMNS = [
    "machine",
    "variant",
    "subject",
    "workload",
    "level",
    "framing",
    "mode",
    "median_run1_ns",
    "median_run2_ns",
    "rel_diff",
]
SUMMARY_COLUMNS = [
    "machine",
    "variant",
    "runs",
    "cells",
    "flagged_cells",
    "max_abs_rel_diff",
    "aggregates",
    "flagged_aggregates",
    "verdict",
]
AGGREGATE_COLUMNS = [
    "machine",
    "variant",
    "subject",
    "corpus",
    "level",
    "framing",
    "mode",
    "sum_median_run1_ns",
    "sum_median_run2_ns",
    "rel_diff",
    "flagged",
]
PENDING = "no full perf runs; run make perf on M-A and M-B"


def run_medians(doc: dict) -> dict:
    """{(subject, workload, level, framing, mode): (median_ns, corpus)} for the ok cells of a run."""
    out = {}
    for c in doc["payload"]["cells"]:
        res = c.get("result")
        if c.get("status") == "unsupported" or not res or not res.get("ok"):
            continue
        key = (c["subject"], c["workload"], c["level"], c["framing"], c["mode"])
        out[key] = (stats.median(res["samples_ns"]), c["corpus"])
    return out


def rel_diff(run1_ns: float, run2_ns: float) -> float:
    return (run2_ns - run1_ns) / run1_ns


def aggregate_rows(docs: list[dict], tolerance: float) -> list[dict]:
    """Per-aggregate agreement of a session's first two runs (cells summed as in the summary)."""
    if len(docs) < 2:
        return []
    machine, variant = docs[0]["machine"], docs[0]["payload"]["variant"]
    m1, m2 = run_medians(docs[0]), run_medians(docs[1])
    agg1: dict = defaultdict(float)
    agg2: dict = defaultdict(float)
    for key in sorted(set(m1) & set(m2)):
        subject, _workload, level, framing, mode = key
        corpus = m1[key][1]
        if corpus != "tiny":
            akey = (subject, corpus, level, framing, mode)
            agg1[akey] += m1[key][0]
            agg2[akey] += m2[key][0]
    rows = []
    for (subject, corpus, level, framing, mode), s1 in sorted(agg1.items()):
        d = rel_diff(s1, agg2[(subject, corpus, level, framing, mode)])
        rows.append({"machine": machine, "variant": variant, "subject": subject, "corpus": corpus,
                     "level": level, "framing": framing, "mode": mode, "sum_median_run1_ns": s1,
                     "sum_median_run2_ns": agg2[(subject, corpus, level, framing, mode)],
                     "rel_diff": d, "flagged": "true" if abs(d) > tolerance else "false"})  # fmt: skip
    return rows


def compare_session(docs: list[dict], tolerance: float) -> tuple[list[dict], dict]:
    """Flagged cells and the summary row for one (machine, variant) session."""
    first = docs[0]
    machine, variant = first["machine"], first["payload"]["variant"]
    summary = {
        "machine": machine,
        "variant": variant,
        "runs": len(docs),
        "cells": 0,
        "flagged_cells": 0,
        "max_abs_rel_diff": None,
        "aggregates": 0,
        "flagged_aggregates": 0,
        "verdict": "insufficient runs",
    }
    if len(docs) < 2:
        return [], summary
    m1, m2 = run_medians(docs[0]), run_medians(docs[1])
    flagged = []
    agg1: dict = defaultdict(float)
    agg2: dict = defaultdict(float)
    max_abs = 0.0
    common = sorted(set(m1) & set(m2))
    for key in common:
        d = rel_diff(m1[key][0], m2[key][0])
        max_abs = max(max_abs, abs(d))
        subject, workload, level, framing, mode = key
        if abs(d) > tolerance:
            flagged.append(
                {
                    "machine": machine,
                    "variant": variant,
                    "subject": subject,
                    "workload": workload,
                    "level": level,
                    "framing": framing,
                    "mode": mode,
                    "median_run1_ns": m1[key][0],
                    "median_run2_ns": m2[key][0],
                    "rel_diff": d,
                }
            )
        corpus = m1[key][1]
        if corpus != "tiny":
            akey = (subject, corpus, level, framing, mode)
            agg1[akey] += m1[key][0]
            agg2[akey] += m2[key][0]
    flagged_aggs = sum(1 for k in agg1 if abs(rel_diff(agg1[k], agg2[k])) > tolerance)
    summary.update(
        cells=len(common),
        flagged_cells=len(flagged),
        max_abs_rel_diff=max_abs,
        aggregates=len(agg1),
        flagged_aggregates=flagged_aggs,
        verdict="flagged" if flagged_aggs else "pass",
    )
    return flagged, summary


def derive(cfg: dict | None = None) -> tuple[list[dict], list[dict]]:
    cfg = cfg or config.load_config("full")
    tol = cfg["perf"]["agreement_tolerance"]
    sessions = perf_report.load_sessions()
    script = "cfbench.agreement"
    if not sessions:
        for name, cols in (
            ("perf_agreement", FLAG_COLUMNS),
            ("perf_agreement_summary", SUMMARY_COLUMNS),
            ("perf_agreement_aggregates", AGGREGATE_COLUMNS),
        ):
            provenance.write_table(name, cols, [], script=script, raw_files=[], pending=PENDING)
        return [], []
    flags, summaries, aggs, raw = [], [], [], []
    for docs in sessions.values():
        raw.extend(d["path"] for d in docs)
        f, s = compare_session(docs, tol)
        flags.extend(f)
        summaries.append(s)
        aggs.extend(aggregate_rows(docs, tol))
    provenance.write_table("perf_agreement", FLAG_COLUMNS, flags, script=script, raw_files=raw)
    provenance.write_table(
        "perf_agreement_summary", SUMMARY_COLUMNS, summaries, script=script, raw_files=raw
    )
    provenance.write_table(
        "perf_agreement_aggregates", AGGREGATE_COLUMNS, aggs, script=script, raw_files=raw
    )
    return flags, summaries


def main() -> int:
    _flags, summaries = derive()
    for s in summaries:
        print(f"{s['machine']} {s['variant']}: {s['verdict']} ({s['flagged_cells']} cells flagged)")
    if not summaries:
        print("agreement: pending (no full perf runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
