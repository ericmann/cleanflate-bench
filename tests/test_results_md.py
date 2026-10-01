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


THREATS = ["Training-data contamination", "Machine variance and thermal effects", "Feature-scope mismatch",
           "Fuzz budget limits", "n=1 build effort", "Hardware-CRC asymmetry"]  # fmt: skip


def test_threats_section_covers_six_required_threats(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    text = results_md.threats_section(d, CFG)
    heads = re.findall(r"^### (.+)$", text, flags=re.MULTILINE)
    assert heads == THREATS
    paras = [p for p in text.split("### ")[1:]]
    assert all(len(p.splitlines()) >= 3 for p in paras)  # a real paragraph under each heading
    assert "T1 claim" in paras[0] or "Pending" in paras[0]
    assert f"{CFG['perf']['max_start_load']}" in paras[1] and "not 'pass'" in paras[1]
    assert str(CFG["fuzz"]["budget_cpu_hours"]) in paras[3]
    assert "hardware CRC" in paras[5]


def test_full_render_is_deterministic(isolated):
    d = isolated / "res"
    shutil.copytree(FIX, d)
    a = results_md.render(d, CFG)
    assert a == results_md.render(d, CFG)
    assert a.startswith(results_md.HEADER)
    heads = re.findall(r"^## (.+)$", a, flags=re.MULTILINE)
    assert heads == [*TITLES, "Correctness", "Size, safety and complexity", "Clean-room verification",
                     "Effort, cost and provenance", "Findings for the cleanflate repo", "Threats to validity"]  # fmt: skip
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
    text = results_md.similarity_section(d, CFG)
    assert "| cf-zrs | 5 | 2 | 1 | 1 | 1 |" in text
    assert "RFC-forced" in text and "Unreviewed" in text and "STRUCTURE_COMPARISON.md" in text
    assert "**Result statement:**" in text and "tree-sitter" in text


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
