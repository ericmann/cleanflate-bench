import io
import subprocess
from pathlib import Path

from cfbench import clean_clone as cc


def git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True, capture_output=True,
    )  # fmt: skip


def make_repo(tmp_path, committed="old\n", recipe="printf 'new\\n' > out.txt") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    (repo / "out.txt").write_text(committed)
    (repo / "Makefile").write_text(f"all:\n\t{recipe}\n.PHONY: all\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def test_dirty_tree_is_refused(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "out.txt").write_text("edited\n")
    out = io.StringIO()
    assert cc.run_check("all", ["out.txt"], repo=repo, sync=None, out=out) == cc.DIRTY
    assert "uncommitted changes" in out.getvalue() and "out.txt" in out.getvalue()
    # an untracked file also means HEAD is not the whole story
    git(repo, "checkout", "--", "out.txt")
    (repo / "stray.txt").write_text("x")
    assert cc.run_check("all", ["out.txt"], repo=repo, sync=None, out=io.StringIO()) == cc.DIRTY
    # but explicitly ignored paths do not block the check
    assert cc.dirty_paths(repo, ignore=("stray.txt",)) == []


def test_difference_exits_nonzero(tmp_path):
    repo = make_repo(tmp_path, committed="old\n")
    out = io.StringIO()
    assert cc.run_check("all", ["out.txt"], repo=repo, sync=None, out=out) == cc.DIFFERENT
    text = out.getvalue()
    assert "DIFFERENT: out.txt" in text and "-old" in text and "+new" in text
    assert "--- HEAD:out.txt" in text and "+++ regenerated:out.txt" in text


def test_identical_regeneration_exits_zero(tmp_path):
    repo = make_repo(tmp_path, committed="new\n")
    out = io.StringIO()
    assert cc.run_check("all", ["out.txt"], repo=repo, sync=None, out=out) == 0
    assert "identical: out.txt" in out.getvalue()
    # the working tree is untouched: the clone is where the target ran
    assert (repo / "out.txt").read_text() == "new\n"
    assert (
        cc.committed_bytes(repo, "out.txt") == b"new\n" and cc.committed_bytes(repo, "nope") is None
    )


def test_missing_files_are_compared_as_absence(tmp_path):
    # absent in HEAD and in the clone (output still pending): consistent, reported as such
    repo = make_repo(tmp_path, recipe="true")
    out = io.StringIO()
    assert cc.run_check("all", ["gone.txt"], repo=repo, sync=None, out=out) == 0
    assert "identical: gone.txt (absent in both" in out.getvalue()
    # committed but not regenerated: a difference
    out2 = io.StringIO()
    repo2 = make_repo(tmp_path / "b", recipe="rm out.txt")
    assert cc.run_check("all", ["out.txt"], repo=repo2, sync=None, out=out2) == cc.DIFFERENT
    assert "missing in the regenerated clone" in out2.getvalue()
    # regenerated but never committed: a difference too
    out3 = io.StringIO()
    repo3 = make_repo(tmp_path / "c", recipe="printf 'x' > extra.txt")
    assert cc.run_check("all", ["extra.txt"], repo=repo3, sync=None, out=out3) == cc.DIFFERENT
    assert "missing in HEAD" in out3.getvalue()
