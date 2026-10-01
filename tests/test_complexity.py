import json
from pathlib import Path

import lizard
import pytest

from cfbench import complexity, paths, provenance, rawio
from cfbench.tools import ToolStatus

FIX = Path(__file__).parent / "fixtures" / "complexity"


def test_distribution_nearest_rank_p90():
    d = complexity.distribution(list(range(1, 11)))
    assert d == {"n": 10, "median": 5.5, "p90": 9, "max": 10}  # rank ceil(0.9 * 10) = 9
    assert complexity.distribution([7])["p90"] == 7
    d11 = complexity.distribution([1] * 10 + [100])
    assert d11["p90"] == 1 and d11["max"] == 100  # rank ceil(9.9) = 10
    assert complexity.distribution([3, 1, 2])["median"] == 2
    assert complexity.distribution([]) == {"n": 0, "median": None, "p90": None, "max": None}


def test_rca_json_function_spaces_parsed():
    doc = json.loads((FIX / "rca_excerpt.json").read_text())
    funcs = complexity.rca_functions(doc, "a.rs")
    names = [f["name"] for f in funcs]
    assert names[:3] == ["new", "bits", "available"] and complexity.ANONYMOUS not in names
    fill = next(f for f in funcs if f["name"] == "fill")
    assert fill == {
        "file": "a.rs",
        "name": "fill",
        "start_line": 51,
        "cyclomatic": 3.0,
        "cognitive": 3.0,
    }
    refill = next(f for f in funcs if f["name"] == "refill_bulk")
    assert refill["cyclomatic"] == 8.0  # the enclosing function carries its closures' complexity


def test_tool_gap_falls_back_and_marks_cognitive_unavailable(tmp_path):
    files = {s: [tmp_path / f"{s}.rs"] for s in complexity.RUST_SUBJECTS}
    gap = ToolStatus("rust-code-analysis-cli", "0.0.25", "/x", False, "install failed (101): boom")
    payload = complexity.collect_rust(
        gap, rca=lambda *a: pytest.fail("rca must not run"),
        lizard=lambda f: (FIX / "lizard.csv").read_text(), file_lists=files,
    )  # fmt: skip
    assert payload["tool"]["name"] == "lizard" and payload["cognitive"] == "unavailable"
    assert payload["tool_gap"]["error"].startswith("install failed")
    cf = payload["subjects"]["cf"]
    assert cf["distributions"]["cognitive"] is None
    assert cf["distributions"]["cyclomatic"] == {"n": 2, "median": 3.0, "p90": 5.0, "max": 5.0}
    assert [f["cognitive"] for f in cf["functions"]] == [None, None]
    ok = ToolStatus("rust-code-analysis-cli", "0.0.25", "/bin/rca", True, None)
    doc = json.loads((FIX / "rca_excerpt.json").read_text())
    got = complexity.collect_rust(ok, rca=lambda b, f: doc, file_lists=files)
    assert got["cognitive"] == "available" and got["tool_gap"] is None
    assert got["subjects"]["zrs"]["distributions"]["cognitive"]["n"] > 0


C_SOURCE = """
int classify(int a, int b) {
    if (a > 0 && b > 0) { return 1; }
    for (int i = 0; i < a; i++) { if (i == b) return 2; }
    return 0;
}
static int plain(void) { return 3; }
"""


def test_lizard_function_list_parsed():
    info = lizard.analyze_file.analyze_source_code("a.c", C_SOURCE)
    funcs = complexity.c_functions(info, "a.c")
    assert [f["name"] for f in funcs] == ["classify", "plain"]
    assert funcs[0]["cyclomatic"] == 5.0 and funcs[1]["cyclomatic"] == 1.0
    assert all(f["cognitive"] is None and f["file"] == "a.c" for f in funcs)
    payload = complexity.collect_c(
        analyze=lambda path: lizard.analyze_file.analyze_source_code(path, C_SOURCE),
        file_lists={s: [Path("x.c")] for s in complexity.C_SUBJECTS},
    )
    assert payload["tool"]["version"] == lizard.version and payload["cognitive"] == "unavailable"
    assert payload["subjects"]["zlib"]["distributions"]["cyclomatic"]["max"] == 5.0


def test_table_marks_cognitive_unavailable_for_c(tmp_path, monkeypatch):
    c = complexity.collect_c(
        analyze=lambda path: lizard.analyze_file.analyze_source_code(path, C_SOURCE),
        file_lists={s: [Path("x.c")] for s in complexity.C_SUBJECTS},
    )
    rust = {
        "tool": {"name": "rust-code-analysis-cli", "version": "0.0.25"},
        "cognitive": "available",
        "subjects": {"cf": {"distributions": {
            "cyclomatic": {"n": 3, "median": 2, "p90": 4, "max": 4},
            "cognitive": {"n": 3, "median": 0, "p90": 6, "max": 6}}}},
    }  # fmt: skip
    rows = complexity.table_rows(rust, c)
    by = {(r["subject"], r["metric"]): r for r in rows}
    assert (
        by[("cf", "cognitive")]["p90"] == 6
        and by[("cf", "cognitive")]["tool"] == "rust-code-analysis-cli"
    )
    cog = by[("zlib", "cognitive")]
    assert (
        cog["tool"].endswith("(cognitive unavailable)")
        and cog["median"] is None
        and cog["max"] is None
    )
    assert cog["n_functions"] == 2 and cog["tool_version"] == lizard.version
    assert (
        by[("zlib", "cyclomatic")]["max"] == 5.0 and by[("zng", "cyclomatic")]["n_functions"] == 2
    )
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    complexity.derive()
    assert provenance.read_table("complexity")[1]["pending"] == complexity.PENDING
    rawio.write_raw("size", c, machine="any", profile="full", script="s", environment=None)
    complexity.derive()
    got, side = provenance.read_table("complexity")
    assert side["pending"] is None and list(got[0]) == complexity.COLUMNS and len(got) == 4
