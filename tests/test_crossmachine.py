import json

import pytest

from cfbench import config, crossmachine, paths, provenance, rawio
from cfbench.kits import pipeline

CFG = config.load_config("full")
LOCK = {"machines": {
    "M-A": {"builds": {"zlib": {"hw_crc": {"compiled_in": True, "runtime_dispatch": False, "method": ["disassembly"]}},
                       "cf": {"hw_crc": {"compiled_in": False}}}},
    "M-B": {"builds": {"zlib": {"hw_crc": {"compiled_in": False, "method": ["disassembly", "symbols"]}},
                       "zng": {"hw_crc": {"compiled_in": True, "runtime_dispatch": True}},
                       "zsys": {"hw_crc": {"compiled_in": None}}}},
}}  # fmt: skip


def agg(
    machine,
    framing,
    ratio,
    variant="generic",
    subject="cf",
    corpus="silesia",
    level="6",
    mode="oneshot",
):
    return {"machine": machine, "variant": variant, "subject": subject, "corpus": corpus, "level": level,
            "framing": framing, "mode": mode, "ratio_vs_zlib": str(ratio)}  # fmt: skip


def test_hw_crc_states():
    assert crossmachine.hw_crc(LOCK, "M-A", "zlib") == ("yes", "disassembly")
    assert crossmachine.hw_crc(LOCK, "M-B", "zlib") == ("no", "disassembly+symbols")
    assert crossmachine.hw_crc(LOCK, "M-B", "zng")[0] == "yes (runtime dispatch)"
    assert crossmachine.hw_crc(LOCK, "M-B", "zsys")[0] == "unknown"
    assert crossmachine.hw_crc(LOCK, "M-A", "cf@native") == ("not recorded", "")


def test_gap_rows_pair_raw_and_gzip_per_machine():
    aggs = [agg("M-A", "raw", 0.7), agg("M-A", "gzip", 0.6), agg("M-B", "raw", 0.8), agg("M-B", "gzip", 0.78),
            agg("M-B", "raw", 0.5, corpus="canterbury")]  # canterbury has no gzip row: skipped  # fmt: skip
    rows = {r["machine"]: r for r in crossmachine.gap_rows(aggs, LOCK, CFG)}
    assert set(rows) == {"M-A", "M-B"}
    assert (
        rows["M-A"]["gap_gzip_minus_raw"] == pytest.approx(-0.1)
        and rows["M-A"]["zlib_hw_crc"] == "yes"
    )
    assert (
        rows["M-B"]["gap_gzip_minus_raw"] == pytest.approx(-0.02)
        and rows["M-B"]["zlib_hw_crc"] == "no"
    )
    assert (
        rows["M-A"]["subject_hw_crc"] == "no"
        and rows["M-A"]["level"] == CFG["paper"]["figure_level"]
    )


def test_sleep_rows_compare_last_round_with_perf():
    traj = [{"machine": "M-A", "round": "3", "corpus": "silesia", "framing": "raw", "level": "6", "mode": "oneshot",
             "ratio_vs_zlib": "0.72"},
            {"machine": "M-A", "round": "2", "corpus": "silesia", "framing": "raw", "level": "6", "mode": "oneshot",
             "ratio_vs_zlib": "0.69"},
            {"machine": "M-B", "round": "3", "corpus": "silesia", "framing": "raw", "level": "6", "mode": "oneshot",
             "ratio_vs_zlib": "0.60"}]  # fmt: skip
    aggs = [agg("M-A", "raw", 0.71), agg("M-B", "raw", 0.75)]
    spans = {"M-A": ("M-A-rounds-x", 11.0)}
    rows = {r["machine"]: r for r in crossmachine.sleep_rows(traj, aggs, spans, CFG, 3)}
    tol = CFG["perf"]["agreement_tolerance"]
    assert rows["M-A"]["verdict"] == crossmachine.WITHIN and rows["M-A"]["tolerance"] == tol
    assert (
        rows["M-A"]["rel_diff"] == pytest.approx(0.01 / 0.71)
        and rows["M-A"]["session_span_h"] == 11.0
    )
    assert rows["M-B"]["verdict"] == crossmachine.OUTSIDE and rows["M-B"]["session_span_h"] is None


def test_session_spans_from_raw_session_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(rawio, "utc_timestamp", lambda: "20261003T164704Z")
    rawio.write_raw("trajectory", {"kind": "trajectory", "cells": [], "variant": "generic"}, machine="M-A",
                    profile="full", script="t", environment=None, session="M-A-rounds-20261003T054806Z")  # fmt: skip
    session, hours = crossmachine.session_spans()["M-A"]
    assert session == "M-A-rounds-20261003T054806Z"
    assert hours == pytest.approx((16 * 3600 + 47 * 60 + 4 - (5 * 3600 + 48 * 60 + 6)) / 3600)


def test_derive_pending_without_perf(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps(LOCK))
    crossmachine.derive(CFG, lock_path=lock)
    for t in ("crossmachine_gzip_gap", "crossmachine_sleep_check"):
        rows, side = provenance.read_table(t)
        assert rows == [] and side["pending"]


def test_session_notes_and_not_run_reasons():
    ids = [n.id for n in pipeline.notes()]
    assert ids == [
        "m-a-high-power",
        "m-a-sleep",
        "m-a-fixtures",
        "m-b-background-load",
        "fuzz-throttling",
    ]
    assert pipeline.note_text("m-a-sleep").startswith(
        "Operator note (`config/session_notes.toml`, `m-a-sleep`): "
    )
    assert pipeline.note_text("missing") == ""
    assert "fuzz budget" in pipeline.not_run_reason("M-A", "fuzz_stats")
    assert pipeline.not_run_reason("M-B", "fuzz_stats") is None
    assert pipeline.PIPELINE_NAME in pipeline.thesis()
