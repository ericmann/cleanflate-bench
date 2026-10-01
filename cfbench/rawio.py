"""Raw-data envelope I/O. The only module (with env.py) that reads the wall clock."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from cfbench import paths

SCHEMA = "cfbench.raw/1"


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(paths.ROOT), *args], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def bench_git() -> dict:
    sha = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return {"sha": sha, "dirty": None if status is None else bool(status)}


def _root(profile: str) -> Path:
    return paths.RAW if profile == "full" else paths.SMOKE


def write_raw(
    category: str,
    payload: dict,
    *,
    machine: str,
    profile: str,
    script: str,
    environment: dict | None,
    session: str | None = None,
    run_index: int | None = None,
) -> Path:
    stamp = utc_timestamp()
    d = _root(profile) / category / machine
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{stamp}.json"
    n = 1
    while path.exists():
        path = d / f"{stamp}-{n}.json"
        n += 1
    doc = {
        "schema": SCHEMA,
        "category": category,
        "machine": machine,
        "profile": profile,
        "timestamp": stamp,
        "session": session,
        "run_index": run_index,
        "script": script,
        "argv": list(sys.argv),
        "bench_git": bench_git(),
        "environment": environment,
        "payload": payload,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, sort_keys=True, indent=1)
        f.write("\n")
    return path


def load_raw(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path}: unexpected schema {doc.get('schema')!r}")
    return doc


def list_raw(
    category: str, machine: str | None = None, profile: str = "full", kind: str | None = None
) -> list[Path]:
    base = _root(profile) / category
    if not base.is_dir():
        return []
    machines = [machine] if machine else sorted(p.name for p in base.iterdir() if p.is_dir())
    out = []
    for m in machines:
        out.extend(sorted((base / m).glob("*.json")))
    if kind is not None:
        out = [p for p in out if load_raw(p)["payload"].get("kind") == kind]
    return sorted(out)


def latest_session(
    category: str, machine: str, kind: str | None = None, profile: str = "full"
) -> list[dict]:
    docs = [load_raw(p) for p in list_raw(category, machine=machine, profile=profile, kind=kind)]
    docs = [d for d in docs if d["session"] is not None]
    if not docs:
        return []
    newest = max(docs, key=lambda d: (d["timestamp"], d["session"]))["session"]
    same = [d for d in docs if d["session"] == newest]
    return sorted(same, key=lambda d: d["run_index"] if d["run_index"] is not None else 0)
