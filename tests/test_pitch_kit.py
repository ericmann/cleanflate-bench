import re
import shutil
import struct
from pathlib import Path

import pytest

from cfbench import config, paths
from cfbench.kits import pitch

FIX = Path(__file__).parent / "fixtures" / "results"
CFG = config.load_config("full")


@pytest.fixture
def fixture_results(tmp_path, monkeypatch):
    d = tmp_path / "results"
    shutil.copytree(FIX, d)
    monkeypatch.setattr(paths, "RESULTS", d)
    return d


@pytest.fixture
def empty_results(tmp_path, monkeypatch):
    d = tmp_path / "empty"
    d.mkdir()
    monkeypatch.setattr(paths, "RESULTS", d)
    return d


def png_size(p: Path) -> tuple[int, int]:
    head = p.read_bytes()[:24]
    return struct.unpack(">II", head[16:24])


def test_slide_figures_are_16_by_9(fixture_results, tmp_path):
    figs, _doc = pitch.build(fixture_results, tmp_path / "kit", CFG)
    rendered = [f for f in figs if f.rendered]
    assert len(rendered) >= 3
    pngs = sorted((tmp_path / "kit").glob("*.png"))
    assert pngs
    for p in pngs:
        w, h = png_size(p)
        assert abs(w / h - 16 / 9) < 0.01, p.name
    for p in (tmp_path / "kit").glob("*.svg"):
        m = re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', p.read_text())
        assert m and abs(float(m.group(1)) / float(m.group(2)) - 16 / 9) < 0.01, p.name
    assert {f.key for f in rendered} >= {"unsafe_counts", "binary_size", "similarity"}


def test_fewer_than_eight_figures_is_stated(empty_results, tmp_path):
    figs, doc = pitch.build(empty_results, tmp_path / "kit", CFG)
    text = doc.read_text()
    assert not any(f.rendered for f in figs)
    assert "Only 0 figures rendered" in text and "aims for 8 to 12" in text
    assert "table trajectory is missing" in text  # the pending reason is listed
    eight = [pitch.Figure(f"k{i}", f"T{i}", [f"s{i}"]) for i in range(8)]
    head8 = pitch.render_document([], empty_results, CFG)  # no figures: stated
    assert "Only 0 figures" in head8
    assert not pitch.render_document(eight[:0], empty_results, CFG).startswith("no")
    assert pitch.MIN_FIGURES == 8 and pitch.MAX_FIGURES == 12


def test_all_four_named_questions_answered_or_marked_no_data(
    empty_results, fixture_results, tmp_path
):
    names = ["Why is it slower than C?", "How do you know it wasn't copied?", "What does this cost?",
             "Can it run air-gapped / on other models?"]  # fmt: skip
    for results in (empty_results, fixture_results):
        paths.RESULTS = results
        _figs, doc = pitch.build(results, tmp_path / results.name, CFG)
        text = doc.read_text()
        qa = text.split("## Questions a reviewer will ask")[1]
        for q in names:
            assert f"### {q}" in qa
        for section in qa.split("### ")[1:]:
            assert (
                "no measurement in this study" in section
                or "Pending" in section
                or re.search(r"\d", section)
            ), section
    empty_qa = pitch.render_document([], empty_results, CFG).split(
        "## Questions a reviewer will ask"
    )[1]
    assert empty_qa.count("no measurement in this study") >= 4
    full_qa = pitch.render_document([], fixture_results, CFG)
    assert "28.5" not in full_qa and "30.0 hours" in full_qa  # fixture effort total, from evidence


def test_talking_point_numbers_come_from_evidence(fixture_results, tmp_path):
    with pytest.raises(ValueError, match="has no evidence"):
        pitch.check_bullet(pitch.Bullet("it is 99 times faster"))
    ok = pitch.Bullet("scores 0.040 here", (pitch._look("similarity_summary", {"metric": "ident_jaccard", "pair": "zrs-mox"},
                                                        "score", fixture_results, fmt="{:.3f}"),))  # fmt: skip
    assert pitch.check_bullet(ok) is ok
    seen = 0
    for fn in pitch.BULLETS.values():
        for b in fn(fixture_results, CFG):
            pitch.check_bullet(b)  # raises on an unsupported number
            seen += len(pitch.numbers(b.text))
    assert seen > 0
    for question in pitch.QUESTIONS:
        for b in question(fixture_results, CFG).bullets:
            pitch.check_bullet(b)
    figs, doc = pitch.build(fixture_results, tmp_path / "kit", CFG)
    assert doc.read_text().startswith(pitch.HEADER)
    again = pitch.render_document(figs, fixture_results, CFG)
    assert again == doc.read_text()  # deterministic


def test_substring_of_evidence_is_not_evidence():
    with pytest.raises(ValueError):
        pitch.check_bullet(
            pitch.Bullet("cf is 9 times faster than zlib on 35 files", (), ("0.935",))
        )
