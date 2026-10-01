import json

import pytest

from cfbench import paths, subjects


def test_registry_covers_every_subject():
    assert set(subjects.SUBJECTS) == {
        "cf", "zlib", "zlib-nohw", "zng", "zrs", "mox", "zsys", "cf-r1", "cf-r2", "cf-r3",
    }  # fmt: skip
    assert subjects.SUBJECTS["zsys"].kind == "secondary"
    assert subjects.SUBJECTS["zlib-nohw"].kind == "control"


def test_binary_paths_per_build():
    assert subjects.binary_path("cf") == paths.ROOT / "target" / "release" / "cfb-cf"
    assert subjects.binary_path("zng", "debug") == paths.ROOT / "target" / "debug" / "cfb-zng"
    assert "native" in subjects.binary_path("zrs", "native").parts
    with pytest.raises(ValueError):
        subjects.binary_path("zng", "round1")  # only cf has round builds
    with pytest.raises(ValueError):
        subjects.binary_path("cf", "bogus")


def test_command_override_from_env(monkeypatch):
    monkeypatch.setenv("CFB_SUBJECT_CMD", json.dumps({"cf": ["python", "fake.py", "--x"]}))
    assert subjects.command("cf") == ["python", "fake.py", "--x"]
    assert subjects.command("zlib") == [str(subjects.binary_path("zlib"))]
    monkeypatch.delenv("CFB_SUBJECT_CMD")
    assert subjects.command("cf") == [str(subjects.binary_path("cf"))]


def test_native_binary_path():
    p = subjects.binary_path("cf", "native")
    assert p == paths.ROOT / "target" / "native" / "release" / "cfb-cf"
    assert subjects.native_label("zrs") == "zrs@native"
    assert subjects.split_label("zrs@native") == ("zrs", "native")
    assert subjects.split_label("zlib") == ("zlib", "release")


def test_round_binary_paths():
    for n in (1, 2, 3):
        want = paths.ROOT / "target" / f"round{n}" / "release" / "cfb-cf"
        assert subjects.binary_path(f"cf-r{n}") == want
        assert subjects.binary_path("cf", f"round{n}") == want
        assert subjects.SUBJECTS[f"cf-r{n}"].kind == "round"
    assert subjects.binary_path("cf-r2", "release") == subjects.binary_path("cf-r2", "round2")


def test_cargo_revs_match_rounds_json():
    import tomllib

    with open(paths.ROOT / "crates" / "subj-cf" / "Cargo.toml", "rb") as f:
        deps = tomllib.load(f)["dependencies"]
    rounds = json.loads((paths.CONFIG / "rounds.json").read_text())
    for r in rounds["rounds"]:
        dep = deps[f"cleanflate_r{r['round']}"]
        assert dep["rev"] == r["sha"], r
        assert dep["package"] == "cleanflate" and dep["optional"] is True
        assert dep["git"] == rounds["repo_url"]
