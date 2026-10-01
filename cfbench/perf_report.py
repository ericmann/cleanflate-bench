"""Derive per-cell performance tables from the latest raw perf session (SPEC 3.2)."""

import random
import sys
from collections import defaultdict

from cfbench import config, provenance, rawio, stats

CELL_COLUMNS = [
    "machine",
    "variant",
    "subject",
    "corpus",
    "workload",
    "level",
    "framing",
    "mode",
    "input_bytes",
    "output_bytes",
    "n_samples",
    "median_mib_s",
    "best_mib_s",
    "ci_lo_mib_s",
    "ci_hi_mib_s",
    "ns_per_byte",
    "peak_heap_bytes",
    "ratio_vs_zlib",
    "status",
]
AGG_COLUMNS = [
    "machine",
    "variant",
    "subject",
    "corpus",
    "level",
    "framing",
    "mode",
    "files",
    "total_output_bytes",
    "sum_median_ns",
    "agg_mib_s",
    "sum_best_ns",
    "agg_best_mib_s",
    "ratio_vs_zlib",
    "complete",
]
TINY_COLUMNS = [
    "machine",
    "variant",
    "subject",
    "workload",
    "prefix_bytes",
    "level",
    "framing",
    "mode",
    "median_ns_per_op",
    "ci_lo_ns",
    "ci_hi_ns",
    "time_ratio_vs_zlib",
]
BASELINE = "zlib"
PENDING_NO_PERF = "no full perf runs; run make perf on M-A and M-B"


def load_sessions(category: str = "perf", kind: str = "perf") -> dict:
    """{(machine, variant): [raw docs of the newest session]} from full-profile raw files."""
    docs = [(p, rawio.load_raw(p)) for p in rawio.list_raw(category, kind=kind)]
    groups: dict = defaultdict(list)
    for p, d in docs:
        if d["session"] is None:
            continue
        groups[(d["machine"], d["payload"]["variant"])].append((p, d))
    out = {}
    for key, items in sorted(groups.items()):
        newest = max(items, key=lambda x: (x[1]["timestamp"], x[1]["session"]))[1]["session"]
        same = [(p, d) for p, d in items if d["session"] == newest]
        same.sort(key=lambda x: x[1]["run_index"] or 0)
        out[key] = [{"path": p, **d} for p, d in same]
    return out


def pooled_cells(session_docs: list[dict]) -> dict:
    """Pool samples of every run: {cell key: {cell fields, samples, ...}}."""
    pooled: dict = {}
    for doc in session_docs:
        for c in doc["payload"]["cells"]:
            key = (c["subject"], c["workload"], c["level"], c["framing"], c["mode"])
            entry = pooled.setdefault(
                key, {"cell": c, "samples": [], "heap": None, "input": None, "output": None}
            )
            res = c.get("result")
            if c.get("status") == "unsupported":
                entry["status"] = "unsupported"
            elif res is None or not res.get("ok"):
                msg = (res or {}).get("error") or "no result"
                entry.setdefault("status", f"error:{msg}")
            else:
                entry["samples"].extend(res["samples_ns"])
                entry["input"], entry["output"] = res["input_bytes"], res["output_bytes"]
                heap = res.get("peak_heap_bytes")
                if heap is not None:
                    entry["heap"] = max(entry["heap"] or 0, heap)
    return pooled


def _write_pending(raw_files: list) -> None:
    for name, cols in (
        ("perf_cells", CELL_COLUMNS),
        ("perf_aggregates", AGG_COLUMNS),
        ("perf_tiny", TINY_COLUMNS),
    ):
        provenance.write_table(
            name,
            cols,
            [],
            script="cfbench.perf_report",
            raw_files=raw_files,
            pending=PENDING_NO_PERF,
        )


def compute_rows(cfg: dict, category: str = "perf", kind: str = "perf") -> tuple[list[dict], list]:
    """Per-cell rows (CSV columns plus hidden `_median_ns`, `_best_ns`, `_ci_*_ns`) and raw files."""
    sessions = load_sessions(category, kind)
    rng = random.Random(cfg["run"]["seed"])
    rows: list[dict] = []
    raw_files: list = []
    for (machine, variant), docs in sessions.items():
        raw_files.extend(d["path"] for d in docs)
        pooled = pooled_cells(docs)
        for key in sorted(pooled):
            e = pooled[key]
            subject, workload, level, framing, mode = key
            row = {
                "machine": machine,
                "variant": variant,
                "subject": subject,
                "corpus": e["cell"]["corpus"],
                "workload": workload,
                "level": level,
                "framing": framing,
                "mode": mode,
                "status": e.get("status", "ok"),
            }
            if row["status"] == "ok":
                s = stats.cell_stats(e["samples"], e["output"], cfg, rng)
                row.update(
                    input_bytes=e["input"],
                    output_bytes=e["output"],
                    n_samples=s.n,
                    median_mib_s=s.median_mib_s,
                    best_mib_s=s.best_mib_s,
                    ci_lo_mib_s=s.ci_lo_mib_s,
                    ci_hi_mib_s=s.ci_hi_mib_s,
                    ns_per_byte=s.ns_per_byte,
                    peak_heap_bytes=e["heap"],
                    _median_ns=s.median_ns,
                    _best_ns=s.best_ns,
                    _ci_lo_ns=s.ci_lo_ns,
                    _ci_hi_ns=s.ci_hi_ns,
                )
            rows.append(row)
    add_ratios(rows)
    return rows, raw_files


def add_ratios(rows: list[dict]) -> None:
    """Fill `ratio_vs_zlib` from the zlib cell with the same like-for-like key."""
    cells = [{**r, "session": r["variant"], "median_mib_s": r.get("median_mib_s")} for r in rows]
    for r, ratio in zip(rows, stats.ratios_vs_baseline(cells, BASELINE), strict=True):
        r["ratio_vs_zlib"] = ratio


def aggregates(rows: list[dict]) -> list[dict]:
    """Per-corpus aggregate: total output bytes over the summed per-file times."""
    groups: dict = defaultdict(list)
    for r in rows:
        if r["corpus"] == "tiny":
            continue
        groups[
            (r["machine"], r["variant"], r["corpus"], r["level"], r["framing"], r["mode"])
        ].append(r)
    out = []
    for (machine, variant, corpus, level, framing, mode), members in sorted(groups.items()):
        expected = {r["workload"] for r in members}
        by_subject: dict = defaultdict(list)
        for r in members:
            by_subject[r["subject"]].append(r)
        agg = {}
        for subject, rs in by_subject.items():
            ok = [r for r in rs if r["status"] == "ok"]
            if not ok:
                continue
            total = sum(r["output_bytes"] for r in ok)
            t_med = sum(r["_median_ns"] for r in ok)
            t_best = sum(r["_best_ns"] for r in ok)
            agg[subject] = {
                "files": {r["workload"] for r in ok},
                "total": total,
                "sum_median_ns": t_med,
                "sum_best_ns": t_best,
                "mib_s": stats.mib_per_s(total, t_med),
                "best_mib_s": stats.mib_per_s(total, t_best),
            }
        base = agg.get(BASELINE)
        for subject, a in sorted(agg.items()):
            ratio = None
            if base and base["files"] == a["files"]:
                ratio = stats.ratio_vs_baseline(a["mib_s"], base["mib_s"])
            out.append(
                {
                    "machine": machine,
                    "variant": variant,
                    "subject": subject,
                    "corpus": corpus,
                    "level": level,
                    "framing": framing,
                    "mode": mode,
                    "files": len(a["files"]),
                    "total_output_bytes": a["total"],
                    "sum_median_ns": a["sum_median_ns"],
                    "agg_mib_s": a["mib_s"],
                    "sum_best_ns": a["sum_best_ns"],
                    "agg_best_mib_s": a["best_mib_s"],
                    "ratio_vs_zlib": ratio,
                    "complete": a["files"] == expected,
                }
            )
    return out


def tiny_rows(rows: list[dict]) -> list[dict]:
    """Setup-cost table for tiny inputs. The ratio is of times: zlib = 1.00, lower is faster."""
    base = {}
    for r in rows:
        if r["corpus"] == "tiny" and r["subject"] == BASELINE and r["status"] == "ok":
            base[
                (r["machine"], r["variant"], r["workload"], r["level"], r["framing"], r["mode"])
            ] = r["_median_ns"]
    out = []
    for r in rows:
        if r["corpus"] != "tiny" or r["status"] != "ok":
            continue
        key = (r["machine"], r["variant"], r["workload"], r["level"], r["framing"], r["mode"])
        ref = base.get(key)
        out.append(
            {
                "machine": r["machine"],
                "variant": r["variant"],
                "subject": r["subject"],
                "workload": r["workload"],
                "prefix_bytes": int(r["workload"].rsplit("-", 1)[1]),
                "level": r["level"],
                "framing": r["framing"],
                "mode": r["mode"],
                "median_ns_per_op": r["_median_ns"],
                "ci_lo_ns": r["_ci_lo_ns"],
                "ci_hi_ns": r["_ci_hi_ns"],
                "time_ratio_vs_zlib": r["_median_ns"] / ref if ref else None,
            }
        )
    return out


def derive_all(cfg: dict | None = None) -> dict:
    """Write perf_cells, perf_aggregates and perf_tiny. Exits cleanly with pending sidecars."""
    cfg = cfg or config.load_config("full")
    rows, raw_files = compute_rows(cfg)
    if not rows:
        _write_pending([])
        return {"perf_cells": [], "perf_aggregates": [], "perf_tiny": []}
    script = "cfbench.perf_report"
    agg, tiny = aggregates(rows), tiny_rows(rows)
    provenance.write_table("perf_cells", CELL_COLUMNS, rows, script=script, raw_files=raw_files)
    provenance.write_table("perf_aggregates", AGG_COLUMNS, agg, script=script, raw_files=raw_files)
    provenance.write_table("perf_tiny", TINY_COLUMNS, tiny, script=script, raw_files=raw_files)
    return {"perf_cells": rows, "perf_aggregates": agg, "perf_tiny": tiny}


def derive_cells(cfg: dict | None = None) -> list[dict]:
    """Write only the per-cell table (all three come from `derive_all`)."""
    return derive_all(cfg)["perf_cells"]


def main() -> int:
    out = derive_all()
    print(", ".join(f"{k}: {len(v)} rows" for k, v in out.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
