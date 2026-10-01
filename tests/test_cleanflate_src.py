import json
import subprocess

import pytest

from cfbench import cleanflate_src as cs
from cfbench import paths


def _g(cwd, *args):
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    """A throwaway upstream with three tagged commits, wired in as the pinned rounds."""
    up = tmp_path / "up"
    up.mkdir()
    _g(up, "init", "-q", "-b", "main")
    rs = []
    for i in (1, 2, 3):
        (up / "f.txt").write_text(str(i))
        _g(up, "add", "f.txt")
        _g(up, "commit", "-q", "-m", f"c{i}")
        tag = f"v0.{i}.0-cleanroom"
        _g(up, "tag", tag)
        rs.append({"round": i, "tag": tag, "sha": _g(up, "rev-parse", "HEAD")})
    rounds = {"repo_url": str(up), "primary_round": 3, "rounds": rs}
    monkeypatch.setattr(cs, "rounds", lambda: rounds)
    monkeypatch.setattr(paths, "THIRD_PARTY", tmp_path / "tp")
    return up, rounds, tmp_path


def test_clone_detaches_at_pinned_sha(upstream):
    _, rounds, tmp = upstream
    p = cs.ensure_clone()
    assert p == tmp / "tp" / "cleanflate"
    assert _g(p, "rev-parse", "HEAD") == rounds["rounds"][2]["sha"]
    assert _g(p, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
    assert cs.pristine_check() == []


def test_tag_mismatch_fails(upstream):
    rounds = upstream[1]
    rounds["rounds"][0]["sha"] = "0" * 40
    with pytest.raises(cs.SourceError, match="v0.1.0-cleanroom"):
        cs.ensure_clone()


def test_pristine_check_reports_dirty_tree(upstream):
    cs.ensure_clone()
    (cs.clone_path() / "f.txt").write_text("edited")
    problems = cs.pristine_check()
    assert any("not clean" in p for p in problems)


def test_pristine_check_ignores_gitignored_files(upstream):
    # an upstream that ignores its generated products, as cleanflate does
    cs.ensure_clone()
    clone = cs.clone_path()
    (clone / ".git" / "info" / "exclude").write_text("generated/\n")
    (clone / "generated").mkdir()
    (clone / "generated" / "x.bin").write_bytes(b"x")
    assert cs.pristine_check() == []


def test_corpus_files_reads_sources_json(tmp_path):
    base = tmp_path / "testdata" / "corpora"
    base.mkdir(parents=True)
    src = {
        "canterbury": {"files": [{"name": "b.txt", "sha256": "bb", "bytes": 2}]},
        "silesia": {
            "files": [
                {"name": "z", "sha256": "zz", "bytes": 3},
                {"name": "a", "sha256": "aa", "bytes": 1},
            ]
        },
    }
    (base / "SOURCES.json").write_text(json.dumps(src))
    got = cs.corpus_files("silesia", path=tmp_path)
    assert got == [("a", base / "silesia" / "a", "aa", 1), ("z", base / "silesia" / "z", "zz", 3)]
    assert cs.corpus_files("canterbury", path=tmp_path)[0][0] == "b.txt"
