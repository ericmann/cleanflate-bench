import shutil
from pathlib import Path

import pytest

from cfbench import charts, config, provenance
from cfbench.kits import paper_assets as pa

FIX = Path(__file__).parent / "fixtures" / "results"
CFG = config.load_config("full")


@pytest.fixture
def results(tmp_path):
    d = tmp_path / "results"
    shutil.copytree(FIX, d)
    return d


def drop(d, table, keep):
    import csv

    rows, side = provenance.read_table(table, d)
    with open(provenance.table_path(table, d), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(side["columns"])
        for r in rows:
            if keep(r):
                w.writerow([r[c] for c in side["columns"]])


def test_table_has_at_most_six_rows_and_footnote(results):
    t = pa.build_table(results, CFG)
    assert len(t.rows) == 5 <= pa.MAX_ROWS
    assert t.columns == ["cf", "zlib", "mox"]
    assert "no SIMD" in t.footnote and "no C ABI" in t.footnote  # the parity note, always present
    md = t.to_markdown()
    assert md.rstrip().endswith(f"*{t.footnote}*") and md.count("\n| ") >= 5
    r1, r2, r3, r4, r5 = t.rows
    # machine-dependent rows show both machines in one cell, M-A first
    assert "M-A / M-B" in r1.label and "M-A / M-B" in r2.label and "M-A / M-B" in r5.label
    assert r1.cells["cf"].display == "80 MiB/s (0.86x) / 70 MiB/s (0.76x)"
    assert r1.cells["zlib"].display == "100 MiB/s (1.00x) / 100 MiB/s (1.00x)"
    assert r2.cells["cf"].display == "0.86x / 0.76x" and r2.cells["zlib"].display == "1.00x / 1.00x"
    assert (
        r2.cells["mox"].display == "n/a" and r2.cells["mox"].status == "n/a"
    )  # unsupported, never zero
    assert (
        r3.cells["cf"].display == "0 blocks + 0 fns"
        and r3.cells["zlib"].display == "C (whole codebase)"
    )
    assert r3.cells["mox"].display == "0 blocks + 0 fns"
    assert (
        r4.cells["cf"].display == "0 direct / 0 transitive"
        and r4.cells["mox"].display == "1 direct / 1 transitive"
    )
    assert r4.cells["zlib"].display == "n/a"
    # the fixture has binary sizes for M-B only, so M-A's half is pending
    assert r5.cells["cf"].display == "pending / 393,888 B" and r5.cells["cf"].status == "pending"
    # every numeric cell is backed by evidence with a raw file and a script
    for row in t.rows:
        for c in row.cells.values():
            if c.evidence:
                assert all(e.raw_files and e.script for e in c.evidence)


def test_missing_machine_cells_are_pending(results):
    drop(results, "perf_aggregates", lambda r: r["machine"] != "M-A")
    t = pa.build_table(results, CFG)
    a = t.rows[0]
    assert a.cells["cf"].display.startswith("pending / ") and a.cells["cf"].status == "pending"
    assert "no row" in a.cells["cf"].reason and "make perf" in a.cells["cf"].reason
    assert a.cells["cf"].display != "pending / pending"
    drop(results, "binary_size", lambda r: False)
    assert pa.build_table(results, CFG).rows[4].cells["cf"].display == "pending / pending"
    empty = results.parent / "empty"
    empty.mkdir()
    t = pa.build_table(empty, CFG)
    pending = [c for row in t.rows for c in row.cells.values() if c.status == "pending"]
    assert pending and all("pending" in c.display for c in pending)
    assert t.rows[2].cells["zlib"].display == "C (whole codebase)"  # needs no data


def test_figure_written_at_paper_width(results, tmp_path):
    out_dir = tmp_path / "figs"
    paths_, evid, pending = pa.build_figure(results, out_dir, CFG)
    assert [p.name for p in paths_] == [
        "paper_throughput_unsafe.svg",
        "paper_throughput_unsafe.png",
    ]
    assert pending == [] and evid and all(e.raw_files for e in evid)
    png = paths_[1].read_bytes()
    width = int.from_bytes(png[16:20], "big")
    dpi = CFG["charts"]["base_dpi"]
    assert width == round(CFG["charts"]["paper_width_in"] * 2 * dpi)  # 2x PNG at the paper width
    assert charts.size_inches("paper")[0] == CFG["charts"]["paper_width_in"]


def test_figure_annotates_unsafe_and_marks_missing_data(results, tmp_path):
    data, _, _ = pa._bar_data(results, CFG)
    assert data["M-A"]["cf"] == (80.0, "unsafe: 0") and data["M-A"]["zlib"][1] == "C"
    fig = pa.draw_bars(data, CFG)
    texts = sorted(t.get_text() for t in fig.axes[0].texts)
    assert texts.count("unsafe: 0") == 4 and texts.count("C") == 2
    drop(results, "perf_aggregates", lambda r: r["machine"] == "M-B")
    data, _, pending = pa._bar_data(results, CFG)
    assert "M-A" not in data and pending and "M-A" in pending[0]
    fig = pa.draw_bars(data, CFG)
    assert "pending" in [t.get_text() for t in fig.axes[0].texts]
    none, _, why = pa.build_figure(results.parent / "empty", tmp_path / "f2", CFG)
    assert none is None and why


def test_trajectory_figure_variant(results, tmp_path):
    cfg = config.load_config("full")
    cfg["paper"]["figure"] = "trajectory"
    out, _, pending = pa.build_figure(results, tmp_path / "f", cfg)
    assert [p.name for p in out] == ["trajectory_M-A.svg", "trajectory_M-A.png"] and pending == []
