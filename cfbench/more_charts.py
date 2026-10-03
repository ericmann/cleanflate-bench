"""Remaining figures drawn from derived tables (SPEC 5 T2 and 2.4).

Each figure function reads its table with `provenance.read_table`. A pending (or empty) table gives
no figure: the function returns None and records the reason in `PENDING_REASONS[name]`. All output
goes through `charts.save_figure`, which adds the parity note.
"""

import sys
from collections import defaultdict
from pathlib import Path

from matplotlib.patches import Rectangle

from cfbench import charts, config, parity, provenance

COLORS = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860", "#DA8BC3", "#8C8C8C"]
PENDING_REASONS: dict[str, str] = {}
UNSAFE_NOTE_C = "C: whole codebase"
OUTCOME_COLORS = {"accept": "#9BD39B", "accept+trailing": "#CFE8A8", "error": "#E8A0A0",
                  "unsupported": "#D8D8D8"}  # fmt: skip


def _table(name: str, figure: str) -> list[dict] | None:
    """Rows of a derived table, or None (with the reason recorded) when pending or absent."""
    try:
        rows, side = provenance.read_table(name)
    except FileNotFoundError:
        PENDING_REASONS[figure] = f"{name}.csv does not exist"
        return None
    if side.get("pending"):
        PENDING_REASONS[figure] = f"{name} is pending: {side['pending']}"
        return None
    if not rows:
        PENDING_REASONS[figure] = f"{name} has no rows"
        return None
    PENDING_REASONS.pop(figure, None)
    return rows


def _save(fig, name: str, note: str, out_dir=None) -> list[Path]:
    return charts.save_figure(fig, name, parity_note=note, size="default", out_dir=out_dir)


def _int(s: str) -> int:
    return int(float(s)) if s != "" else 0


# ---- unsafe counts ---------------------------------------------------------------------------


def unsafe_data(rows: list[dict]) -> tuple[dict[str, tuple[int, int]], list[str]]:
    """({rust subject: (unsafe blocks, unsafe fns)} over its crates, [C subjects])."""
    rust: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    c_subjects = []
    for r in rows:
        if r["unsafe_blocks"] == "" and r["note"].startswith("C:"):
            if r["subject"] not in c_subjects:
                c_subjects.append(r["subject"])
            continue
        rust[r["subject"]][0] += _int(r["unsafe_blocks"])
        rust[r["subject"]][1] += _int(r["unsafe_fns"])
    return {s: (b, f) for s, (b, f) in sorted(rust.items())}, c_subjects


def unsafe_counts(out_dir=None):
    rows = _table("unsafe", "unsafe_counts")
    if rows is None:
        return None
    rust, c_subjects = unsafe_data(rows)
    fig = charts.new_figure("default")
    ax = fig.subplots()
    names = [*rust, *c_subjects]
    for i, s in enumerate(rust):
        blocks, fns = rust[s]
        ax.bar(i, blocks, color=COLORS[0], label="unsafe blocks" if i == 0 else None)
        ax.bar(i, fns, bottom=blocks, color=COLORS[1], label="unsafe fns" if i == 0 else None)
        ax.text(i, blocks + fns, str(blocks + fns), ha="center", va="bottom", fontsize=7)
    for j, _s in enumerate(c_subjects):
        ax.text(len(rust) + j, 0.02, UNSAFE_NOTE_C, rotation=90, ha="center", va="bottom",
                fontsize=7, color="#666666")  # fmt: skip
    ax.set_xticks(range(len(names)), names, fontsize=7)
    ax.set_xlim(-0.6, len(names) - 0.4)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylabel("unsafe blocks and fns (incl. dependencies)", fontsize=7)
    ax.set_ylim(bottom=0, top=max(1, max((b + f for b, f in rust.values()), default=0) * 1.2))
    ax.legend(fontsize=6, frameon=False)
    fig.suptitle("Unsafe code per subject", fontsize=8)
    return _save(fig, "unsafe_counts", parity.PARITY_NOTE, out_dir)


# ---- binary size -----------------------------------------------------------------------------


def size_data(rows: list[dict], machine: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for r in rows:
        if r["machine"] == machine and r["bytes"] != "":
            out[r["subject"]][r["opt"]] = int(float(r["bytes"]))
    return dict(sorted(out.items()))


def binary_size(out_dir=None):
    rows = _table("binary_size", "binary_size")
    if rows is None:
        return None
    cfg = config.load_config("full")
    machines = sorted({r["machine"] for r in rows})
    machine = (
        cfg["paper"]["table_machine"] if cfg["paper"]["table_machine"] in machines else machines[0]
    )
    data = size_data(rows, machine)
    opts = list(cfg["size"]["opt_levels"])
    fig = charts.new_figure("default")
    ax = fig.subplots()
    width = 0.8 / len(opts)
    for k, opt in enumerate(opts):
        xs = [i + (k - (len(opts) - 1) / 2) * width for i in range(len(data))]
        have = [(x, d[opt] / 1024) for x, d in zip(xs, data.values(), strict=True) if opt in d]
        ax.bar([x for x, _ in have], [h for _, h in have], width * 0.9,
               color=COLORS[k], label=f"opt-level {opt}")  # fmt: skip
        for x, d in zip(xs, data.values(), strict=True):
            if opt not in d:  # unmeasured: label the slot, never draw a zero-height bar
                ax.text(x, 0, "n/a", ha="center", va="bottom", fontsize=6, rotation=90)
    ax.set_xticks(range(len(data)), list(data), fontsize=7)
    ax.set_ylabel("stripped minimal decoder binary (KiB)", fontsize=7)
    ax.legend(fontsize=6, frameon=False)
    fig.suptitle(f"Binary size per subject ({machine})", fontsize=8)
    return _save(fig, "binary_size", parity.with_context(machine, "generic"), out_dir)


# ---- effort per stage ------------------------------------------------------------------------


def effort_data(
    rows: list[dict],
) -> tuple[list[str], dict[str, dict[str, int]], dict[str, float | None]]:
    """(rounds, {stage: {round: fresh tokens}}, {round: cost or None}); cache reads excluded."""
    rounds = sorted({r["round"] for r in rows}, key=lambda x: int(x) if x.isdigit() else 10**9)
    tokens: dict[str, dict[str, int]] = defaultdict(dict)
    cost: dict[str, float | None] = dict.fromkeys(rounds)
    for r in rows:
        t = _int(r["input_tokens"]) + _int(r["output_tokens"]) + _int(r["cache_write_tokens"])
        tokens[r["stage"]][r["round"]] = tokens[r["stage"]].get(r["round"], 0) + t
        c = provenance.to_float(r["cost_usd"])
        if c is not None:
            cost[r["round"]] = (cost[r["round"]] or 0.0) + c
    return rounds, dict(sorted(tokens.items())), cost


def effort_cost_per_stage(out_dir=None):
    rows = _table("effort_stage_round", "effort_cost_per_stage")
    if rows is None:
        return None
    rounds, tokens, cost = effort_data(rows)
    fig = charts.new_figure("default")
    ax = fig.subplots()
    bottoms = [0.0] * len(rounds)
    for k, (stage, per_round) in enumerate(tokens.items()):
        vals = [per_round.get(r, 0) / 1e6 for r in rounds]
        ax.bar(range(len(rounds)), vals, bottom=bottoms, color=COLORS[k % len(COLORS)], label=stage)
        bottoms = [b + v for b, v in zip(bottoms, vals, strict=True)]
    ax.set_xticks(range(len(rounds)), [f"round {r}" for r in rounds], fontsize=7)
    ax.set_ylabel("input + output + cache-write tokens (millions)", fontsize=7)
    ax.set_ylim(top=max(bottoms, default=1) * 1.3)
    ax.tick_params(axis="y", labelsize=7)
    ax.legend(fontsize=6, ncol=4, frameon=False, loc="upper left")
    priced = [r for r in rounds if cost[r] is not None]
    if priced:
        ax2 = ax.twinx()
        ax2.plot([rounds.index(r) for r in priced], [cost[r] for r in priced], "k.-")
        ax2.set_ylabel("cost (USD)", fontsize=7)
    fig.suptitle("Effort per stage and round (cache reads excluded)", fontsize=8)
    return _save(fig, "effort_cost_per_stage", parity.PARITY_NOTE, out_dir)


# ---- malformed highlights --------------------------------------------------------------------


def outcome_class(outcome: str) -> str:
    return "error" if outcome.startswith("error") else outcome


def malformed_grid(
    matrix: list[dict], disagreements: list[dict]
) -> tuple[list[str], list[str], dict]:
    """(rows, subjects, {(row, subject): outcome}) restricted to disagreement files.

    With a `machine` column a row is `file (machine)`, so each machine's outcomes stay separate.
    """

    def label(r: dict) -> str:
        return f"{r['file']} ({r['machine']})" if r.get("machine") else r["file"]

    files = list(dict.fromkeys(label(d) for d in disagreements))
    by_machine = any(d.get("machine") for d in disagreements)
    subjects: list[str] = []
    cell = {}
    for r in matrix:
        key = label(r) if by_machine else r["file"]
        if key in files:
            if r["subject"] not in subjects:
                subjects.append(r["subject"])
            cell[(key, r["subject"])] = r["outcome"]
    return files, subjects, cell


def malformed_highlights(out_dir=None):
    matrix = _table("malformed_matrix", "malformed_highlights")
    dis = _table("malformed_disagreements", "malformed_highlights")
    if matrix is None or dis is None:
        return None
    files, subjects, cell = malformed_grid(matrix, dis)
    fig = charts.new_figure("default")
    ax = fig.subplots()
    for i, f in enumerate(files):
        for j, s in enumerate(subjects):
            o = cell.get((f, s), "unsupported")
            ax.add_patch(_rect(j, i, OUTCOME_COLORS[outcome_class(o)]))
            ax.text(j + 0.5, i + 0.5, o.replace("error:", ""), ha="center", va="center", fontsize=5)
    ax.set_xlim(0, len(subjects))
    ax.set_ylim(len(files), 0)
    ax.set_xticks([j + 0.5 for j in range(len(subjects))], subjects, fontsize=7)
    ax.set_yticks([i + 0.5 for i in range(len(files))], files, fontsize=6)
    fig.suptitle("Malformed inputs where subjects disagree on accept versus reject", fontsize=8)
    return _save(fig, "malformed_highlights", parity.PARITY_NOTE, out_dir)


def _rect(x: int, y: int, color: str):
    return Rectangle((x, y), 1, 1, facecolor=color, edgecolor="white")


# ---- fuzz statistics -------------------------------------------------------------------------


def fuzz_stats(out_dir=None):
    rows = _table("fuzz_stats", "fuzz_stats")
    if rows is None:
        return None
    targets = [f"{r['target']} ({r['machine']})" for r in rows]
    fig = charts.new_figure("default")
    ax1, ax2 = fig.subplots(1, 2)
    ax1.bar(range(len(rows)), [_int(r["executions"]) / 1e6 for r in rows], color=COLORS[0])
    ax1.set_ylabel("executions (millions)", fontsize=7)
    ax2.bar(range(len(rows)), [_int(r["divergences"]) for r in rows], color=COLORS[3])
    ax2.set_ylabel("divergences", fontsize=7)
    for ax in (ax1, ax2):
        ax.set_xticks(range(len(rows)), targets, fontsize=6, rotation=20, ha="right")
    fig.suptitle("Differential fuzzing: executions and divergences", fontsize=8)
    return _save(fig, "fuzz_stats", parity.PARITY_NOTE, out_dir)


# ---- checksum throughput ---------------------------------------------------------------------


def checksum_series(
    rows: list[dict], machine: str
) -> dict[tuple[str, str], list[tuple[int, float]]]:
    out: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    for r in rows:
        v = provenance.to_float(r["median_gib_s"])
        if r["machine"] == machine and v is not None:
            out[(r["subject"], r["algo"])].append((int(r["size"]), v))
    return {k: sorted(v) for k, v in sorted(out.items())}


def checksum_throughput(out_dir=None):
    rows = _table("checksums", "checksum_throughput")
    if rows is None:
        return None
    saved = []
    for machine in sorted({r["machine"] for r in rows}):
        series = checksum_series(rows, machine)
        if not series:
            continue
        fig = charts.new_figure("default")
        ax = fig.subplots()
        subjects = sorted({s for s, _a in series})
        styles = {"adler32": "-", "crc32": "--"}
        for (s, algo), pts in series.items():
            ax.plot([p[0] for p in pts], [p[1] for p in pts], styles.get(algo, ":"),
                    color=COLORS[subjects.index(s) % len(COLORS)], marker="o", markersize=3,
                    label=f"{s} {algo}")  # fmt: skip
        ax.set_xscale("log")
        ax.set_xlabel("input size (bytes)", fontsize=7)
        ax.set_ylabel("throughput (GiB/s)", fontsize=7)
        ax.legend(fontsize=5, ncol=3, frameon=False, loc="upper left")
        fig.suptitle(f"Checksum throughput ({machine})", fontsize=8)
        saved += _save(
            fig, f"checksum_throughput_{machine}", parity.with_context(machine, "generic"), out_dir
        )
    if not saved:
        PENDING_REASONS["checksum_throughput"] = "checksums has no measured rows"
        return None
    return saved


FIGURES = {
    "unsafe_counts": unsafe_counts,
    "binary_size": binary_size,
    "effort_cost_per_stage": effort_cost_per_stage,
    "malformed_highlights": malformed_highlights,
    "fuzz_stats": fuzz_stats,
    "checksum_throughput": checksum_throughput,
}


def render_all(out_dir=None) -> dict[str, list[Path] | None]:
    return {name: fn(out_dir) for name, fn in FIGURES.items()}


def main() -> int:
    for name, paths_ in render_all().items():
        if paths_ is None:
            print(f"{name}: pending ({PENDING_REASONS.get(name, 'no data')})")
        else:
            print(f"{name}: " + ", ".join(p.name for p in paths_))
    return 0


if __name__ == "__main__":
    sys.exit(main())
