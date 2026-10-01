import json

import pytest

from cfbench import paths, subjects


def test_registry_covers_every_subject():
    assert set(subjects.SUBJECTS) == {"cf", "zlib", "zlib-nohw", "zng", "zrs", "mox", "zsys"}
    assert subjects.SUBJECTS["zsys"].kind == "secondary"
    assert subjects.SUBJECTS["zlib-nohw"].kind == "control"


def test_binary_paths_per_build():
    assert subjects.binary_path("cf") == paths.ROOT / "target" / "release" / "cfb-cf"
    assert subjects.binary_path("zng", "debug") == paths.ROOT / "target" / "debug" / "cfb-zng"
    assert "native" in subjects.binary_path("zrs", "native").parts
    assert subjects.binary_path("cf", "round2").parts[-2:] == ("round2", "cfb-cf")
    with pytest.raises(ValueError):
        subjects.binary_path("zng", "round1")
    with pytest.raises(ValueError):
        subjects.binary_path("cf", "bogus")


def test_command_override_from_env(monkeypatch):
    monkeypatch.setenv("CFB_SUBJECT_CMD", json.dumps({"cf": ["python", "fake.py", "--x"]}))
    assert subjects.command("cf") == ["python", "fake.py", "--x"]
    assert subjects.command("zlib") == [str(subjects.binary_path("zlib"))]
    monkeypatch.delenv("CFB_SUBJECT_CMD")
    assert subjects.command("cf") == [str(subjects.binary_path("cf"))]
