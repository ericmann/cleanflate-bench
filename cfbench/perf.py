"""Randomised perf orchestrator: one subject process per cell (SPEC 3.1, 3.2)."""

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from cfbench import config, env, machine, rawio, subjects, workloads
from cfbench.subjects import native_label, split_label

MODE_KIND = {"oneshot": "oneshot", "stream_small": "stream", "stream_large": "stream"}


def _chunks(perf: dict, mode: str) -> tuple[int, int]:
    if mode == "stream_small":
        return perf["small_in_chunk"], perf["small_out_chunk"]
    if mode == "stream_large":
        return perf["large_in_chunk"], perf["large_out_chunk"]
    return 0, 0


def session_labels(cfg: dict, variant: str) -> list[str]:
    """Subject labels measured in a variant's session, in table order.

    The native session holds the native Rust subjects (labelled `<id>@native`) plus the generic
    `zlib` build as the same-session baseline.
    """
    perf = cfg["perf"]
    if variant == "native":
        return [native_label(s) for s in perf["native_subjects"]] + ["zlib"]
    return list(perf["subjects"])


def build_cells(cfg: dict, subject_infos: dict, wls: list, variant: str = "generic") -> list[dict]:
    """Every (subject, workload, mode) cell; unsupported ones carry status `unsupported`."""
    perf = cfg["perf"]
    ids = [s for s in session_labels(cfg, variant) if s in subject_infos]
    cells = []
    for sid in ids:
        info = subject_infos[sid]
        for w in wls:
            for mode in perf["modes"]:
                in_chunk, out_chunk = _chunks(perf, mode)
                cell = {
                    "subject": sid,
                    "workload": w.id,
                    "corpus": w.corpus,
                    "level": w.level,
                    "framing": w.framing,
                    "mode": mode,
                    "in_chunk": in_chunk,
                    "out_chunk": out_chunk,
                }
                if w.framing not in info["framings"] or MODE_KIND[mode] not in info["modes"]:
                    cell["status"] = "unsupported"
                cells.append(cell)
    return cells


def shuffled(cells: list[dict], seed: int, run_index: int) -> list[dict]:
    rng = random.Random(seed * 1000 + run_index)
    out = list(cells)
    rng.shuffle(out)
    return out


def check_preconditions(environment: dict, cfg: dict, system: str | None = None) -> list[str]:
    """Warnings about a noisy machine. Never raises."""
    system = system or environment.get("_system")
    warnings = []
    power = environment.get("power") or {}
    if system == "Darwin":
        if power.get("on_ac") is False:
            warnings.append("not on AC power")
        if power.get("low_power_mode") is True:
            warnings.append("low power mode is on")
    else:
        gov = environment.get("governor")
        if gov is not None and gov != "performance":
            warnings.append(f"CPU governor is {gov!r}, not 'performance'")
    load = environment.get("load_avg_start")
    if load and load[0] > cfg["perf"]["max_start_load"]:
        warnings.append(f"start load average {load[0]:.2f} exceeds {cfg['perf']['max_start_load']}")
    return warnings


def _run_json(argv: list[str]) -> dict:
    out = subprocess.run(argv, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)} exited {out.returncode}: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def exec_cell(argv_prefix: list[str], cell_path: Path) -> dict:
    try:
        return _run_json([*argv_prefix, "bench", "--cell", str(cell_path)])
    except (RuntimeError, ValueError) as e:
        return {"ok": False, "error": f"harness failure: {e}", "samples_ns": []}


def _cell_json(cfg: dict, cell: dict, w: "workloads.Workload") -> dict:
    perf = cfg["perf"]
    return {
        "framing": cell["framing"],
        "mode": "oneshot" if cell["mode"] == "oneshot" else "stream",
        "in_chunk": cell["in_chunk"],
        "out_chunk": cell["out_chunk"],
        "input": str(w.path),
        "expected": str(w.orig_path),
        "warmup_ms": perf["warmup_ms"],
        "min_samples": perf["min_samples"],
        "min_sample_ms": perf["min_sample_ms"],
    }


def run(
    cfg: dict,
    subject_ids: list[str],
    variant: str = "generic",
    session: str | None = None,
    profile: str | None = None,
    strict: bool = False,
    build: str = "release",
    runner=exec_cell,
    category: str = "perf",
    kind: str = "perf",
) -> list[Path]:
    profile = profile or os.environ.get("CFB_PROFILE") or "full"
    m = machine.detect_machine()
    if variant == "native":
        wanted = [s for s in subject_ids if s in cfg["perf"]["native_subjects"]]
        labels = [native_label(s) for s in wanted] + ["zlib"]
    else:
        labels = list(subject_ids)
    cmds = {}
    for label in labels:
        base, label_build = split_label(label)
        cmds[label] = subjects.command(base, label_build if variant == "native" else build)
    subject_ids = labels
    infos = {s: _run_json([*cmds[s], "info"]) for s in subject_ids}
    wls = workloads.list_workloads(cfg)
    missing = [str(w.path) for w in wls if not w.path.exists()]
    if missing:
        raise RuntimeError(f"{len(missing)} workload streams are missing: run `make workloads`")
    by_key = {(w.id, w.level, w.framing): w for w in wls}
    cells = build_cells(cfg, infos, wls, variant)
    runnable = [c for c in cells if c.get("status") != "unsupported"]
    start_env = env.capture_environment()
    warnings = check_preconditions(start_env, cfg)
    if warnings and strict:
        raise RuntimeError("preconditions failed: " + "; ".join(warnings))
    session = session or f"{m}-{variant}-{rawio.utc_timestamp()}"
    seed = cfg["run"]["seed"]
    written = []
    for run_index in range(1, cfg["perf"]["runs"] + 1):
        results = []
        with tempfile.TemporaryDirectory() as tmp:
            for order, cell in enumerate(shuffled(runnable, seed, run_index)):
                w = by_key[(cell["workload"], cell["level"], cell["framing"])]
                p = Path(tmp) / "cell.json"
                p.write_text(json.dumps(_cell_json(cfg, cell, w)))
                res = runner(cmds[cell["subject"]], p)
                results.append({**cell, "order_index": order, "result": res})
        unsupported = [
            {**c, "order_index": None, "result": None} for c in cells if c not in runnable
        ]
        results.sort(
            key=lambda c: (c["subject"], c["workload"], c["level"], c["framing"], c["mode"])
        )
        payload = {
            "kind": kind,
            "variant": variant,
            "build": "native" if variant == "native" else build,
            "seed": seed,
            "subjects": infos,
            "cells": results + unsupported,
            "preconditions": warnings,
            "environment_end": env.capture_end(start_env),
        }
        written.append(
            rawio.write_raw(
                category,
                payload,
                machine=m,
                profile=profile,
                script="cfbench.perf",
                environment=start_env,
                session=session,
                run_index=run_index,
            )
        )
    return written


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--subjects", default=None, help="comma-separated ids")
    ap.add_argument("--variant", default="generic", choices=["generic", "native"])
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    cfg = config.load_config()
    default = cfg["perf"]["native_subjects"] if a.variant == "native" else cfg["perf"]["subjects"]
    ids = a.subjects.split(",") if a.subjects else default
    build = "release"
    try:
        for p in run(cfg, ids, variant=a.variant, strict=a.strict, build=build):
            print(p)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
