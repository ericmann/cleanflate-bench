"""Read-only access to the pinned cleanflate clone and its corpora.

Git operations here are limited to clone, fetch, checkout (detached), rev-parse,
status, log and show. Nothing in this module modifies cleanflate history or sources.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from cfbench import config, paths


class SourceError(RuntimeError):
    pass


def clone_path() -> Path:
    return paths.THIRD_PARTY / "cleanflate"


def rounds() -> dict:
    return config.load_json("rounds.json")


def primary_sha() -> str:
    r = rounds()
    return next(x["sha"] for x in r["rounds"] if x["round"] == r["primary_round"])


def git(path: Path, *args: str, check: bool = True) -> str:
    out = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=False
    )
    if check and out.returncode != 0:
        raise SourceError(f"git {' '.join(args)} failed in {path}: {out.stderr.strip()}")
    return out.stdout.strip()


def _has_commit(path: Path, sha: str) -> bool:
    out = subprocess.run(
        ["git", "-C", str(path), "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    return out.returncode == 0


def verify_tags(path: Path) -> None:
    bad = []
    for r in rounds()["rounds"]:
        got = git(path, "rev-parse", f"{r['tag']}^{{commit}}", check=False)
        if got != r["sha"]:
            bad.append(f"{r['tag']}: expected {r['sha']}, got {got or 'missing'}")
    if bad:
        raise SourceError("tag/SHA mismatch: " + "; ".join(bad))


def ensure_clone(path: Path | None = None, url: str | None = None) -> Path:
    path = path or clone_path()
    url = url or os.environ.get("CFB_CLEANFLATE_URL") or rounds()["repo_url"]
    sha = primary_sha()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", url, str(path)], check=True)
    pinned = [r["sha"] for r in rounds()["rounds"]]
    if not all(_has_commit(path, s) for s in pinned):
        git(path, "fetch", "--tags", "origin")
    git(path, "checkout", "--detach", sha)
    verify_tags(path)
    return path


def pristine_check(path: Path | None = None) -> list[str]:
    path = path or clone_path()
    problems = []
    head = git(path, "rev-parse", "HEAD")
    if head != primary_sha():
        problems.append(f"HEAD {head} differs from pinned {primary_sha()}")
    status = git(path, "status", "--porcelain")
    if status:
        problems.append("working tree not clean: " + status.replace("\n", "; "))
    return problems


def ensure_corpora(path: Path | None = None) -> None:
    path = path or clone_path()
    env = dict(os.environ, CLEANROOM_ALLOW_CORPUS_FETCH="1")
    subprocess.run(
        ["bash", "tools/cleanroom/fetch-corpora.sh", "all"], cwd=path, env=env, check=True
    )
    problems = pristine_check(path)
    if problems:
        raise SourceError("clone not pristine after corpus fetch: " + "; ".join(problems))


def corpus_files(corpus: str, path: Path | None = None) -> list[tuple[str, Path, str, int]]:
    path = path or clone_path()
    with open(path / "testdata" / "corpora" / "SOURCES.json", encoding="utf-8") as f:
        sources = json.load(f)
    base = path / "testdata" / "corpora" / corpus
    out = []
    for e in sources[corpus]["files"]:
        out.append((e["name"], base / e["name"], e["sha256"], int(e["bytes"])))
    return sorted(out)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    try:
        if cmd == "fetch":
            ensure_clone()
            ensure_corpora()
        elif cmd == "check":
            problems = pristine_check()
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
        else:
            print("usage: cleanflate_src fetch|check", file=sys.stderr)
            return 2
    except (SourceError, subprocess.CalledProcessError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
