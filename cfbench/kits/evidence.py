"""Evidence for every number a kit prints: table row, raw files and script (SPEC 1, 6).

An `Evidence` can only be built by `lookup`, which reads a derived table and its provenance
sidecar. Kits print numbers only through `Evidence.display`.
"""

from dataclasses import dataclass
from pathlib import Path

from cfbench import provenance

TARGETS = {
    "conformance": "make conformance",
    "conformance_disagreements": "make conformance",
    "unsafe": "make size",
    "deps": "make size",
    "binary_size": "make size",
    "perf_aggregates": "make perf",
    "perf_cells": "make perf",
    "perf_agreement_summary": "make perf",
    "trajectory": "make trajectory",
    "similarity_summary": "make similarity",
    "effort_totals": "make effort",
    "framing_overhead": "make framing",
    "framing_hypothesis": "make framing",
    "malformed_matrix": "make malformed",
    "malformed_disagreements": "make malformed",
    "fuzz_stats": "make fuzz",
    "fuzz_divergences": "make fuzz",
    "bombs": "make bombs",
    "effort_denied": "make effort",
    "effort_stage_round": "make effort",
    "checksums": "make checksums",
    "content_hypotheses": "make content",
    "loc": "make size",
    "complexity": "make size",
}
_TOKEN = object()


class MissingData(Exception):
    """The evidence is not available; the message names the make target to run."""


@dataclass(frozen=True)
class Evidence:
    value: float | str
    display: str
    table: str
    row_key: tuple
    column: str
    raw_files: tuple[str, ...]
    script: str
    cell: str
    _token: object = None

    def __post_init__(self):
        if self._token is not _TOKEN:
            raise TypeError("Evidence can only be built by evidence.lookup()")

    def source(self) -> str:
        """`table[key].column (script, raw files)`, for the evidence list of a kit."""
        key = ", ".join(f"{k}={v}" for k, v in self.row_key)
        return f"{self.table}.csv [{key}] {self.column} <- {self.script} <- {', '.join(self.raw_files) or 'no raw file'}"


def _format(value, fmt) -> str:
    if callable(fmt):
        return fmt(value)
    if fmt is not None:
        return fmt.format(value)
    return provenance.fmt(value)


def table_rows(table: str, results_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Rows and sidecar of a derived table; MissingData when absent or pending."""
    try:
        rows, side = provenance.read_table(table, results_dir)
    except FileNotFoundError:
        raise MissingData(
            f"table {table} is missing: run `{TARGETS.get(table, 'make all')}`"
        ) from None
    if side.get("pending"):
        raise MissingData(f"table {table} is pending: {side['pending']}")
    return rows, side


def lookup(
    table: str,
    where: dict,
    column: str,
    *,
    results_dir: Path | None = None,
    fmt=None,
    transform=None,
) -> Evidence:
    """The single cell `column` of the row of `table` matching `where` (compared as text)."""
    rows, side = table_rows(table, results_dir)
    want = {k: str(v) for k, v in where.items()}
    hits = [r for r in rows if all(r.get(k) == v for k, v in want.items())]
    if not hits:
        raise MissingData(f"no row {where} in {table}: run `{TARGETS.get(table, 'make all')}`")
    if len(hits) > 1:
        raise MissingData(f"{len(hits)} rows match {where} in {table}; the key is not unique")
    cell = hits[0].get(column)
    if cell is None:
        raise MissingData(f"table {table} has no column {column}")
    if cell == "":
        raise MissingData(f"{table} {where} {column} is empty (not measured)")
    try:
        value: float | str = float(cell)
    except ValueError:
        value = cell
    if transform is not None and isinstance(value, float):
        value = transform(value)
    return Evidence(
        value=value,
        display=_format(value, fmt),
        table=table,
        row_key=tuple(sorted(want.items())),
        column=column,
        raw_files=tuple(e["path"] for e in side["raw_files"]),
        script=side["script"],
        cell=cell,
        _token=_TOKEN,
    )
