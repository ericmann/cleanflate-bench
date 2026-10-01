"""Deterministic CSV tables with provenance sidecars (SPEC 1, 4 and 6)."""

import csv
import hashlib
import json
from pathlib import Path

from cfbench import paths, rawio


def fmt(x) -> str:
    """Format a cell value: floats as `.6g`, None as empty, everything else via str."""
    if x is None:
        return ""
    if isinstance(x, bool):
        return str(x).lower()
    if isinstance(x, float):
        return format(x, ".6g")
    return str(x)


def _sort_key(value):
    if value is None:
        return (0, 0.0, "")
    if isinstance(value, bool):
        return (1, float(value), "")
    if isinstance(value, (int, float)):
        return (1, float(value), "")
    return (2, 0.0, str(value))


def _rel(p: Path) -> str:
    p = Path(p)
    try:
        return p.resolve().relative_to(paths.ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def table_path(name: str, results_dir: Path | None = None) -> Path:
    return (results_dir or paths.RESULTS) / f"{name}.csv"


def sidecar_path(name: str, results_dir: Path | None = None) -> Path:
    return (results_dir or paths.RESULTS) / f"{name}.csv.provenance.json"


def _raw_entry(p: Path) -> dict:
    doc = rawio.load_raw(p)
    return {
        "path": _rel(p),
        "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(),
        "machine": doc["machine"],
        "timestamp": doc["timestamp"],
    }


def write_table(
    name: str,
    columns: list[str],
    rows: list[dict],
    *,
    script: str,
    raw_files: list[Path],
    pending: str | None = None,
) -> Path:
    """Write `results/<name>.csv` and its sidecar. Same inputs give byte-identical files."""
    ordered = sorted(rows, key=lambda r: tuple(_sort_key(r.get(c)) for c in columns))
    out = table_path(name)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in ordered:
            w.writerow([fmt(r.get(c)) for c in columns])
    entries = sorted((_raw_entry(p) for p in raw_files), key=lambda e: e["path"])
    sidecar = {
        "table": f"{name}.csv",
        "script": script,
        "columns": list(columns),
        "raw_files": entries,
        "pending": pending,
    }
    with open(sidecar_path(name), "w", encoding="utf-8") as f:
        json.dump(sidecar, f, sort_keys=True, indent=1)
        f.write("\n")
    return out


def read_table(name: str, results_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Rows as dicts of strings (empty cells are ''), plus the parsed sidecar."""
    with open(table_path(name, results_dir), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    with open(sidecar_path(name, results_dir), encoding="utf-8") as f:
        sidecar = json.load(f)
    return rows, sidecar


def to_float(s: str) -> float | None:
    return float(s) if s != "" else None
