import pytest

from cfbench import more_charts, paths, provenance


def put(name, columns, rows, pending=None):
    provenance.write_table(name, columns, rows, script="t", raw_files=[], pending=pending)


UNSAFE = ["subject", "crate", "version", "role", "forbid_unsafe_code", "unsafe_blocks", "unsafe_fns",
          "unsafe_impls", "unsafe_traits", "target_feature_attrs", "geiger_used", "geiger_unused", "note"]  # fmt: skip
STAGE = ["round", "stage", "wall_clock_s", "models", "input_tokens", "output_tokens",
         "cache_write_tokens", "cache_read_tokens", "cost_usd"]  # fmt: skip


def fixtures():
    base = dict.fromkeys(UNSAFE, "")
    put("unsafe", UNSAFE, [
        {**base, "subject": "cf", "crate": "cleanflate", "role": "subject", "unsafe_blocks": 0, "unsafe_fns": 0},
        {**base, "subject": "zrs", "crate": "zlib-rs", "role": "subject", "unsafe_blocks": 120, "unsafe_fns": 30},
        {**base, "subject": "zrs", "crate": "libz-rs-sys", "role": "subject", "unsafe_blocks": 5, "unsafe_fns": 1},
        {**base, "subject": "zlib", "crate": "zlib", "role": "subject", "note": "C: entire codebase memory-unsafe by language"},
    ])  # fmt: skip
    put("binary_size", ["machine", "subject", "opt", "bytes", "note"], [
        {"machine": "M-B", "subject": s, "opt": o, "bytes": b, "note": ""}
        for s, o, b in [("cf", "3", 393888), ("cf", "s", 373408), ("zlib", "3", 43136), ("zlib", "s", 34944)]
    ] + [{"machine": "M-B", "subject": "zsys", "opt": "3", "bytes": "", "note": "dynamic"}])  # fmt: skip
    put("effort_stage_round", STAGE, [
        {"round": 1, "stage": "implement", "input_tokens": 100, "output_tokens": 2000, "cache_write_tokens": 5000, "cost_usd": ""},
        {"round": 1, "stage": "plan", "input_tokens": 10, "output_tokens": 900, "cache_write_tokens": 700, "cost_usd": ""},
        {"round": 2, "stage": "implement", "input_tokens": 50, "output_tokens": 800, "cache_write_tokens": 9000, "cost_usd": ""},
        {"round": 2, "stage": "untagged", "input_tokens": "", "output_tokens": "", "cache_write_tokens": "", "cost_usd": ""},
    ])  # fmt: skip
    mcols = [
        "machine",
        "file",
        "framing",
        "subject",
        "outcome",
        "produced",
        "trailing_bytes",
        "error",
    ]
    put("malformed_matrix", mcols, [
        {"machine": "M-B", "file": "rfc1950/t.bin", "framing": "zlib", "subject": s, "outcome": o}
        for s, o in [("cf", "error:TrailingData"), ("zlib", "accept"), ("mox", "accept+trailing"), ("zng", "unsupported")]
    ] + [{"machine": "M-B", "file": "rfc1951/x.bin", "framing": "raw", "subject": "cf", "outcome": "accept"}])  # fmt: skip
    put("malformed_disagreements", ["file", "framing", "outcomes_by_subject", "cf_expected"],
        [{"file": "rfc1950/t.bin", "framing": "zlib", "outcomes_by_subject": "", "cf_expected": "TrailingData"}])  # fmt: skip
    put("fuzz_stats", ["machine", "target", "budget_cpu_hours", "executions", "exec_per_s", "cov_lines_pct",
                       "cov_regions_pct", "divergences", "archive"],
        [{"machine": "M-B", "target": t, "budget_cpu_hours": 4, "executions": 5_000_000, "exec_per_s": 300,
          "cov_lines_pct": 70, "cov_regions_pct": 60, "divergences": d, "archive": "a"}
         for t, d in [("diff_cf_zlib", 0), ("diff_cf_zrs", 2)]])  # fmt: skip
    put("checksums", ["machine", "subject", "algo", "size", "median_gib_s", "ci_lo_gib_s", "ci_hi_gib_s", "status"], [
        {"machine": m, "subject": s, "algo": a, "size": n, "median_gib_s": v, "status": "ok"}
        for m in ("M-B", "M-A")
        for s in ("cf", "zlib")
        for a in ("adler32", "crc32")
        for n, v in [(64, 1.0), (4096, 4.0), (65536, 8.0)]
    ])  # fmt: skip


@pytest.fixture
def results(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    more_charts.PENDING_REASONS.clear()
    fixtures()
    return tmp_path


@pytest.mark.parametrize("name", list(more_charts.FIGURES))
def test_each_figure_renders_from_fixture_tables(name, results):
    out = results / "figs"
    got = more_charts.FIGURES[name](out)
    assert got, name
    assert all(p.exists() and p.stat().st_size > 1000 for p in got)
    assert {p.suffix for p in got} == {".svg", ".png"}
    if name == "checksum_throughput":
        assert {p.stem for p in got} == {"checksum_throughput_M-A", "checksum_throughput_M-B"}
    else:
        assert {p.stem for p in got} == {name}
    assert "Parity note" in next(p for p in got if p.suffix == ".svg").read_text()


def test_pending_table_returns_none_with_reason(results):
    put("fuzz_stats", ["machine", "target"], [], pending="no full fuzz run")
    assert more_charts.fuzz_stats(results / "figs") is None
    assert more_charts.PENDING_REASONS["fuzz_stats"] == "fuzz_stats is pending: no full fuzz run"
    put("unsafe", ["subject"], [])
    assert more_charts.unsafe_counts(results / "figs") is None
    assert more_charts.PENDING_REASONS["unsafe_counts"] == "unsafe has no rows"
    (results / "results" / "binary_size.csv").unlink()
    assert more_charts.binary_size(results / "figs") is None
    assert "does not exist" in more_charts.PENDING_REASONS["binary_size"]
    assert not (results / "figs" / "fuzz_stats.svg").exists()


def test_figure_data_helpers():
    rust, c = more_charts.unsafe_data([
        {"subject": "zrs", "unsafe_blocks": "10", "unsafe_fns": "2", "note": ""},
        {"subject": "zrs", "unsafe_blocks": "1", "unsafe_fns": "", "note": ""},
        {"subject": "zlib", "unsafe_blocks": "", "unsafe_fns": "", "note": "C: whole"},
    ])  # fmt: skip
    assert rust == {"zrs": (11, 2)} and c == ["zlib"]
    rounds, tokens, cost = more_charts.effort_data([
        {"round": "1", "stage": "plan", "input_tokens": "1", "output_tokens": "2", "cache_write_tokens": "3", "cost_usd": "1.5"},
        {"round": "2", "stage": "plan", "input_tokens": "", "output_tokens": "", "cache_write_tokens": "", "cost_usd": ""},
    ])  # fmt: skip
    assert (
        rounds == ["1", "2"]
        and tokens["plan"] == {"1": 6, "2": 0}
        and cost == {"1": 1.5, "2": None}
    )


def test_binary_size_missing_opt_is_na_not_zero(results, monkeypatch):
    put("binary_size", ["machine", "subject", "opt", "bytes", "note"], [
        {"machine": "M-B", "subject": s, "opt": o, "bytes": b, "note": ""}
        for s, o, b in [("cf", "3", 393888), ("cf", "s", 373408), ("zng", "3", 90000), ("zng", "s", "")]
    ])  # fmt: skip
    grabbed = {}

    def grab(fig, name, note, out_dir=None):
        grabbed["fig"] = fig
        return []

    monkeypatch.setattr(more_charts, "_save", grab)
    more_charts.binary_size(results / "figs")
    ax = grabbed["fig"].axes[0]
    assert all(p.get_height() > 0 for p in ax.patches)
    assert len(ax.patches) == 3
    assert [t.get_text() for t in ax.texts].count("n/a") == 1


def test_malformed_grid_keeps_machines_apart():
    from cfbench import more_charts

    matrix = [{"machine": m, "file": "f.bin", "subject": s, "outcome": o}
              for m, s, o in (("M-A", "cf", "error:X"), ("M-A", "zlib", "accept"),
                              ("M-B", "cf", "accept"), ("M-B", "zlib", "accept"))]  # fmt: skip
    dis = [{"machine": "M-A", "file": "f.bin"}]
    files, subjects, cell = more_charts.malformed_grid(matrix, dis)
    assert files == ["f.bin (M-A)"] and subjects == ["cf", "zlib"]
    assert cell[("f.bin (M-A)", "cf")] == "error:X"  # M-B's outcome does not overwrite M-A's
    legacy = more_charts.malformed_grid(
        [{"file": "f.bin", "subject": "cf", "outcome": "accept"}], [{"file": "f.bin"}]
    )
    assert legacy[0] == ["f.bin"]
