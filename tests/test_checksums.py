import json
import sys
from pathlib import Path

import pytest

from cfbench import checksums as ck
from cfbench import config, paths, provenance, rawio

FAKE_INFO = {"checksums": ["adler32", "crc32"], "framings": ["raw"], "modes": ["oneshot"]}
CFG = config.load_config("full")


def infos(**kw):
    return {
        "cf": FAKE_INFO,
        "mox": {**FAKE_INFO, "checksums": ["adler32"]},  # no crc32
        "zlib": FAKE_INFO,
        **kw,
    }


def small_cfg():
    cfg = config.load_config("full")
    cfg["framing"]["checksum_subjects"] = ["cf", "mox", "zlib"]
    cfg["framing"]["checksum_sizes"] = [64, 4096]
    cfg["perf"]["min_samples"] = 3
    return cfg


def test_cells_cover_algo_by_size_and_mark_unsupported():
    cfg = small_cfg()
    cells = ck.build_cells(cfg, infos())
    assert len(cells) == 3 * 2 * 2
    assert {(c["algo"], c["size"]) for c in cells} == {(a, s) for a in ck.ALGOS for s in (64, 4096)}
    unsupported = [c for c in cells if c.get("status") == "unsupported"]
    assert {(c["subject"], c["algo"]) for c in unsupported} == {("mox", "crc32")}
    assert len(unsupported) == 2  # one per size
    # the configured subjects are the full list from SPEC 3.3, including the hw-CRC control
    assert CFG["framing"]["checksum_subjects"] == [
        "cf",
        "zlib",
        "zlib-nohw",
        "zng",
        "zrs",
        "mox",
        "zsys",
    ]
    assert CFG["framing"]["checksum_sizes"] == [64, 4096, 65536, 1048576]
    argv = ck.checksum_argv(["bin"], {"algo": "crc32", "size": 64}, cfg)
    assert argv[:2] == ["bin", "checksum"] and argv[argv.index("--seed") + 1] == str(
        cfg["run"]["seed"]
    )
    assert argv[argv.index("--min-samples") + 1] == "3"


def test_value_mismatch_is_recorded():
    def res(value):
        return {"ok": True, "value": value, "samples_ns": [1.0]}

    results = [
        {"subject": "cf", "algo": "crc32", "size": 64, "result": res(7)},
        {"subject": "zlib", "algo": "crc32", "size": 64, "result": res(7)},
        {"subject": "zng", "algo": "crc32", "size": 64, "result": res(9)},
        {"subject": "cf", "algo": "adler32", "size": 64, "result": res(1)},
        {"subject": "zlib", "algo": "adler32", "size": 64, "result": res(1)},
        {"subject": "bad", "algo": "adler32", "size": 64, "result": {"ok": False, "error": "x"}},
    ]
    assert ck.value_mismatches(results) == [
        {"algo": "crc32", "size": 64, "majority": 7, "differing": ["zng"]}
    ]
    assert ck.value_mismatches(results[:2]) == []


def test_gib_per_s_conversion():
    assert ck.gib_per_s(1 << 30, 1e9) == pytest.approx(1.0)  # 1 GiB in 1 s
    assert ck.gib_per_s(1 << 20, 1e6) == pytest.approx(1000 / 1024)  # 1 MiB in 1 ms
    assert ck.gib_per_s(4096, 100.0) == pytest.approx(4096 / 100.0 * 1e9 / (1 << 30))


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "SMOKE", tmp_path / "smoke")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setenv("CFB_MACHINE", "M-T")
    fake = Path(__file__).parent / "fixtures" / "fake_subject.py"
    monkeypatch.setenv(
        "CFB_SUBJECT_CMD",
        json.dumps({s: [sys.executable, str(fake)] for s in ("cf", "mox", "zlib")}),
    )
    return tmp_path


def fake_runner(values):
    def runner(argv):
        algo = argv[argv.index("--algo") + 1]
        size = int(argv[argv.index("--size") + 1])
        return {"ok": True, "algo": algo, "size": size, "value": values.get((algo, size), 5),
                "samples_ns": [1000.0 + i for i in range(3)]}  # fmt: skip

    return runner


def test_run_derive_pools_runs(raw, monkeypatch):
    cfg = small_cfg()

    monkeypatch.setattr(ck.perf, "_run_json", lambda argv: FAKE_INFO)
    out = ck.run(cfg, runner=fake_runner({}), profile="full", session="S")
    assert len(out) == cfg["perf"]["runs"]
    docs = [rawio.load_raw(p) for p in out]
    assert {d["session"] for d in docs} == {"S"} and docs[0]["category"] == "framing"
    assert (
        docs[0]["payload"]["kind"] == "checksums" and docs[0]["payload"]["value_mismatches"] == []
    )
    rows = ck.derive(cfg)
    ok = [r for r in rows if r["status"] == "ok"]
    assert ok and all(
        r["median_gib_s"] > 0 and r["ci_lo_gib_s"] <= r["median_gib_s"] <= r["ci_hi_gib_s"]
        for r in ok
    )
    side = provenance.read_table("checksums")[1]
    assert side["pending"] is None and len(side["raw_files"]) == cfg["perf"]["runs"]


def test_derive_marks_value_mismatch_and_pending(raw):
    ck.derive(config.load_config("full"))
    assert provenance.read_table("checksums")[1]["pending"] == ck.PENDING
    cell = lambda s, a, v: {
        "subject": s,
        "algo": a,
        "size": 64,
        "order_index": 0,
        "result": {"ok": True, "value": v, "samples_ns": [100.0, 110.0, 120.0]},
    }
    payload = {"kind": "checksums", "cells": [cell("cf", "crc32", 1), cell("zlib", "crc32", 2),
               cell("mox", "crc32", 2), {"subject": "mox", "algo": "adler32", "size": 64, "status": "unsupported",
                                          "order_index": None, "result": None}],
               "value_mismatches": [{"algo": "crc32", "size": 64, "majority": 2, "differing": ["cf"]}],
               "subjects": {}, "preconditions": [], "environment_end": {}}  # fmt: skip
    rawio.write_raw(
        "framing",
        payload,
        machine="M-T",
        profile="full",
        script="t",
        environment=None,
        session="s",
        run_index=1,
    )
    rows = {(r["subject"], r["algo"]): r for r in ck.derive(config.load_config("full"))}
    assert rows[("cf", "crc32")]["status"] == "error:value mismatch"
    assert (
        rows[("zlib", "crc32")]["status"] == "ok"
        and rows[("mox", "adler32")]["status"] == "unsupported"
    )
    assert rows[("mox", "adler32")].get("median_gib_s") is None  # n/a, never zero
