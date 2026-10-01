from pathlib import Path

import pytest

from cfbench import config, paths, perf_report, provenance

FIX_RAW = Path(__file__).parent / "fixtures" / "raw"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "RAW", FIX_RAW)


def rows_by_key(rows):
    return {(r["variant"], r["subject"]): r for r in rows}


def test_samples_are_pooled_across_runs_of_a_session(setup):
    rows = perf_report.derive_cells(config.load_config("full"))
    r = rows_by_key(rows)[("generic", "cf")]
    assert r["n_samples"] == 10  # 5 samples x 2 runs of the newest session
    assert r["status"] == "ok" and r["machine"] == "M-T"
    assert r["output_bytes"] == 1048576
    assert r["ci_lo_mib_s"] <= r["median_mib_s"] <= r["ci_hi_mib_s"]
    assert r["peak_heap_bytes"] == 1000
    assert rows_by_key(rows)[("generic", "mox")]["status"] == "unsupported"
    assert rows_by_key(rows)[("generic", "mox")].get("median_mib_s") is None
    assert rows_by_key(rows)[("generic", "zrs")]["status"] == "error:output mismatch"


def test_older_sessions_are_ignored(setup):
    rows = perf_report.derive_cells(config.load_config("full"))
    cf = rows_by_key(rows)[("generic", "cf")]
    # newest session: ~1.0 ms for 1 MiB (about 1000 MiB/s); the old one was 10x slower
    assert 900 < cf["median_mib_s"] < 1000
    sidecar = provenance.read_table("perf_cells")[1]
    used = [e["path"].rsplit("/", 1)[-1] for e in sidecar["raw_files"]]
    assert "20260101T000000Z.json" not in used and "20260102T000000Z.json" in used


def test_variants_are_separate_sessions(setup):
    rows = perf_report.derive_cells(config.load_config("full"))
    assert {r["variant"] for r in rows} == {"generic", "native"}
    native = rows_by_key(rows)[("native", "cf")]
    assert native["n_samples"] == 5


def test_output_is_byte_identical_on_rederive(setup):
    cfg = config.load_config("full")
    perf_report.derive_cells(cfg)
    a = (paths.RESULTS / "perf_cells.csv").read_bytes()
    perf_report.derive_cells(cfg)
    assert a == (paths.RESULTS / "perf_cells.csv").read_bytes()


def test_no_data_writes_pending_sidecar(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "RAW", tmp_path / "empty")
    assert perf_report.derive_cells(config.load_config("full")) == []
    rows, side = provenance.read_table("perf_cells")
    assert rows == []
    assert side["pending"] == "no full perf runs; run make perf on M-A and M-B"
    header = (paths.RESULTS / "perf_cells.csv").read_text().strip()
    assert header == ",".join(perf_report.CELL_COLUMNS)
