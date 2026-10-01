import json
from pathlib import Path

import pytest

from cfbench import complexity
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
