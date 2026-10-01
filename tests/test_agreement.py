from pathlib import Path

import pytest

from cfbench import agreement, config, paths, provenance

FIX_RAW = Path(__file__).parent / "fixtures" / "raw"
TOL = 0.05


def cell(subject, workload, ns, corpus="silesia", mode="oneshot"):
    return {
        "subject": subject, "workload": workload, "corpus": corpus, "level": 6,
        "framing": "raw", "mode": mode,
        "result": {"ok": True, "samples_ns": [ns] * 5, "output_bytes": 1, "input_bytes": 1},
    }  # fmt: skip


def doc(run_index, cells, machine="M-T", variant="generic"):
    return {
        "machine": machine, "session": "s", "run_index": run_index,
        "payload": {"variant": variant, "cells": cells},
    }  # fmt: skip


def test_within_tolerance_passes():
    d1 = doc(1, [cell("cf", "silesia/a", 1000.0), cell("zlib", "silesia/a", 500.0)])
    d2 = doc(2, [cell("cf", "silesia/a", 1040.0), cell("zlib", "silesia/a", 480.0)])
    flagged, s = agreement.compare_session([d1, d2], TOL)
    assert flagged == []
    assert s["verdict"] == "pass" and s["cells"] == 2 and s["flagged_cells"] == 0
    assert s["max_abs_rel_diff"] == pytest.approx(0.04)
    assert s["runs"] == 2 and s["aggregates"] == 2


def test_cell_over_tolerance_is_flagged_not_dropped():
    # one noisy file out of two: the cell is flagged but the aggregate still agrees
    d1 = doc(1, [cell("cf", "silesia/a", 1000.0), cell("cf", "silesia/b", 100000.0)])
    d2 = doc(2, [cell("cf", "silesia/a", 1200.0), cell("cf", "silesia/b", 100000.0)])
    flagged, s = agreement.compare_session([d1, d2], TOL)
    assert [f["workload"] for f in flagged] == ["silesia/a"]
    assert flagged[0]["rel_diff"] == pytest.approx(0.2)
    assert flagged[0]["median_run1_ns"] == 1000.0 and flagged[0]["median_run2_ns"] == 1200.0
    assert s["cells"] == 2 and s["flagged_cells"] == 1
    assert s["verdict"] == "pass" and s["flagged_aggregates"] == 0
    # a large move flags the aggregate and the verdict
    d3 = doc(2, [cell("cf", "silesia/a", 1000.0), cell("cf", "silesia/b", 120000.0)])
    _, s2 = agreement.compare_session([d1, d3], TOL)
    assert s2["verdict"] == "flagged" and s2["flagged_aggregates"] == 1


def test_single_run_session_is_insufficient():
    flagged, s = agreement.compare_session([doc(1, [cell("cf", "silesia/a", 1.0)])], TOL)
    assert flagged == []
    assert s["verdict"] == "insufficient runs" and s["runs"] == 1


def test_tiny_cells_and_unsupported_are_handled():
    unsupported = {"subject": "mox", "workload": "silesia/a", "corpus": "silesia", "level": 6,
                   "framing": "gzip", "mode": "oneshot", "status": "unsupported", "result": None}  # fmt: skip
    d1 = doc(1, [cell("cf", "tiny/x-64", 100.0, corpus="tiny"), unsupported])
    d2 = doc(2, [cell("cf", "tiny/x-64", 200.0, corpus="tiny"), unsupported])
    flagged, s = agreement.compare_session([d1, d2], TOL)
    assert len(flagged) == 1 and s["cells"] == 1
    assert s["aggregates"] == 0 and s["verdict"] == "pass"  # tiny is not aggregated


def test_derive_from_fixtures_and_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "RAW", FIX_RAW)
    flags, summaries = agreement.derive(config.load_config("full"))
    by = {(s["machine"], s["variant"]): s for s in summaries}
    assert by[("M-T", "generic")]["runs"] == 2 and by[("M-T", "generic")]["verdict"] == "pass"
    assert by[("M-T", "native")]["verdict"] == "insufficient runs"
    assert flags == []
    assert provenance.read_table("perf_agreement_summary")[1]["pending"] is None
    monkeypatch.setattr(paths, "RAW", tmp_path / "empty")
    agreement.derive(config.load_config("full"))
    rows, side = provenance.read_table("perf_agreement_summary")
    assert rows == [] and side["pending"] == agreement.PENDING
