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
    "status",
]
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


def derive_cells(cfg: dict | None = None) -> list[dict]:
    cfg = cfg or config.load_config("full")
    sessions = load_sessions()
    if not sessions:
        provenance.write_table(
            "perf_cells",
            CELL_COLUMNS,
            [],
            script="cfbench.perf_report",
            raw_files=[],
            pending=PENDING_NO_PERF,
        )
        return []
    rng = random.Random(cfg["run"]["seed"])
    rows = []
    raw_files = []
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
                )
            rows.append(row)
    provenance.write_table(
        "perf_cells", CELL_COLUMNS, rows, script="cfbench.perf_report", raw_files=raw_files
    )
    return rows


def main() -> int:
    rows = derive_cells()
    print(f"perf_cells: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
