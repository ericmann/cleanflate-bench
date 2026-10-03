import re
import shutil
from pathlib import Path

import pytest

from cfbench import config, paths, provenance
from cfbench.kits import pipeline, results_md, sections

FIX = Path(__file__).parent / "fixtures" / "results"
CFG = config.load_config("full")
TITLES = ["Claims and evidence", "Equivalence", "Safety", "Clean-room", "Effort, cost and provenance",
          "Viability", "Iteration", "Findings for the cleanflate repo", "Threats to validity", "Appendix"]  # fmt: skip
APPENDIX = ["Environments", "Subjects and pins", "Per-file throughput", "Tiny inputs (setup cost)",
            "Content analysis", "Binary size"]  # fmt: skip


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    return tmp_path


def test_sections_present_in_order(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    text = results_md.render_sections(d, CFG)
    heads = re.findall(r"^## (.+)$", text, flags=re.MULTILINE)
    assert heads == TITLES == results_md.TITLES
    # the claims lead, in category order, before any results section
    claims_part = text.split("\n## Equivalence")[0]
    cats = re.findall(r"^### (.+)$", claims_part, flags=re.MULTILINE)
    assert cats == [
        "Equivalence",
        "Safety",
        "Clean-room",
        "Effort",
        "Viability",
        "Iteration",
        "Checked and not claimed",
    ]
    # content correlations, binary size, tiny inputs and per-file tables live in the appendix
    appendix = text.split("\n## Appendix")[1]
    assert re.findall(r"^### (.+)$", appendix, flags=re.MULTILINE) == APPENDIX
    body = text.split("\n## Appendix")[0]
    for moved in (
        "Minimal decoder binary size",
        "Tiny inputs (setup cost)",
        "median MiB/s per file",
        "## Content analysis",
    ):
        assert moved not in body, moved
    viab = text.split("\n## Viability")[1].split("\n## Iteration")[0]
    assert "### Both machines in one table" in viab and "Aggregate MiB/s" in viab
    assert "### Hardware-CRC evidence: the gzip gap on each machine" in viab
    assert "### Sleep-interruption check" in text.split("\n## Iteration")[1]
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
    text = results_md.render_sections(isolated / "none", CFG)
    for make in ("make perf", "make framing", "make content", "make trajectory", "make env", "make malformed",
                 "make conformance", "make fuzz", "make effort"):  # fmt: skip
        assert f"Pending: run `{make}`" in text, make
    pend = [p for p in text.split("\n\n") if p.startswith("Pending: run `")]
    assert pend and all(re.match(r"Pending: run `make [\w-]+` on ", p) for p in pend)


REQUIRED_THREATS = ["Single case study (n=1 target)", "Run-to-run stability", "M-A sleep during trajectory",
                    "M-A High Power Mode", "M-B background load", "Fuzz budget and throttling",
                    "Host-dependent gzip fixtures"]  # fmt: skip


def test_threats_section_covers_required_threats(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    text = results_md.threats_section(d, CFG)
    heads = re.findall(r"^### (.+)$", text, flags=re.MULTILINE)
    assert heads == sections.THREAT_TITLES and heads[: len(REQUIRED_THREATS)] == REQUIRED_THREATS
    paras = {p.split("\n", 1)[0]: p for p in text.split("### ")[1:]}
    assert all(
        len(p.splitlines()) >= 3 for p in paras.values()
    )  # a real paragraph under each heading
    assert "one target library" in paras["Single case study (n=1 target)"]
    assert "M-A generic: 0 of 10 aggregates flagged (pass)" in paras["Run-to-run stability"]
    assert "rests on none" in paras["Run-to-run stability"]
    for title, note in (("M-A sleep during trajectory", "m-a-sleep"), ("M-A High Power Mode", "m-a-high-power"),
                        ("M-B background load", "m-b-background-load"), ("Fuzz budget and throttling", "fuzz-throttling"),
                        ("Host-dependent gzip fixtures", "m-a-fixtures")):  # fmt: skip
        assert pipeline.note(note).text in paras[title], title
    assert (
        "review stage missed" in paras["Host-dependent gzip fixtures"]
        and "findings.md" in paras["Host-dependent gzip fixtures"]
    )
    fuzz = paras["Fuzz budget and throttling"]
    assert str(CFG["fuzz"]["budget_cpu_hours"]) in fuzz and "1,000 executions" in fuzz
    assert "T1 claim" in paras["Training-data contamination"]
    assert "hardware crc" in paras["Hardware-CRC asymmetry"].lower()


def test_full_render_is_deterministic(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    a = results_md.render(d, CFG)
    assert a == results_md.render(d, CFG)
    assert a.startswith(results_md.HEADER)
    assert f"# Results: {pipeline.PIPELINE_NAME}" in a
    heads = re.findall(r"^## (.+)$", a, flags=re.MULTILINE)
    assert heads == TITLES
    assert (
        results_md.num("2962") == "2962"
        and results_md.num("0.5", 2) == "0.50"
        and results_md.num("") == "n/a"
    )


def test_similarity_section_reports_verdict_counts(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    header = "rank,fragment_id,tokens,left_file,left_lines,right_file,right_lines,verdict,note\n"
    rows = ["1,a,9,x,1-2,y,1-2,RFC-forced,", "2,b,8,x,3-4,y,3-4,RFC-forced,", "3,c,7,x,5-6,y,5-6,suspicious,",
            "4,d,6,x,7-8,y,7-8,,", "5,e,5,x,9-10,y,9-10,idiomatic-inevitable,"]  # fmt: skip
    (d / "similarity_fragments_cf_zrs.csv").write_text(header + "\n".join(rows) + "\n")
    counts = results_md.fragment_counts(d)
    assert counts == [["cf-zrs", 5, 2, 1, 1, 1]]
    text = results_md.clean_room_section(d, CFG)
    assert "| cf-zrs | 5 | 2 | 1 | 1 | 1 |" in text
    assert "RFC-forced" in text and "Unreviewed" in text and "STRUCTURE_COMPARISON.md" in text
    assert "**Result statement:**" in text and "tree-sitter" in text
    assert "### Similarity against negative and positive controls" in text
    assert "Guard and audit totals per round" in text and "Forbidden-read candidates" in text


def test_every_table_carries_parity_note(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    lines = results_md.render(d, CFG).splitlines()
    tables = 0
    for i, line in enumerate(lines):
        if not line.startswith("|---"):
            continue
        tables += 1
        j = i + 1
        while j < len(lines) and lines[j].startswith("|"):
            j += 1
        found = False
        while j < len(lines) and not lines[j].startswith(("#", "|")):
            if results_md.PARITY_NOTE in lines[j]:
                found = True
                break
            j += 1
        assert found, f"table at line {i} lacks the parity note"
    assert tables > 0


def test_methodology_matches_precondition_behaviour(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    p = CFG["perf"]
    meth = results_md.methodology(CFG)
    threats = results_md.threats_section(d, CFG)
    for text in (meth, threats):
        for sent in re.split(r"(?<=[.;])\s+", text):
            if "refused" in sent and "load" in sent:
                assert "strict" in sent, sent
    for key in ("small_in_chunk", "small_out_chunk", "large_in_chunk", "large_out_chunk"):
        assert str(p[key]) in meth
