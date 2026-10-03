import re
import shutil
from pathlib import Path

import pytest

from cfbench import config, paths, provenance
from cfbench.kits import blog, pipeline, sections

FIX = Path(__file__).parent / "fixtures" / "results"
CFG = config.load_config("full")


@pytest.fixture
def results(tmp_path, monkeypatch):
    d = tmp_path / "res"
    shutil.copytree(FIX, d)
    monkeypatch.setattr(paths, "RESULTS", d)
    return d


def put(d, name, columns, rows, pending=None):
    provenance.write_table(name, columns, rows, script="t", raw_files=[], pending=pending)


def test_outline_beats_present(results, tmp_path):
    text = blog.render(results, CFG)
    heads = re.findall(r"^## (.+)$", text, flags=re.MULTILINE)
    assert heads[0] == blog.LEAD == "Claims and evidence"  # the claims lead every kit
    assert heads[1 : 1 + len(blog.BEATS)] == blog.BEATS
    assert heads[1 + len(blog.BEATS) :] == ["Most surprising findings (ranked)", "Open questions"]
    assert text.startswith(blog.HEADER) and "not a finished post" in text
    assert f"# Blog notes: {pipeline.PIPELINE_NAME}" in text
    lead = text.split("## The pipeline and the question")[0]
    order = [lead.index(f"**{c.title}.**") for c in pipeline.CATEGORIES]
    assert order == sorted(order)
    empty = tmp_path / "empty"
    empty.mkdir()
    again = blog.render(empty, CFG)  # no data at all still gives every beat
    assert (
        re.findall(r"^## (.+)$", again, flags=re.MULTILINE)[1 : 1 + len(blog.BEATS)] == blog.BEATS
    )
    assert blog.render(results, CFG) == text  # deterministic


def test_surprises_include_malformed_disagreements_and_outliers(results):
    put(results, "malformed_disagreements", ["file", "framing", "outcomes_by_subject", "cf_expected"],
        [{"file": f"rfc1950/f{i}.bin", "framing": "zlib", "outcomes_by_subject": "cf=error:X", "cf_expected": "X"}
         for i in range(2)])  # fmt: skip
    cols = [
        "machine",
        "variant",
        "subject",
        "corpus",
        "workload",
        "level",
        "framing",
        "mode",
        "ratio_vs_zlib",
        "status",
    ]
    put(results, "perf_cells", cols,
        [{"machine": "M-B", "variant": "generic", "subject": "cf", "corpus": "silesia", "workload": f"silesia/f{i}",
          "level": 6, "framing": "raw", "mode": "oneshot", "ratio_vs_zlib": 0.3 + i * 0.1, "status": "ok"}
         for i in range(8)])  # fmt: skip
    got = [b.text for b in blog.surprises(results, CFG)]
    assert any("disagree on accept versus reject for 2 malformed files" in t for t in got)
    worst = [t for t in got if "worst case" in t]
    best = [t for t in got if "best case" in t]
    assert len(worst) == 3 and len(best) == 3
    assert (
        "silesia/f0" in worst[0]
        and "0.30x" in worst[0]
        and "silesia/f7" in best[0]
        and "1.00x" in best[0]
    )
    assert got.index(next(t for t in got if "malformed" in t)) < got.index(worst[0])  # ranked order


def test_inconclusive_items_listed_as_open_questions(results):
    put(results, "content_hypotheses",
        ["hypothesis", "machine", "feature", "n", "rho", "p", "expected_sign", "verdict"],
        [{"hypothesis": "H1", "machine": "ALL", "feature": "(combined)", "verdict": "inconclusive",
          "expected_sign": "negative"},
         {"hypothesis": "H2", "machine": "ALL", "feature": "(combined)", "verdict": "confirmed",
          "expected_sign": "negative"}])  # fmt: skip
    put(results, "fuzz_stats", ["machine", "target"], [], pending="no full fuzz run")
    items = blog.open_questions(results, CFG)
    assert any("Hypothesis H1 is inconclusive" in i for i in items)
    assert not any("Hypothesis H2" in i for i in items)
    assert any(i.startswith("Pending table `fuzz_stats`") for i in items)
    assert sum(i.startswith("Threat to validity") for i in items) == len(sections.THREAT_TITLES)
    text = blog.render(results, CFG)
    assert any(
        "Hypothesis h1 did not come out confirmed" in b.text for b in blog.surprises(results, CFG)
    )
    assert "Hypothesis H1 is inconclusive" in text
