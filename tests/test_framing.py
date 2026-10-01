import json
import sys
from pathlib import Path

import pytest

from cfbench import config, framing, paths, provenance, rawio, workloads
from cfbench.workloads import Workload

CFG = config.load_config("full")


def agg(machine, subject, framing_, mibs, corpus="silesia", level=6, complete=True):
    return {
        "machine": machine,
        "subject": subject,
        "corpus": corpus,
        "level": level,
        "mode": "oneshot",
        "framing": framing_,
        "agg_mib_s": mibs,
        "complete": complete,
    }


def aggs_for(machine, cf_gzip, nohw_gzip, zlib_gzip):
    """Raw throughput 100 for everyone; the gzip throughput sets each subject's gzip overhead."""
    rows = []
    for subject, gz in (("cf", cf_gzip), ("zlib-nohw", nohw_gzip), ("zlib", zlib_gzip)):
        rows += [
            agg(machine, subject, "raw", 100.0),
            agg(machine, subject, "zlib", 90.0),
            agg(machine, subject, "gzip", gz),
        ]
    return rows


LOCK = {
    "machines": {
        "M-B": {
            "builds": {
                "zlib": {"hw_crc": {"compiled_in": False}},
                "zlib-nohw": {"hw_crc": {"compiled_in": False}},
            }
        },
        "M-A": {
            "builds": {
                "zlib": {"hw_crc": {"compiled_in": True}},
                "zlib-nohw": {"hw_crc": {"compiled_in": False}},
            }
        },
    }
}


def test_overhead_formula():
    # (1/T_framed - 1/T_raw) / (1/T_raw) = T_raw / T_framed - 1
    assert framing.overhead(100.0, 50.0) == pytest.approx(1.0)  # twice the time
    assert framing.overhead(100.0, 80.0) == pytest.approx(0.25)
    assert framing.overhead(100.0, 100.0) == 0.0
    assert framing.overhead(100.0, 125.0) == pytest.approx(-0.2)
    rows = framing.overhead_rows(aggs_for("M-A", 80.0, 80.0, 80.0))
    cf = next(r for r in rows if r["subject"] == "cf")
    assert cf["overhead_gzip"] == pytest.approx(0.25)
    assert cf["overhead_zlib"] == pytest.approx(100 / 90 - 1)
    # an incomplete aggregate or a missing framing is n/a, never zero
    part = framing.overhead_rows(
        [
            agg("M-A", "mox", "raw", 100.0),
            agg("M-A", "mox", "zlib", 90.0),
            agg("M-A", "cf", "raw", 100.0),
            agg("M-A", "cf", "gzip", 50.0, complete=False),
        ]
    )
    mox = next(r for r in part if r["subject"] == "mox")
    assert mox["overhead_gzip"] is None and mox["overhead_zlib"] is not None
    assert next(r for r in part if r["subject"] == "cf")["overhead_gzip"] is None


def test_hypothesis_confirmed_within_tolerance_on_both_machines():
    over = framing.overhead_rows(
        aggs_for("M-A", 80.0, 78.0, 77.0) + aggs_for("M-B", 82.0, 80.0, 80.0)
    )
    rows = framing.hypothesis_rows(over, CFG, LOCK)
    by = {r["machine"]: r for r in rows}
    assert by["ALL"]["verdict"] == "confirmed"
    assert by["M-A"]["verdict"] == "within band" and abs(by["M-A"]["rel_diff"]) < 0.25
    assert by["M-A"]["cf_overhead_gzip"] == pytest.approx(0.25)
    assert by["M-A"]["zlib_nohw_overhead_gzip"] == pytest.approx(100 / 78 - 1)
    both_out = framing.overhead_rows(
        aggs_for("M-A", 40.0, 90.0, 90.0) + aggs_for("M-B", 40.0, 90.0, 90.0)
    )
    assert framing.hypothesis_rows(both_out, CFG, None)[-1]["verdict"] == "refuted"
    split = framing.overhead_rows(
        aggs_for("M-A", 80.0, 80.0, 80.0) + aggs_for("M-B", 40.0, 90.0, 90.0)
    )
    last = framing.hypothesis_rows(split, CFG, None)[-1]
    assert last["machine"] == "ALL" and last["verdict"] == "inconclusive"  # anything else


def test_hypothesis_inconclusive_with_one_machine():
    over = framing.overhead_rows(aggs_for("M-B", 80.0, 80.0, 80.0))
    rows = framing.hypothesis_rows(over, CFG, LOCK)
    assert rows[-1] == {
        "machine": "ALL",
        "corpus": "silesia",
        "level": 6,
        "verdict": "inconclusive",
    }
    assert framing.hypothesis_rows([], CFG, LOCK)[-1]["verdict"] == "inconclusive"  # missing data
    nodata = framing.overhead_rows([agg("M-A", "cf", "raw", 100.0), agg("M-A", "cf", "gzip", 80.0)])
    r = framing.hypothesis_rows(nodata, CFG, None)[0]
    assert r["verdict"] == "no data" and r["rel_diff"] is None  # no zlib-nohw cell


def test_x86_control_identity_is_annotated():
    over = framing.overhead_rows(
        aggs_for("M-A", 80.0, 80.0, 80.0) + aggs_for("M-B", 80.0, 80.0, 80.0)
    )
    by = {r["machine"]: r for r in framing.hypothesis_rows(over, CFG, LOCK)}
    assert "control identical to default on x86_64" in by["M-B"]["verdict"]
    assert "control identical" not in by["M-A"]["verdict"]  # aarch64: hardware CRC really differs
    assert by["ALL"]["verdict"] == "confirmed"  # annotations do not change the band decision
    assert framing.control_identical(LOCK, "M-B") is True
    assert framing.control_identical(LOCK, "M-A") is False
    assert framing.control_identical(None, "M-B") is None
    assert framing.control_identical(LOCK, "M-Z") is None


@pytest.fixture
def env_(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "SMOKE", tmp_path / "smoke")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setenv("CFB_MACHINE", "M-T")
    wls = []
    for fr in ("raw", "zlib", "gzip"):
        d = tmp_path / "w" / "silesia" / "x"
        d.mkdir(parents=True, exist_ok=True)
        (d / "orig").write_bytes(b"y")
        (d / f"l6.{fr}").write_bytes(b"x")
        wls.append(Workload("silesia/x", "silesia", "x", 6, fr, d / "orig", d / f"l6.{fr}", 1, 1))
    monkeypatch.setattr(workloads, "list_workloads", lambda cfg: wls)
    fake = [sys.executable, str(Path(__file__).parent / "fixtures" / "fake_subject.py")]
    monkeypatch.setenv("CFB_SUBJECT_CMD", json.dumps({s: fake for s in CFG["framing"]["subjects"]}))
    return tmp_path


def test_run_and_derive_end_to_end_with_fake_subjects(env_):
    cfg = config.load_config("full")
    cfg["perf"]["min_samples"] = 3
    out = framing.run(cfg, profile="full", session="S")
    assert len(out) == cfg["perf"]["runs"]
    doc = rawio.load_raw(out[0])
    assert doc["category"] == "framing"
    assert doc["payload"]["kind"] == "framing-perf" and doc["payload"]["variant"] == "framing"
    assert set(doc["payload"]["subjects"]) == set(cfg["framing"]["subjects"])
    assert {c["mode"] for c in doc["payload"]["cells"]} == {"oneshot"}
    res = framing.derive(cfg, out_dir=env_ / "figs", lock=LOCK)
    assert {r["subject"] for r in res["overhead"]} == set(cfg["framing"]["subjects"])
    assert all(
        r["overhead_gzip"] == pytest.approx(0.0) for r in res["overhead"]
    )  # identical fake timings
    assert (env_ / "figs" / "framing_decomposition.svg").exists()
    rows, side = provenance.read_table("framing_hypothesis")
    assert "ALL" in [r["machine"] for r in rows] and side["pending"] is None
    assert list(provenance.read_table("framing_overhead")[0][0]) == framing.OVERHEAD_COLUMNS


def test_no_data_is_pending(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(paths, "RAW", tmp_path / "none")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    assert framing.derive(config.load_config("full"), out_dir=tmp_path / "f") == {
        "overhead": [],
        "hypothesis": [],
    }
    assert provenance.read_table("framing_hypothesis")[1]["pending"] == framing.PENDING
    assert not (tmp_path / "f").exists() and "pending" in capsys.readouterr().out
