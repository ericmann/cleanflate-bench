"""RESULTS.md, part 1: methodology and results for SPEC 3.1 to 3.5 (SPEC 5 T3, 6).

`render_sections_part1()` returns Markdown for: environments, subjects and pins, performance
methodology and results, framing decomposition, content analysis and trajectory. Tables are copied
from derived tables read through `kits.evidence.table_rows` (which refuses pending tables), each
followed by a source line (table, raw files, script). Pending data becomes an explicit
"Pending: run `make X` on M-Y" paragraph. Figures are embedded relative to `results/`.
"""

import json
from pathlib import Path

from cfbench import config, paths, rawio
from cfbench.kits import evidence as ev
from cfbench.kits.evidence import MissingData
from cfbench.parity import PARITY_NOTE

MACHINES = "M-A and M-B"


def pending(table: str, machines: str = MACHINES, detail: str = "") -> str:
    target = ev.TARGETS.get(table, "make all")
    extra = f" ({detail})" if detail else ""
    return f"Pending: run `{target}` on {machines}.{extra}"


def md_table(columns: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(columns) + " |"
    sep = "|" + "|".join(["---"] * len(columns)) + "|"
    body = ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def source(table: str, side: dict) -> str:
    raws = ", ".join(f"`{e['path']}`" for e in side["raw_files"]) or "no raw file"
    return f"*Source: `results/{table}.csv` <- {raws} via `{side['script']}`.*"


def num(s: str, digits: int = 2) -> str:
    """Display a table cell: empty is n/a, numbers get fixed digits."""
    if s == "":
        return "n/a"
    try:
        return f"{float(s):.{digits}f}"
    except ValueError:
        return s


def figure(name: str, caption: str, d: Path, note: str = PARITY_NOTE) -> str:
    """Embed a figure from results/figures with its caption and the parity note."""
    if not (d / "figures" / f"{name}.png").exists():
        return f"Pending: figure `{name}` is not rendered yet (run `make figures` once its table has data)."
    return f"![{caption}](figures/{name}.png)\n\n*{caption}* {note}"


def section(title: str, *blocks: str) -> str:
    return "\n\n".join([f"## {title}", *[b for b in blocks if b]])


# ---- environments and pins ------------------------------------------------------------------


def environments(d: Path) -> str:
    newest: dict[str, dict] = {}
    for p in rawio.list_raw("env"):
        doc = rawio.load_raw(p)
        cap = doc["payload"].get("capture") or {}
        m = cap.get("machine") or doc["machine"]
        if m not in newest or doc["timestamp"] > newest[m]["timestamp"]:
            newest[m] = {"timestamp": doc["timestamp"], "cap": cap, "path": p}
    if not newest:
        return section("Environments", pending("env"))
    rows = []
    for m in sorted(newest):
        c = newest[m]["cap"]
        cores = c.get("cores") or {}
        os_ = c.get("os") or {}
        rows.append([m, c.get("cpu_model", "n/a"), f"{cores.get('physical', 'n/a')} / {cores.get('logical', 'n/a')}",
                     " ".join(x for x in (os_.get("name"), os_.get("version")) if x) or "n/a",
                     c.get("kernel", "n/a"), c.get("governor") or "n/a"])  # fmt: skip
    srcs = ", ".join(
        f"`{newest[m]['path'].relative_to(paths.ROOT) if newest[m]['path'].is_relative_to(paths.ROOT) else newest[m]['path']}`"
        for m in sorted(newest)
    )
    missing = [m for m in ("M-A", "M-B") if m not in newest]
    return section(
        "Environments",
        md_table(
            ["Machine", "CPU", "Cores (physical / logical)", "OS", "Kernel", "Governor"], rows
        ),
        f"*Source: raw env captures {srcs}.*",
        pending("env", " and ".join(missing)) if missing else "",
    )


def subjects_and_pins(lock_path: Path | None = None) -> str:
    p = lock_path or paths.ROOT / "subjects.lock.json"
    if not p.exists():
        return section(
            "Subjects and pins", "Pending: run `make pins` (writes `subjects.lock.json`)."
        )
    lock = json.loads(p.read_text(encoding="utf-8"))
    blocks = []
    for m, info in sorted(lock["machines"].items()):
        rows = []
        for name, b in sorted(info["builds"].items()):
            hw = b.get("hw_crc") or {}
            rows.append([name, b.get("compiler_version") or b.get("compiler", "n/a"), b.get("target_cpu", "n/a"),
                         "yes" if hw.get("compiled_in") else "no",
                         "yes" if hw.get("runtime_dispatch") else "no"])  # fmt: skip
        blocks.append(
            f"**{m}**\n\n"
            + md_table(
                ["Build", "Compiler", "Target CPU", "Hardware CRC compiled in", "Runtime dispatch"],
                rows,
            )
        )
    note = (
        "Hardware-CRC determinations come from disassembly and symbol inspection of each built "
        "binary (`subjects.lock.json`); on x86_64 the `zlib-nohw` control is identical to the default build."
    )
    return section("Subjects and pins", *blocks, note, "*Source: `subjects.lock.json`.*")


# ---- performance ----------------------------------------------------------------------------


def methodology(cfg: dict) -> str:
    p = cfg["perf"]
    items = [
        (
            f"Harness: one process per measured cell, cells in randomized order (seed {cfg['run']['seed']}); "
            "the harness is single-threaded and counts heap with an in-process allocator."
        ),
        (
            f"Each cell warms up for {p['warmup_ms']} ms, then takes at least {p['min_samples']} samples of at least "
            f"{p['min_sample_ms']} ms each."
        ),
        f"Medians carry a {p['ci_level']:.0%} bootstrap confidence interval from {p['bootstrap_resamples']} resamples.",
        (
            f"The full session is run {p['runs']} times; the two runs agree when every aggregate is within "
            f"{p['agreement_tolerance']:.0%}, otherwise the machine is flagged."
        ),
        f"A run is refused when the starting load average exceeds {p['max_start_load']}.",
        (
            f"Levels {', '.join(str(x) for x in p['levels'])}; framings {', '.join(p['framings'])}; modes "
            f"{', '.join(p['modes'])}. Streaming uses {p['small_out_chunk']}-byte and {p['large_in_chunk']}-byte chunks."
        ),
        (
            "Aggregates are total output bytes divided by summed per-file time; ratios are against stock zlib "
            "(zlib = 1.00x) and are only formed within the same mode."
        ),
    ]
    return section("Performance methodology", "\n".join(f"- {i}" for i in items))


def _read(table: str, d: Path):
    return ev.table_rows(table, d)


def aggregates_block(d: Path, cfg: dict) -> str:
    try:
        rows, side = _read("perf_aggregates", d)
    except MissingData:
        return pending("perf_aggregates")
    blocks = []
    for m in sorted({r["machine"] for r in rows}):
        for variant in sorted({r["variant"] for r in rows if r["machine"] == m}):
            sel = [r for r in rows if r["machine"] == m and r["variant"] == variant and r["mode"] == "oneshot"
                   and r["level"] == "6"]  # fmt: skip
            if not sel:
                continue
            table = md_table(["Subject", "Corpus", "Framing", "Aggregate MiB/s", "Ratio vs zlib", "Complete"],
                             [[r["subject"], r["corpus"], r["framing"], num(r["agg_mib_s"], 1),
                               num(r["ratio_vs_zlib"]), r["complete"]] for r in sel])  # fmt: skip
            suffix = "" if variant == "generic" else f"_{variant}"
            blocks.append(f"**{m}, {variant} build, one-shot, level 6**\n\n{table}\n\n"
                          + figure(f"perf_throughput_{m}{suffix}", f"Aggregate throughput on {m} ({variant}).", d))  # fmt: skip
    blocks.append(source("perf_aggregates", side))
    return "\n\n".join(blocks)


def per_file_block(d: Path, cfg: dict) -> str:
    try:
        rows, side = _read("perf_cells", d)
    except MissingData:
        return pending("perf_cells")
    out = []
    subjects = cfg["perf"]["subjects"]
    for m in sorted({r["machine"] for r in rows}):
        sel = [
            r
            for r in rows
            if r["machine"] == m and r["variant"] == "generic" and r["mode"] == "oneshot"
        ]
        for corpus in cfg["perf"]["corpora"]:
            for framing in cfg["perf"]["framings"]:
                for level in cfg["perf"]["levels"]:
                    cell = {(r["workload"], r["subject"]): r for r in sel
                            if r["corpus"] == corpus and r["framing"] == framing and r["level"] == str(level)}  # fmt: skip
                    workloads = sorted({w for w, _s in cell})
                    if not workloads:
                        continue
                    tbl = md_table(
                        ["Workload", *subjects],
                        [
                            [
                                w,
                                *[
                                    num(cell[(w, s)]["median_mib_s"], 1)
                                    if (w, s) in cell and cell[(w, s)]["status"] != "unsupported"
                                    else "n/a"
                                    for s in subjects
                                ],
                            ]
                            for w in workloads
                        ],
                    )
                    title = (
                        f"{m}, {corpus}, {framing} framing, level {level}: median MiB/s per file"
                    )
                    if level == 6:
                        out.append(f"**{title}**\n\n{tbl}")
                    else:
                        out.append(f"<details><summary>{title}</summary>\n\n{tbl}\n\n</details>")
    out.append(source("perf_cells", side))
    return "\n\n".join(out)


def tiny_block(d: Path) -> str:
    try:
        rows, side = _read("perf_tiny", d)
    except MissingData:
        return pending("perf_tiny")
    sel = [r for r in rows if r["level"] == "6" and r["framing"] == "raw"]
    tbl = md_table(["Machine", "Workload", "Prefix bytes", "Subject", "ns/op", "Time ratio vs zlib"],
                   [[r["machine"], r["workload"], r["prefix_bytes"], r["subject"], num(r["median_ns_per_op"], 0),
                     num(r["time_ratio_vs_zlib"])] for r in sel])  # fmt: skip
    return f"**Tiny inputs (setup cost), raw framing, level 6**\n\n{tbl}\n\n{source('perf_tiny', side)}"


def agreement_block(d: Path) -> str:
    try:
        rows, side = _read("perf_agreement_summary", d)
    except MissingData:
        return pending("perf_agreement_summary")
    cols = ["machine", "variant", "runs", "cells", "flagged_cells", "max_abs_rel_diff", "aggregates",
            "flagged_aggregates", "verdict"]  # fmt: skip
    tbl = md_table(["Machine", "Variant", "Runs", "Cells", "Flagged cells", "Max |rel. diff|", "Aggregates",
                    "Flagged aggregates", "Verdict"], [[num(r[c], 4) if c == "max_abs_rel_diff" else r[c] for c in cols] for r in rows])  # fmt: skip
    return f"**Run-to-run agreement**\n\n{tbl}\n\n{source('perf_agreement_summary', side)}"


def performance(d: Path, cfg: dict) -> list[str]:
    return [
        methodology(cfg),
        section(
            "Performance results",
            aggregates_block(d, cfg),
            per_file_block(d, cfg),
            tiny_block(d),
            agreement_block(d),
        ),
    ]


# ---- framing, content, trajectory ------------------------------------------------------------


def framing_section(d: Path) -> str:
    blocks = []
    for table, cols, heads in (
        ("framing_overhead", ["machine", "subject", "corpus", "level", "mode", "overhead_zlib", "overhead_gzip"],
         ["Machine", "Subject", "Corpus", "Level", "Mode", "zlib framing overhead", "gzip framing overhead"]),
        ("framing_hypothesis", ["machine", "cf_overhead_gzip", "zlib_nohw_overhead_gzip", "zlib_overhead_gzip", "rel_diff", "verdict"],
         ["Machine", "cf gzip overhead", "zlib-nohw gzip overhead", "zlib gzip overhead", "Relative difference", "Verdict"]),
    ):  # fmt: skip
        try:
            rows, side = _read(table, d)
        except MissingData:
            blocks.append(pending(table))
            continue
        pct = {
            "overhead_zlib",
            "overhead_gzip",
            "cf_overhead_gzip",
            "zlib_nohw_overhead_gzip",
            "zlib_overhead_gzip",
            "rel_diff",
        }
        body = [[(num(str(float(r[c]) * 100), 1) + "%") if c in pct and r[c] != "" else num(r[c]) if c != "verdict" else r[c] for c in cols] for r in rows]  # fmt: skip
        blocks.append(md_table(heads, body) + "\n\n" + source(table, side))
    blocks.append(
        "Overhead is `(1/T_framed - 1/T_raw) / (1/T_raw)`. The headline test asks whether cleanflate's "
        "gzip penalty roughly matches stock zlib's with hardware CRC disabled; the verdict is reported "
        "either way, and on x86_64 the control build is identical to the default build."
    )
    blocks.append(figure("framing_decomposition", "Framing cost per subject.", d))
    return section("Framing decomposition", *blocks)


def content_section(d: Path) -> str:
    blocks = []
    try:
        rows, side = _read("content_hypotheses", d)
        tbl = md_table(["Hypothesis", "Machine", "Feature", "n", "rho", "p", "Expected sign", "Verdict"],
                       [[r["hypothesis"], r["machine"], r["feature"], r["n"] or "n/a", num(r["rho"], 3),
                         num(r["p"], 4), r["expected_sign"], r["verdict"]] for r in rows])  # fmt: skip
        blocks.append(tbl + "\n\n" + source("content_hypotheses", side))
    except MissingData:
        blocks.append(pending("content_hypotheses"))
    blocks.append(
        "H1: cleanflate's relative weakness on Canterbury tracks short-distance and overlapping match "
        "density. H2: its level-1 weakness tracks literal fraction. Verdicts use Spearman rho with a "
        "seeded permutation p-value; they are never omitted."
    )
    findings = d / "CONTENT_FINDINGS.md"
    if findings.exists():
        blocks.append(
            "Findings note: [CONTENT_FINDINGS.md](CONTENT_FINDINGS.md). Per-file token features: "
            "`results/content_features.csv`."
        )
    scatter = (
        sorted((d / "figures").glob("content_scatter_*.png")) if (d / "figures").is_dir() else []
    )
    blocks += [
        figure(p.stem, f"Per-file ratio against {p.stem.removeprefix('content_scatter_')}.", d)
        for p in scatter
    ]
    if not scatter:
        blocks.append(
            "Pending: scatter plots need perf data; run `make perf` on M-A and M-B, then `make content`."
        )
    return section("Content analysis", *blocks)


def trajectory_section(d: Path, cfg: dict) -> str:
    try:
        rows, side = _read("trajectory", d)
    except MissingData:
        return section("Trajectory", pending("trajectory"))
    sel = [r for r in rows if r["level"] == "6" and r["mode"] == "oneshot"]
    tbl = md_table(["Machine", "Round", "Tag", "Corpus", "Framing", "Aggregate MiB/s", "Ratio vs zlib"],
                   [[r["machine"], r["round"], r["tag"], r["corpus"], r["framing"], num(r["agg_mib_s"], 1),
                     num(r["ratio_vs_zlib"])] for r in sel])  # fmt: skip
    figs = [
        figure(f"trajectory_{m}", f"Throughput ratio vs zlib by round on {m}.", d)
        for m in cfg["paper"]["machines"]
    ]
    return section("Trajectory", tbl, source("trajectory", side), *figs)


def render_sections_part1(results_dir: Path | None = None, cfg: dict | None = None) -> str:
    d = Path(results_dir) if results_dir else paths.RESULTS
    cfg = cfg or config.load_config("full")
    parts = [
        environments(d),
        subjects_and_pins(),
        *performance(d, cfg),
        framing_section(d),
        content_section(d),
        trajectory_section(d, cfg),
    ]
    return "\n\n".join(parts) + "\n"
