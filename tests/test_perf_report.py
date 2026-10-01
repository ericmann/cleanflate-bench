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


def row(subject, workload, out_bytes, ns, *, corpus="silesia", level=6, framing="raw",
        mode="oneshot", status="ok", machine="M-T", variant="generic"):  # fmt: skip
    r = {
        "machine": machine, "variant": variant, "subject": subject, "corpus": corpus,
        "workload": workload, "level": level, "framing": framing, "mode": mode, "status": status,
    }  # fmt: skip
    if status == "ok":
        r.update(
            output_bytes=out_bytes,
            median_mib_s=out_bytes / (ns / 1e9) / (1 << 20),
            _median_ns=ns,
            _best_ns=ns * 0.9,
            _ci_lo_ns=ns * 0.95,
            _ci_hi_ns=ns * 1.05,
        )
    return r


def test_aggregate_is_total_bytes_over_summed_time():
    mib = 1 << 20
    rows = [
        row("zlib", "silesia/a", mib, 1e9),  # 1 MiB in 1 s
        row("zlib", "silesia/b", 9 * mib, 1e9),  # 9 MiB in 1 s
        row("cf", "silesia/a", mib, 2e9),
        row("cf", "silesia/b", 9 * mib, 1e9),
    ]
    perf_report.add_ratios(rows)
    agg = {a["subject"]: a for a in perf_report.aggregates(rows)}
    # total bytes / summed time, not the mean of per-file rates (which would be 5 MiB/s)
    assert agg["zlib"]["agg_mib_s"] == pytest.approx(10 / 2)
    assert agg["zlib"]["sum_median_ns"] == 2e9
    assert agg["zlib"]["total_output_bytes"] == 10 * mib
    assert agg["cf"]["agg_mib_s"] == pytest.approx(10 / 3)
    assert agg["cf"]["ratio_vs_zlib"] == pytest.approx((10 / 3) / 5)
    assert agg["zlib"]["ratio_vs_zlib"] == pytest.approx(1.0)
    assert agg["cf"]["agg_best_mib_s"] == pytest.approx(10 / (2.7))
    assert agg["cf"]["complete"] is True and agg["cf"]["files"] == 2


def test_ratio_never_crosses_modes():
    mib = 1 << 20
    rows = [
        row("zlib", "silesia/a", mib, 1e9, mode="oneshot"),
        row("cf", "silesia/a", mib, 1e9, mode="oneshot"),
        row("cf", "silesia/a", mib, 1e9, mode="stream_small"),  # zlib has no stream_small cell
    ]
    perf_report.add_ratios(rows)
    by_mode = {(r["subject"], r["mode"]): r["ratio_vs_zlib"] for r in rows}
    assert by_mode[("cf", "oneshot")] == pytest.approx(1.0)
    assert by_mode[("cf", "stream_small")] is None
    agg = {(a["subject"], a["mode"]): a["ratio_vs_zlib"] for a in perf_report.aggregates(rows)}
    assert agg[("cf", "stream_small")] is None
    assert agg[("cf", "oneshot")] == pytest.approx(1.0)


def test_incomplete_corpus_is_flagged():
    mib = 1 << 20
    rows = [
        row("zlib", "silesia/a", mib, 1e9),
        row("zlib", "silesia/b", mib, 1e9),
        row("cf", "silesia/a", mib, 1e9),
        row("cf", "silesia/b", 0, 0, status="error:output mismatch"),
        row("mox", "silesia/a", 0, 0, status="unsupported"),
        row("mox", "silesia/b", 0, 0, status="unsupported"),
    ]
    perf_report.add_ratios(rows)
    agg = {a["subject"]: a for a in perf_report.aggregates(rows)}
    assert agg["cf"]["complete"] is False and agg["cf"]["files"] == 1
    assert agg["cf"]["agg_mib_s"] == pytest.approx(1.0)  # computed over the files present
    assert agg["cf"]["ratio_vs_zlib"] is None  # different file set from the baseline
    assert agg["zlib"]["complete"] is True
    assert "mox" not in agg  # unsupported is n/a, not an aggregate


def test_tiny_table_reports_time_ratio():
    rows = [
        row("zlib", "tiny/canterbury-alice29.txt-256", 256, 2000.0, corpus="tiny"),
        row("cf", "tiny/canterbury-alice29.txt-256", 256, 1000.0, corpus="tiny"),
        row("zlib", "silesia/a", 1 << 20, 1e9),
    ]
    tiny = {t["subject"]: t for t in perf_report.tiny_rows(rows)}
    assert set(tiny) == {"zlib", "cf"}  # corpus rows are excluded
    assert tiny["zlib"]["time_ratio_vs_zlib"] == pytest.approx(1.0)
    assert tiny["cf"]["time_ratio_vs_zlib"] == pytest.approx(0.5)  # a time ratio: lower is faster
    assert tiny["cf"]["prefix_bytes"] == 256
    assert tiny["cf"]["median_ns_per_op"] == 1000.0
    assert tiny["cf"]["ci_lo_ns"] < 1000.0 < tiny["cf"]["ci_hi_ns"]
    assert perf_report.aggregates(rows[:2]) == []


def test_all_three_tables_written_from_fixtures(setup):
    out = perf_report.derive_all(config.load_config("full"))
    assert set(out) == {"perf_cells", "perf_aggregates", "perf_tiny"}
    for name in out:
        assert (paths.RESULTS / f"{name}.csv").exists()
        assert provenance.read_table(name)[1]["pending"] is None
    cells = rows_by_key(out["perf_cells"])
    assert cells[("generic", "zlib")]["ratio_vs_zlib"] == pytest.approx(1.0)
    assert cells[("generic", "cf")]["ratio_vs_zlib"] == pytest.approx(0.5, rel=0.05)
    assert cells[("native", "zlib")]["ratio_vs_zlib"] == pytest.approx(1.0)


def test_no_data_writes_pending_for_all_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "RAW", tmp_path / "empty")
    perf_report.derive_all(config.load_config("full"))
    for name in ("perf_cells", "perf_aggregates", "perf_tiny"):
        rows, side = provenance.read_table(name)
        assert rows == [] and side["pending"] == perf_report.PENDING_NO_PERF
