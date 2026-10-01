import re
import shutil
from pathlib import Path

import pytest

from cfbench import config, paths, provenance
from cfbench.kits import results_md

FIX = Path(__file__).parent / "fixtures" / "results"
CFG = config.load_config("full")
TITLES = ["Environments", "Subjects and pins", "Performance methodology", "Performance results",
          "Framing decomposition", "Content analysis", "Trajectory"]  # fmt: skip


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    return tmp_path


def test_part1_sections_present_in_order(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    text = results_md.render_sections_part1(d, CFG)
    heads = re.findall(r"^## (.+)$", text, flags=re.MULTILINE)
    assert heads == TITLES
    assert text.index("Aggregate MiB/s") > text.index("## Performance results")
    assert f"seed {CFG['run']['seed']}" in text and f"{CFG['perf']['min_samples']} samples" in text
    assert "Source: `results/perf_aggregates.csv`" in text


def test_per_file_tables_include_every_workload(isolated):
    cols = [
        "machine",
        "variant",
        "subject",
        "corpus",
        "workload",
        "level",
        "framing",
        "mode",
        "status",
        "median_mib_s",
    ]
    rows = []
    wls = ["silesia/dickens", "silesia/xml", "canterbury/kennedy.xls"]
    for w in wls:
        corpus = w.split("/")[0]
        for lv in (1, 6):
            for s in ("cf", "zlib", "mox"):
                rows.append({"machine": "M-B", "variant": "generic", "subject": s, "corpus": corpus,
                             "workload": w, "level": lv, "framing": "raw", "mode": "oneshot",
                             "status": "ok", "median_mib_s": 123.456})  # fmt: skip
    provenance.write_table("perf_cells", cols, rows, script="s", raw_files=[])
    text = results_md.per_file_block(paths.RESULTS, CFG)
    for w in wls:
        assert text.count(f"| {w} |") == 2  # level 6 inline and level 1 in details
    assert "<details>" in text and text.count("123.5") >= 3 * 3
    assert "**M-B, silesia, raw framing, level 6: median MiB/s per file**" in text


def test_pending_sections_name_make_target(isolated):
    text = results_md.render_sections_part1(isolated / "none", CFG)
    for make in ("make perf", "make framing", "make content", "make trajectory", "make env"):
        assert f"Pending: run `{make}`" in text, make
    pend = [p for p in text.split("\n\n") if p.startswith("Pending: run `")]
    assert pend and all(re.match(r"Pending: run `make [\w-]+` on ", p) for p in pend)
