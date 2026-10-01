import hashlib
import json
from pathlib import Path

import pytest

from cfbench import paths, provenance, rawio

FIX_RAW = Path(__file__).parent / "fixtures" / "raw"


@pytest.fixture
def tables(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "RAW", FIX_RAW)
    return tmp_path / "results"


def raw_files():
    return sorted(rawio.list_raw("perf", machine="M-T"))[:2]


ROWS = [
    {"name": "b", "level": 9, "v": 2.0 / 3.0},
    {"name": "a", "level": 6, "v": 1234567.891},
    {"name": "a", "level": 1, "v": None},
]


def test_write_is_byte_identical_on_rewrite(tables):
    provenance.write_table("t", ["name", "level", "v"], ROWS, script="s", raw_files=raw_files())
    first = (tables / "t.csv").read_bytes(), (tables / "t.csv.provenance.json").read_bytes()
    provenance.write_table(
        "t", ["name", "level", "v"], list(reversed(ROWS)), script="s", raw_files=raw_files()[::-1]
    )
    second = (tables / "t.csv").read_bytes(), (tables / "t.csv.provenance.json").read_bytes()
    assert first == second
    lines = first[0].decode().splitlines()
    assert lines == ["name,level,v", "a,1,", "a,6,1.23457e+06", "b,9,0.666667"]


def test_sidecar_lists_raw_files_with_sha256(tables):
    files = raw_files()
    provenance.write_table("t", ["name"], [{"name": "x"}], script="mod.script", raw_files=files)
    side = json.loads((tables / "t.csv.provenance.json").read_text())
    assert side["table"] == "t.csv" and side["script"] == "mod.script"
    assert side["pending"] is None and side["columns"] == ["name"]
    assert [e["sha256"] for e in side["raw_files"]] == [
        hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files, key=lambda p: str(p))
    ]
    assert {e["machine"] for e in side["raw_files"]} == {"M-T"}
    assert all(e["timestamp"].endswith("Z") for e in side["raw_files"])


def test_pending_and_read_round_trip(tables):
    provenance.write_table(
        "t", ["a", "b"], [], script="s", raw_files=[], pending="Pending: run make X"
    )
    rows, side = provenance.read_table("t")
    assert rows == [] and side["pending"] == "Pending: run make X"
    provenance.write_table("u", ["a", "b"], [{"a": 1, "b": None}], script="s", raw_files=[])
    rows, _ = provenance.read_table("u")
    assert rows == [{"a": "1", "b": ""}]
    assert provenance.to_float("") is None and provenance.to_float("2.5") == 2.5


def test_fmt_rules():
    assert provenance.fmt(0.1 + 0.2) == "0.3"
    assert provenance.fmt(None) == ""
    assert provenance.fmt(12) == "12"
    assert provenance.fmt(True) == "true"
