"""Clean-clone regeneration check (SPEC 7 B5 and 4).

`python -m cfbench.clean_clone <target> [--compare <paths...>]` clones HEAD into a temporary
directory, installs the locked environment, runs `make <target>` there and compares each listed path
(directories recursively) with its committed version. A difference exits non-zero with a unified diff. Uncommitted changes in
the working tree are refused because the check is against HEAD.
"""

import argparse
import difflib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cfbench import paths

DIRTY = 2
DIFFERENT = 1
SYNC = ["uv", "sync", "--frozen"]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def dirty_paths(repo: Path, ignore: tuple[str, ...] = ()) -> list[str]:
    """Porcelain lines (tracked changes and untracked files) not covered by `ignore`."""
    out = _git(repo, "status", "--porcelain").stdout.splitlines()
    return [ln for ln in out if not any(ln[3:].strip().startswith(i) for i in ignore)]


def committed_bytes(repo: Path, rel: str) -> bytes | None:
    res = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{rel}"], capture_output=True, check=False
    )
    return res.stdout if res.returncode == 0 else None


def tracked_files(repo: Path, rel: str) -> list[str]:
    """Files tracked at HEAD under `rel` (the path itself when it is a file)."""
    res = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD", "--", rel],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    return [ln for ln in res.stdout.splitlines() if ln]


def expand(repo: Path, clone: Path, rel: str) -> list[str]:
    """A compared path as files: tracked ones under it plus any the clone generated (recursive)."""
    found = set(tracked_files(repo, rel))
    target = clone / rel
    if target.is_dir():
        found |= {p.relative_to(clone).as_posix() for p in target.rglob("*") if p.is_file()}
    elif not found:
        found.add(rel)  # absent in HEAD: compared as absence, or as a single new file
    return sorted(found)


def run_check(
    target: str,
    compare: list[str],
    repo: Path | None = None,
    ignore_dirty: tuple[str, ...] = (),
    sync: list[str] | None = SYNC,
    keep: bool = False,
    out=sys.stdout,
) -> int:
    repo = repo or paths.ROOT
    dirty = dirty_paths(repo, ignore_dirty)
    if dirty:
        print(
            "refused: uncommitted changes in the working tree (the check is against HEAD):",
            file=out,
        )
        print("\n".join(dirty), file=out)
        return DIRTY
    tmp = Path(tempfile.mkdtemp(prefix="cfb-clean-clone-"))
    try:
        clone = tmp / "clone"
        res = subprocess.run(
            ["git", "clone", "--local", "--no-hardlinks", "-q", str(repo), str(clone)], check=False
        )
        if res.returncode != 0:
            print("git clone failed", file=out)
            return DIFFERENT
        if sync:
            subprocess.run(sync, cwd=clone, check=True)
        subprocess.run(["make", target], cwd=clone, check=True)
        status = 0
        for rel in [f for arg in compare for f in expand(repo, clone, arg)]:
            fresh = (clone / rel).read_bytes() if (clone / rel).exists() else None
            want = committed_bytes(repo, rel)
            if fresh == want:
                note = (
                    " (absent in both: not generated yet, e.g. pending data)"
                    if want is None
                    else ""
                )
                print(f"identical: {rel}{note}", file=out)
                continue
            status = DIFFERENT
            print(f"DIFFERENT: {rel}", file=out)
            a = (want or b"").decode("utf-8", errors="replace").splitlines(keepends=True)
            b = (fresh or b"").decode("utf-8", errors="replace").splitlines(keepends=True)
            print("  missing in " + ("HEAD" if want is None else "the regenerated clone"), file=out)
            out.writelines(difflib.unified_diff(a, b, f"HEAD:{rel}", f"regenerated:{rel}"))
        return status
    finally:
        if keep:
            print(f"kept {tmp}", file=out)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--compare", nargs="*", default=[])
    ap.add_argument(
        "--ignore-dirty", nargs="*", default=[], help="path prefixes to ignore in the dirty check"
    )
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    return run_check(a.target, a.compare, ignore_dirty=tuple(a.ignore_dirty), keep=a.keep)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
