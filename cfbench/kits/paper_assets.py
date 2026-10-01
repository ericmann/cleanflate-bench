"""The paper kit's one table (at most six rows) and one paper-sized figure (SPEC 5 T1, 2.4)."""

from dataclasses import dataclass, field
from pathlib import Path

from matplotlib.patches import Patch

from cfbench import charts, config, parity, paths, trajectory
from cfbench.kits import evidence as ev
from cfbench.kits.evidence import Evidence, MissingData

SUBJECTS = ["cf", "zlib", "mox"]
PENDING = "pending"
NA = "n/a"
MAX_ROWS = 6


@dataclass(frozen=True)
class Cell:
    display: str
    evidence: list[Evidence] = field(default_factory=list)
    status: str = "ok"  # ok, pending or n/a
    reason: str = ""


@dataclass(frozen=True)
class Row:
    label: str
    cells: dict[str, Cell]


@dataclass(frozen=True)
class PaperTable:
    columns: list[str]
    rows: list[Row]
    footnote: str

    def to_markdown(self) -> str:
        head = "| " + " | ".join(["Metric", *self.columns]) + " |"
        sep = "|" + "|".join(["---"] * (len(self.columns) + 1)) + "|"
        body = [
            "| " + " | ".join([r.label, *[r.cells[c].display for c in self.columns]]) + " |"
            for r in self.rows
        ]
        return "\n".join([head, sep, *body, "", f"*{self.footnote}*"])


def _pending(e: MissingData) -> Cell:
    return Cell(PENDING, [], "pending", str(e))


def _unsupported(d, machine: str, subject: str, framing: str, cfg: dict) -> bool:
    """True when perf_cells records the subject's framing as unsupported (n/a, never zero)."""
    p = cfg["paper"]
    try:
        rows, _ = ev.table_rows("perf_cells", d)
    except MissingData:
        return False
    return any(
        r["machine"] == machine and r["variant"] == p["perf_variant"] and r["subject"] == subject
        and r["framing"] == framing and r["status"] == "unsupported"
        for r in rows
    )  # fmt: skip


def _perf_cell(d, cfg, machine: str, subject: str, framing: str, with_mibs: bool) -> Cell:
    p = cfg["paper"]
    key = {"machine": machine, "variant": p["perf_variant"], "subject": subject, "corpus": p["figure_corpus"],
           "level": p["figure_level"], "framing": framing, "mode": p["figure_mode"]}  # fmt: skip
    try:
        ratio = ev.lookup("perf_aggregates", key, "ratio_vs_zlib", results_dir=d, fmt="{:.2f}x")
        if not with_mibs:
            return Cell(ratio.display, [ratio])
        mibs = ev.lookup("perf_aggregates", key, "agg_mib_s", results_dir=d, fmt="{:.0f}")
    except MissingData as e:
        if _unsupported(d, machine, subject, framing, cfg):
            return Cell(NA, [], "n/a", f"{subject} does not support {framing} framing")
        return _pending(e)
    return Cell(f"{mibs.display} MiB/s ({ratio.display})", [mibs, ratio])


def _unsafe_cell(d, subject: str) -> Cell:
    if subject == "zlib":
        return Cell("C (whole codebase)", [], "ok", "memory-unsafe by language")
    key = {"subject": subject, "role": "subject"}
    try:
        blocks = ev.lookup("unsafe", key, "unsafe_blocks", results_dir=d, fmt="{:.0f}")
        fns = ev.lookup("unsafe", key, "unsafe_fns", results_dir=d, fmt="{:.0f}")
    except MissingData as e:
        return _pending(e)
    return Cell(f"{blocks.display} blocks + {fns.display} fns", [blocks, fns])


def _deps_cell(d, subject: str) -> Cell:
    if subject == "zlib":
        return Cell(NA, [], "n/a", "dependencies are measured for the Rust subjects only")
    try:
        direct = ev.lookup(
            "deps", {"subject": subject}, "direct_count", results_dir=d, fmt="{:.0f}"
        )
        trans = ev.lookup(
            "deps", {"subject": subject}, "transitive_count", results_dir=d, fmt="{:.0f}"
        )
    except MissingData as e:
        return _pending(e)
    return Cell(f"{direct.display} direct / {trans.display} transitive", [direct, trans])


def _binary_cell(d, cfg, subject: str) -> Cell:
    p = cfg["paper"]
    try:
        e = ev.lookup("binary_size", {"machine": p["table_machine"], "subject": subject, "opt": p["table_opt"]},
                      "bytes", results_dir=d, fmt="{:,.0f}")  # fmt: skip
    except MissingData as err:
        return _pending(err)
    return Cell(f"{e.display} B", [e])


def build_table(results_dir: Path | None = None, cfg: dict | None = None) -> PaperTable:
    d = Path(results_dir) if results_dir else paths.RESULTS
    cfg = cfg or config.load_config("full")
    p = cfg["paper"]
    m_a, m_b = p["machines"][0], p["machines"][-1]
    corpus = p["figure_corpus"].title()
    rows = [
        Row(f"{corpus} raw L{p['figure_level']} one-shot, {m_a}: MiB/s (vs zlib)",
            {s: _perf_cell(d, cfg, m_a, s, "raw", True) for s in SUBJECTS}),
        Row(f"{corpus} raw L{p['figure_level']} one-shot, {m_b}: MiB/s (vs zlib)",
            {s: _perf_cell(d, cfg, m_b, s, "raw", True) for s in SUBJECTS}),
        Row(f"{corpus} gzip L{p['figure_level']} one-shot, {m_b}: ratio vs zlib",
            {s: _perf_cell(d, cfg, m_b, s, "gzip", False) for s in SUBJECTS}),
        Row("`unsafe` blocks + fns in the decompression crate", {s: _unsafe_cell(d, s) for s in SUBJECTS}),
        Row("Runtime dependencies (direct / transitive)", {s: _deps_cell(d, s) for s in SUBJECTS}),
        Row(f"Stripped minimal binary, opt-level {p['table_opt']}, {p['table_machine']}",
            {s: _binary_cell(d, cfg, s) for s in SUBJECTS}),
    ]  # fmt: skip
    assert len(rows) <= MAX_ROWS
    return PaperTable(SUBJECTS, rows, parity.PARITY_NOTE)


# ---- figure -------------------------------------------------------------------------------------


def _bar_data(d, cfg) -> tuple[dict, list[Evidence], list[str]]:
    """{machine: {subject: (agg_mib_s, unsafe label)}}, evidence list and pending reasons."""
    p = cfg["paper"]
    data, evid, pending = {}, [], []
    labels = {}
    for s in p["figure_subjects"]:
        c = _unsafe_cell(d, s)
        labels[s] = (
            "C"
            if s == "zlib"
            else (f"unsafe: {c.evidence[0].display}" if c.evidence else "unsafe: ?")
        )
        # annotate with blocks + fns when both are known
        if len(c.evidence) == 2:
            labels[s] = f"unsafe: {int(c.evidence[0].value + c.evidence[1].value)}"
        evid += c.evidence
    for m in p["machines"]:
        per = {}
        for s in p["figure_subjects"]:
            key = {"machine": m, "variant": p["perf_variant"], "subject": s, "corpus": p["figure_corpus"],
                   "level": p["figure_level"], "framing": p["figure_framing"], "mode": p["figure_mode"]}  # fmt: skip
            try:
                e = ev.lookup("perf_aggregates", key, "agg_mib_s", results_dir=d, fmt="{:.0f}")
            except MissingData as err:
                pending.append(f"{m} {s}: {err}")
                continue
            evid.append(e)
            per[s] = (e.value, labels[s])
        if per:
            data[m] = per
    return data, evid, pending


def draw_bars(data: dict, cfg: dict):
    p = cfg["paper"]
    subjects = p["figure_subjects"]
    colors = ["#4C72B0", "#55A868", "#DD8452"]
    fig = charts.new_figure("paper")
    ax = fig.subplots()
    width = 0.8 / len(subjects)
    machines = p["machines"]
    for gi, m in enumerate(machines):
        per = data.get(m)
        if not per:
            ax.text(
                gi,
                0.02,
                "pending",
                ha="center",
                va="bottom",
                fontsize=6,
                color="#666666",
                rotation=90,
            )
            continue
        for si, s in enumerate(subjects):
            x = gi + (si - (len(subjects) - 1) / 2) * width
            if s not in per:
                ax.text(
                    x,
                    0.02,
                    "pending",
                    ha="center",
                    va="bottom",
                    fontsize=5,
                    color="#666666",
                    rotation=90,
                )
                continue
            v, label = per[s]
            ax.bar(x, v, width * 0.9, color=colors[si % len(colors)])
            ax.text(x, v, label, ha="center", va="bottom", fontsize=5)
    top = max((v for per in data.values() for v, _ in per.values()), default=1.0)
    ax.set_ylim(0, top * 1.15)
    ax.set_xticks(range(len(machines)), machines, fontsize=7)
    ax.set_ylabel(
        f"{p['figure_corpus'].title()} {p['figure_framing']} L{p['figure_level']} MiB/s", fontsize=6
    )
    ax.tick_params(axis="y", labelsize=6)
    handles = [Patch(color=colors[i % len(colors)], label=s) for i, s in enumerate(subjects)]
    ax.legend(
        handles=handles,
        fontsize=5,
        ncol=len(subjects),
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        frameon=False,
    )
    return fig


def build_figure(
    results_dir: Path | None = None, out_dir: Path | None = None, cfg: dict | None = None
):
    """Write the paper figure; returns (paths or None, evidence list, pending reasons)."""
    d = Path(results_dir) if results_dir else paths.RESULTS
    cfg = cfg or config.load_config("full")
    p = cfg["paper"]
    left: list[str] = []
    if p["figure"] == "trajectory":
        machine = p["machines"][0]
        try:
            rows, _ = ev.table_rows("trajectory", d)
        except MissingData as e:
            return None, [], [str(e)]
        typed = [{**r, "round": int(r["round"]), "level": int(r["level"]),
                  "ratio_vs_zlib": float(r["ratio_vs_zlib"]) if r["ratio_vs_zlib"] else None} for r in rows]  # fmt: skip
        series = trajectory.figure_series(typed, machine)
        if not series:
            return None, [], [f"no trajectory ratios for {machine}: run `make trajectory`"]
        tags = {int(r["round"]): r["tag"] for r in rows}
        fig = trajectory.draw(series, tags, machine, size="paper")
        name = f"trajectory_{machine}"
        evid: list[Evidence] = []
    else:
        data, evid, pending = _bar_data(d, cfg)
        if not data:
            return None, evid, pending
        fig = draw_bars(data, cfg)
        name = "paper_throughput_unsafe"
        left = pending
    out = charts.save_figure(
        fig, name, parity_note=parity.PARITY_NOTE, size="paper", out_dir=out_dir
    )
    return out, evid, left
