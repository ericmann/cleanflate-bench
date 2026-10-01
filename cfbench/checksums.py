"""Adler-32 and CRC-32 microbenchmarks (SPEC 3.3), in GiB/s at several buffer sizes."""

import json
import os
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from cfbench import config, env, machine, perf, provenance, rawio, stats, subjects

ALGOS = ["adler32", "crc32"]
CATEGORY = "framing"
KIND = "checksums"
GIB = 1 << 30
COLUMNS = [
    "machine",
    "subject",
    "algo",
    "size",
    "median_gib_s",
    "ci_lo_gib_s",
    "ci_hi_gib_s",
    "status",
]
PENDING = "no checksum run; run make checksums on M-A and M-B"


def gib_per_s(size_bytes: int, ns: float) -> float:
    """Throughput in GiB/s of processing `size_bytes` in `ns` nanoseconds."""
    return size_bytes / ns * 1e9 / GIB


def build_cells(cfg: dict, infos: dict) -> list[dict]:
    """Every (subject, algo, size) cell; unsupported ones carry status `unsupported`."""
    f = cfg["framing"]
    cells = []
    for s in f["checksum_subjects"]:
        if s not in infos:
            continue
        for algo in ALGOS:
            for size in f["checksum_sizes"]:
                cell = {"subject": s, "algo": algo, "size": size}
                if algo not in infos[s]["checksums"]:
                    cell["status"] = "unsupported"
                cells.append(cell)
    return cells


def checksum_argv(cmd: list[str], cell: dict, cfg: dict) -> list[str]:
    p = cfg["perf"]
    return [
        *cmd,
        "checksum",
        "--algo",
        cell["algo"],
        "--size",
        str(cell["size"]),
        "--seed",
        str(cfg["run"]["seed"]),
        "--warmup-ms",
        str(p["warmup_ms"]),
        "--min-samples",
        str(p["min_samples"]),
        "--min-sample-ms",
        str(p["min_sample_ms"]),
    ]


def exec_cell(argv: list[str]) -> dict:
    out = subprocess.run(argv, capture_output=True, text=True, check=False)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {
            "ok": False,
            "error": f"harness failure: exit {out.returncode}: {out.stderr.strip()[:200]}",
        }


def value_mismatches(results: list[dict]) -> list[dict]:
    """Cells whose checksum value differs from the majority for the same algorithm and size."""
    groups: dict[tuple, dict[str, int]] = defaultdict(dict)
    for c in results:
        r = c.get("result")
        if r and r.get("ok") and "value" in r:
            groups[(c["algo"], c["size"])][c["subject"]] = r["value"]
    out = []
    for (algo, size), vals in sorted(groups.items()):
        counts: dict[int, int] = defaultdict(int)
        for v in vals.values():
            counts[v] += 1
        if len(counts) > 1:
            modal = max(sorted(counts), key=lambda v: counts[v])
            out.append(
                {
                    "algo": algo,
                    "size": size,
                    "majority": modal,
                    "differing": sorted(s for s, v in vals.items() if v != modal),
                }
            )
    return out


def run(
    cfg: dict, runner=exec_cell, profile: str | None = None, session: str | None = None
) -> list[Path]:
    profile = profile or os.environ.get("CFB_PROFILE") or "full"
    m = machine.detect_machine()
    f = cfg["framing"]
    cmds = {s: subjects.command(s) for s in f["checksum_subjects"]}
    infos = {s: perf._run_json([*cmds[s], "info"]) for s in f["checksum_subjects"]}
    cells = build_cells(cfg, infos)
    runnable = [c for c in cells if c.get("status") != "unsupported"]
    start_env = env.capture_environment()
    session = session or f"{m}-checksums-{rawio.utc_timestamp()}"
    seed = cfg["run"]["seed"]
    written = []
    for run_index in range(1, cfg["perf"]["runs"] + 1):
        results = []
        for order, cell in enumerate(perf.shuffled(runnable, seed, run_index)):
            res = runner(checksum_argv(cmds[cell["subject"]], cell, cfg))
            results.append({**cell, "order_index": order, "result": res})
        unsupported = [
            {**c, "order_index": None, "result": None} for c in cells if c not in runnable
        ]
        results.sort(key=lambda c: (c["subject"], c["algo"], c["size"]))
        payload = {
            "kind": KIND,
            "seed": seed,
            "subjects": infos,
            "cells": results + unsupported,
            "value_mismatches": value_mismatches(results),
            "preconditions": perf.check_preconditions(start_env, cfg),
            "environment_end": env.capture_end(start_env),
        }
        written.append(
            rawio.write_raw(
                CATEGORY,
                payload,
                machine=m,
                profile=profile,
                script="cfbench.checksums",
                environment=start_env,
                session=session,
                run_index=run_index,
            )
        )
    return written


def derive(cfg: dict | None = None) -> list[dict]:
    """The `checksums` table from the newest session of each machine; pending without data."""
    cfg = cfg or config.load_config("full")
    script = "cfbench.checksums"
    files = rawio.list_raw(CATEGORY, kind=KIND)
    if not files:
        provenance.write_table(
            "checksums", COLUMNS, [], script=script, raw_files=[], pending=PENDING
        )
        return []
    by_machine: dict[str, list] = defaultdict(list)
    for p in files:
        d = rawio.load_raw(p)
        by_machine[d["machine"]].append((p, d))
    rng = random.Random(cfg["run"]["seed"])
    rows, raw = [], []
    for m, items in sorted(by_machine.items()):
        newest = max(items, key=lambda x: (x[1]["timestamp"], x[1]["session"] or ""))[1]["session"]
        docs = sorted(
            (x for x in items if x[1]["session"] == newest), key=lambda x: x[1]["run_index"] or 0
        )
        raw += [p for p, _ in docs]
        pooled: dict[tuple, list[float]] = defaultdict(list)
        status: dict[tuple, str] = {}
        mismatched = {
            (mm["algo"], mm["size"], s)
            for _, d in docs
            for mm in d["payload"]["value_mismatches"]
            for s in mm["differing"]
        }
        for _, d in docs:
            for c in d["payload"]["cells"]:
                key = (c["subject"], c["algo"], c["size"])
                if c.get("status") == "unsupported":
                    status[key] = "unsupported"
                    continue
                r = c["result"]
                if not r.get("ok"):
                    status.setdefault(key, f"error:{r.get('error')}")
                else:
                    pooled[key].extend(r["samples_ns"])
                    status.setdefault(key, "ok")
        for key in sorted(status):
            subject, algo, size = key
            row = {
                "machine": m,
                "subject": subject,
                "algo": algo,
                "size": size,
                "status": status[key],
            }
            if status[key] == "ok":
                if (algo, size, subject) in mismatched:
                    row["status"] = "error:value mismatch"
                s = stats.cell_stats(pooled[key], size, cfg, rng)
                row.update(
                    median_gib_s=gib_per_s(size, s.median_ns),
                    ci_lo_gib_s=gib_per_s(size, s.ci_hi_ns),
                    ci_hi_gib_s=gib_per_s(size, s.ci_lo_ns),
                )
            rows.append(row)
    provenance.write_table("checksums", COLUMNS, rows, script=script, raw_files=raw)
    return rows


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    cfg = config.load_config()
    if cmd == "run":
        try:
            for p in run(cfg):
                print(p)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        derive()
    elif cmd == "derive":
        derive()
    else:
        print("usage: cfbench.checksums run|derive", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
