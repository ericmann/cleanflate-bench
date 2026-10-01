"""RESULTS.md: methodology and results for SPEC 3 (SPEC 5 T3, 6). Part 1 covers 3.1 to 3.5, part 2 the rest.

`render_sections_part1()` returns Markdown for: environments, subjects and pins, performance
methodology and results, framing decomposition, content analysis and trajectory. Tables are copied
from derived tables read through `kits.evidence.table_rows` (which refuses pending tables), each
followed by a source line (table, raw files, script). Pending data becomes an explicit
"Pending: run `make X` on M-Y" paragraph. Figures are embedded relative to `results/`.
"""

import csv
import json
import sys
from importlib import metadata
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
    if s.lstrip("-").isdigit():
        return s
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
        rows.append(
            [
                m,
                c.get("cpu_model", "n/a"),
                f"{cores.get('physical', 'n/a')} / {cores.get('logical', 'n/a')}",
                " ".join(x for x in (os_.get("name"), os_.get("version")) if x) or "n/a",
                c.get("kernel", "n/a"),
                c.get("governor") or "n/a",
            ]
        )
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
            rows.append(
                [
                    name,
                    b.get("compiler_version") or b.get("compiler", "n/a"),
                    b.get("target_cpu", "n/a"),
                    "yes" if hw.get("compiled_in") else "no",
                    "yes" if hw.get("runtime_dispatch") else "no",
                ]
            )
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
            sel = [
                r
                for r in rows
                if r["machine"] == m
                and r["variant"] == variant
                and r["mode"] == "oneshot"
                and r["level"] == "6"
            ]
            if not sel:
                continue
            table = md_table(
                ["Subject", "Corpus", "Framing", "Aggregate MiB/s", "Ratio vs zlib", "Complete"],
                [
                    [
                        r["subject"],
                        r["corpus"],
                        r["framing"],
                        num(r["agg_mib_s"], 1),
                        num(r["ratio_vs_zlib"]),
                        r["complete"],
                    ]
                    for r in sel
                ],
            )
            suffix = "" if variant == "generic" else f"_{variant}"
            blocks.append(
                f"**{m}, {variant} build, one-shot, level 6**\n\n{table}\n\n"
                + figure(
                    f"perf_throughput_{m}{suffix}", f"Aggregate throughput on {m} ({variant}).", d
                )
            )
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
                    cell = {
                        (r["workload"], r["subject"]): r
                        for r in sel
                        if r["corpus"] == corpus
                        and r["framing"] == framing
                        and r["level"] == str(level)
                    }
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
    tbl = md_table(
        ["Machine", "Workload", "Prefix bytes", "Subject", "ns/op", "Time ratio vs zlib"],
        [
            [
                r["machine"],
                r["workload"],
                r["prefix_bytes"],
                r["subject"],
                num(r["median_ns_per_op"], 0),
                num(r["time_ratio_vs_zlib"]),
            ]
            for r in sel
        ],
    )
    return f"**Tiny inputs (setup cost), raw framing, level 6**\n\n{tbl}\n\n{source('perf_tiny', side)}"


def agreement_block(d: Path) -> str:
    try:
        rows, side = _read("perf_agreement_summary", d)
    except MissingData:
        return pending("perf_agreement_summary")
    cols = [
        "machine",
        "variant",
        "runs",
        "cells",
        "flagged_cells",
        "max_abs_rel_diff",
        "aggregates",
        "flagged_aggregates",
        "verdict",
    ]
    tbl = md_table(
        [
            "Machine",
            "Variant",
            "Runs",
            "Cells",
            "Flagged cells",
            "Max |rel. diff|",
            "Aggregates",
            "Flagged aggregates",
            "Verdict",
        ],
        [[num(r[c], 4) if c == "max_abs_rel_diff" else r[c] for c in cols] for r in rows],
    )
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
        (
            "framing_overhead",
            ["machine", "subject", "corpus", "level", "mode", "overhead_zlib", "overhead_gzip"],
            [
                "Machine",
                "Subject",
                "Corpus",
                "Level",
                "Mode",
                "zlib framing overhead",
                "gzip framing overhead",
            ],
        ),
        (
            "framing_hypothesis",
            [
                "machine",
                "cf_overhead_gzip",
                "zlib_nohw_overhead_gzip",
                "zlib_overhead_gzip",
                "rel_diff",
                "verdict",
            ],
            [
                "Machine",
                "cf gzip overhead",
                "zlib-nohw gzip overhead",
                "zlib gzip overhead",
                "Relative difference",
                "Verdict",
            ],
        ),
    ):
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
        body = [
            [
                (num(str(float(r[c]) * 100), 1) + "%")
                if c in pct and r[c] != ""
                else num(r[c])
                if c != "verdict"
                else r[c]
                for c in cols
            ]
            for r in rows
        ]
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
        tbl = md_table(
            ["Hypothesis", "Machine", "Feature", "n", "rho", "p", "Expected sign", "Verdict"],
            [
                [
                    r["hypothesis"],
                    r["machine"],
                    r["feature"],
                    r["n"] or "n/a",
                    num(r["rho"], 3),
                    num(r["p"], 4),
                    r["expected_sign"],
                    r["verdict"],
                ]
                for r in rows
            ],
        )
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
    tbl = md_table(
        ["Machine", "Round", "Tag", "Corpus", "Framing", "Aggregate MiB/s", "Ratio vs zlib"],
        [
            [
                r["machine"],
                r["round"],
                r["tag"],
                r["corpus"],
                r["framing"],
                num(r["agg_mib_s"], 1),
                num(r["ratio_vs_zlib"]),
            ]
            for r in sel
        ],
    )
    figs = [
        figure(f"trajectory_{m}", f"Throughput ratio vs zlib by round on {m}.", d)
        for m in cfg["paper"]["machines"]
    ]
    return section("Trajectory", tbl, source("trajectory", side), *figs)


# ---- part 2 ----------------------------------------------------------------------------------


def table_block(
    table: str,
    columns: list[str],
    heads: list[str],
    d: Path,
    *,
    where=None,
    digits: int = 3,
    limit: int | None = None,
    title: str = "",
) -> str:
    """A derived table as Markdown with its source line, or a pending paragraph."""
    try:
        rows, side = _read(table, d)
    except MissingData:
        return pending(table)
    sel = [r for r in rows if where is None or where(r)][:limit]
    body = [
        [num(r[c], digits) if _numeric(r[c]) else (r[c] or "n/a") for c in columns] for r in sel
    ]
    head = f"**{title}**\n\n" if title else ""
    return head + md_table(heads, body) + "\n\n" + source(table, side)


def _numeric(s: str) -> bool:
    try:
        float(s)
    except ValueError:
        return False
    return s != ""


def correctness_section(d: Path) -> str:
    return section(
        "Correctness",
        table_block(
            "conformance",
            ["machine", "subject", "streams", "passed", "failed", "unsupported", "pass_rate"],
            ["Machine", "Subject", "Streams", "Passed", "Failed", "Unsupported", "Pass rate"],
            d,
            digits=4,
            title="Conformance over the shared corpus",
        ),
        table_block(
            "conformance_disagreements",
            ["machine", "entry", "framing", "subject", "outcome", "error"],
            ["Machine", "Entry", "Framing", "Subject", "Outcome", "Error"],
            d,
            title="Conformance disagreements (an empty table means none)",
        ),
        table_block(
            "malformed_disagreements",
            ["file", "framing", "outcomes_by_subject", "cf_expected"],
            ["File", "Framing", "Outcomes by subject", "cf expected"],
            d,
            title="Malformed inputs on which subjects disagree about accept versus reject",
        ),
        "Full matrix: `results/malformed_matrix.csv`; highlights: [MALFORMED_HIGHLIGHTS.md](MALFORMED_HIGHLIGHTS.md).",
        figure("malformed_highlights", "Malformed-input disagreements.", d),
        table_block(
            "fuzz_stats",
            [
                "machine",
                "target",
                "budget_cpu_hours",
                "executions",
                "exec_per_s",
                "cov_lines_pct",
                "cov_regions_pct",
                "divergences",
            ],
            [
                "Machine",
                "Target",
                "CPU hours",
                "Executions",
                "Exec/s",
                "cf line coverage %",
                "cf region coverage %",
                "Divergences",
            ],
            d,
            digits=1,
            title="Differential fuzzing",
        ),
        table_block(
            "fuzz_divergences",
            ["machine", "target", "artifact_sha256", "classification", "outcomes_by_subject"],
            ["Machine", "Target", "Artifact SHA-256", "Classification", "Outcomes"],
            d,
            title="Fuzz divergences after triage",
        ),
        figure("fuzz_stats", "Fuzzing executions and divergences.", d),
        table_block(
            "bombs",
            [
                "machine",
                "subject",
                "case",
                "ratio",
                "output_bytes",
                "limit_bytes",
                "outcome",
                "peak_rss_bytes",
                "seconds",
                "limit_enforcement",
            ],
            [
                "Machine",
                "Subject",
                "Case",
                "Ratio",
                "Output bytes",
                "Limit bytes",
                "Outcome",
                "Peak RSS bytes",
                "Seconds",
                "Limit enforcement",
            ],
            d,
            digits=4,
            title="Decompression-bomb sweep",
        ),
    )


def size_section(d: Path) -> str:
    return section(
        "Size, safety and complexity",
        table_block(
            "binary_size",
            ["machine", "subject", "opt", "bytes", "note"],
            ["Machine", "Subject", "Opt-level", "Stripped bytes", "Note"],
            d,
            digits=0,
            title="Minimal decoder binary size",
        ),
        figure("binary_size", "Binary size per subject.", d),
        table_block(
            "cargo_bloat",
            ["machine", "subject", "opt", "crate", "bytes", "share"],
            ["Machine", "Subject", "Opt-level", "Crate", "Bytes", "Share"],
            d,
            digits=4,
            limit=40,
            title="cargo bloat, first rows",
        ),
        table_block(
            "unsafe",
            [
                "subject",
                "crate",
                "version",
                "role",
                "forbid_unsafe_code",
                "unsafe_blocks",
                "unsafe_fns",
                "unsafe_impls",
                "geiger_used",
                "note",
            ],
            [
                "Subject",
                "Crate",
                "Version",
                "Role",
                "forbids unsafe",
                "Unsafe blocks",
                "Unsafe fns",
                "Unsafe impls",
                "geiger used",
                "Note",
            ],
            d,
            digits=0,
            title="Unsafe surface",
        ),
        figure("unsafe_counts", "Unsafe code per subject.", d),
        table_block(
            "deps",
            ["subject", "package", "direct_count", "transitive_count", "advisories"],
            ["Subject", "Package", "Direct", "Transitive", "Advisories"],
            d,
            digits=0,
            title="Dependencies",
        ),
        table_block(
            "loc",
            ["subject", "language", "files", "code", "comments", "blanks"],
            ["Subject", "Language", "Files", "Code", "Comments", "Blanks"],
            d,
            digits=0,
            title="Decompression-path lines of code (tokei; method in docs/methods/decomp-paths.md)",
        ),
        table_block(
            "complexity",
            ["subject", "tool", "tool_version", "metric", "n_functions", "median", "p90", "max"],
            ["Subject", "Tool", "Version", "Metric", "Functions", "Median", "p90", "Max"],
            d,
            digits=0,
            title="Per-function complexity (p90 by nearest rank)",
        ),
    )


def _statement_lines(d: Path) -> list[str]:
    p = d / "similarity_statement.md"
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def fragment_counts(d: Path) -> list[list[str]]:
    """Verdict counts for the top fragments of each test pair (from the fragment tables)."""
    rows = []
    for p in sorted(d.glob("similarity_fragments_*.csv")):
        with open(p, encoding="utf-8", newline="") as f:
            frags = list(csv.DictReader(f))
        counts = {"RFC-forced": 0, "idiomatic-inevitable": 0, "suspicious": 0}
        unreviewed = 0
        for r in frags:
            v = r.get("verdict", "")
            if v in counts:
                counts[v] += 1
            else:
                unreviewed += 1
        pair = p.name.removeprefix("similarity_fragments_").removesuffix(".csv").replace("_", "-")
        rows.append(
            [
                pair,
                len(frags),
                counts["RFC-forced"],
                counts["idiomatic-inevitable"],
                counts["suspicious"],
                unreviewed,
            ]
        )
    return rows


def similarity_section(d: Path, cfg: dict) -> str:
    jplag = config.load_toml("tools.toml").get("jplag", {}).get("version", "n/a")
    versions = []
    for pkg in ("tree-sitter", "tree-sitter-rust", "tree-sitter-c"):
        try:
            versions.append(f"{pkg} {metadata.version(pkg)}")
        except metadata.PackageNotFoundError:
            versions.append(f"{pkg} not installed")
    methods = (
        f"Methods (full description in `docs/methods/similarity.md`): tree-sitter token n-gram Jaccard "
        f"(n from {cfg['similarity']['ngram_min']} to {cfg['similarity']['ngram_max']}), identifier overlap "
        f"(length at least {cfg['similarity']['min_ident_len']}, RFC-mandated names excluded), comment n-gram "
        f"overlap, and JPlag {jplag}. Tools: {', '.join(versions)}. The RFC exclusion list is "
        "`config/rfc_identifiers.txt` (effective list: `results/similarity_identifier_exclusions.txt`)."
    )
    stmt = _statement_lines(d)
    claim = next((ln for ln in stmt if "T1 claim" in ln), None)
    blocks = [
        methods,
        table_block(
            "similarity_summary",
            [
                "metric",
                "pair",
                "role",
                "score",
                "neg_score",
                "pos_score",
                "position",
                "classification",
            ],
            [
                "Metric",
                "Pair",
                "Role",
                "Score",
                "Negative control",
                "Positive control",
                "Position",
                "Classification",
            ],
            d,
            digits=4,
            title="Scores against the controls (negative zrs-mox, positive zrs-zng)",
        ),
        ("**Result statement:** " + claim.replace("**", ""))
        if claim
        else pending("similarity_summary"),
        figure("similarity_controls", "Where cleanflate falls between the controls.", d),
    ]
    counts = fragment_counts(d)
    if counts:
        blocks.append(
            "**Top fragment pairs and their review verdicts**\n\n"
            + md_table(
                [
                    "Pair",
                    "Fragments",
                    "RFC-forced",
                    "idiomatic-inevitable",
                    "suspicious",
                    "Unreviewed",
                ],
                counts,
            )
            + "\n\nVerdicts live in `config/similarity_verdicts.toml` and are filled in by a human reviewer; "
            "per-pair excerpts are under `results/similarity_fragments/`."
        )
    else:
        blocks.append(pending("similarity_summary", detail="no fragment tables"))
    blocks.append("Structural write-up: [STRUCTURE_COMPARISON.md](STRUCTURE_COMPARISON.md).")
    return section("Clean-room verification", *blocks)


def effort_section(d: Path) -> str:
    gaps = d / "EFFORT_GAPS.md"
    blocks = [
        table_block(
            "effort_totals",
            [
                "round",
                "wall_clock_s",
                "idle_s",
                "models",
                "input_tokens",
                "output_tokens",
                "cache_write_tokens",
                "cache_read_tokens",
                "cost_usd",
            ],
            [
                "Round",
                "Wall-clock s",
                "Idle s",
                "Models",
                "Input tokens",
                "Output tokens",
                "Cache-write tokens",
                "Cache-read tokens",
                "Cost USD",
            ],
            d,
            digits=0,
            title="Totals per round",
        ),
        table_block(
            "effort_stage_round",
            [
                "round",
                "stage",
                "wall_clock_s",
                "models",
                "input_tokens",
                "output_tokens",
                "cache_write_tokens",
                "cache_read_tokens",
                "cost_usd",
            ],
            [
                "Round",
                "Stage",
                "Wall-clock s",
                "Models",
                "Input tokens",
                "Output tokens",
                "Cache-write tokens",
                "Cache-read tokens",
                "Cost USD",
            ],
            d,
            digits=0,
            title="Per stage and round",
        ),
        figure("effort_cost_per_stage", "Effort per stage and round.", d),
        table_block(
            "effort_milestones",
            ["round", "milestone", "wall_clock_s", "review_rounds"],
            ["Round", "Milestone", "Wall-clock s", "Review rounds"],
            d,
            digits=0,
            title="Milestones",
        ),
        table_block(
            "effort_review_rounds",
            ["round", "review_round", "verdict", "fix_tasks"],
            ["Round", "Review round", "Verdict", "Fix tasks"],
            d,
            digits=0,
            title="Review rounds",
        ),
        table_block(
            "effort_defects",
            ["round", "source", "count"],
            ["Round", "Discovery source", "Defects"],
            d,
            digits=0,
            title="Defect discovery source",
        ),
        table_block(
            "effort_interventions",
            ["round", "when", "stage_task", "nature"],
            ["Round", "When", "Stage/task", "Nature"],
            d,
            title="Human interventions",
        ),
        table_block(
            "effort_denied",
            ["round", "category", "count"],
            ["Round", "Category", "Denied calls"],
            d,
            digits=0,
            title="Denied tool calls",
        ),
    ]
    blocks.append(
        "Data gaps and methods: "
        + ("[EFFORT_GAPS.md](EFFORT_GAPS.md)." if gaps.exists() else pending("effort_totals"))
    )
    ctx = d / "zlibrs_context.csv"
    if ctx.exists():
        with open(ctx, encoding="utf-8", newline="") as f:
            facts = list(csv.DictReader(f))
        body = [
            [r["fact"], r["value"], r["fetched_at"]] for r in facts if r["fact"] != "scope_note"
        ]
        note = next((r["value"] for r in facts if r["fact"] == "scope_note"), "")
        blocks.append(
            "**zlib-rs status-quo context (from the public GitHub and crates.io APIs)**\n\n"
            + md_table(["Fact", "Value", "Fetched"], body)
            + f"\n\n*Scope:* {note}\n\n"
            "*Source: `results/zlibrs_context.csv` via `cfbench.effort.context`.*"
        )
    else:
        blocks.append(pending("effort_totals", detail="zlib-rs context table missing"))
    return section("Effort, cost and provenance", *blocks)


def findings_section(d: Path) -> str:
    p = d / "findings.md"
    body = "See [findings.md](findings.md) for bugs found in cleanflate. They are recorded there and never patched in this repo."
    if p.exists():
        entries = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith("- ")]
        body += (
            f" The file currently lists {len(entries)} entries."
            if entries
            else " The file currently lists no entries."
        )
    return section("Findings for the cleanflate repo", body)


def threats_section(d: Path, cfg: dict) -> str:
    stmt = next((ln.replace("**", "") for ln in _statement_lines(d) if "T1 claim" in ln), None)
    flagged = pending("perf_agreement_summary")
    try:
        rows, _ = _read("perf_agreement_summary", d)
        bad = [r for r in rows if r["verdict"] != "pass"]
        flagged = (
            f"The agreement summary has {len(rows)} machine and variant entries, of which {len(bad)} are not "
            f"'pass' (tolerance {cfg['perf']['agreement_tolerance']:.0%})."
        )
    except MissingData:
        pass
    try:
        fz, _ = _read("fuzz_stats", d)
        budget = (
            f"The fuzz runs recorded in `fuzz_stats` used {', '.join(r['target'] + ' ' + r['budget_cpu_hours'] for r in fz)} "
            f"CPU hours against a configured {cfg['fuzz']['budget_cpu_hours']} per target."
        )
    except MissingData:
        budget = (
            f"No full fuzz run is recorded yet (configured budget {cfg['fuzz']['budget_cpu_hours']} CPU hours "
            f"per target); {pending('fuzz_stats', 'a machine that can spare it')}"
        )
    lock = paths_lock()
    crc = []
    for m, info in sorted(lock.get("machines", {}).items()):
        builds = info["builds"]
        nohw = builds.get("zlib-nohw", {}).get("hw_crc", {}).get("compiled_in")
        dflt = builds.get("zlib", {}).get("hw_crc", {}).get("compiled_in")
        crc.append(
            f"on {m} the default zlib build has hardware CRC {'compiled in' if dflt else 'not compiled in'} and the "
            f"zlib-nohw control {'has it' if nohw else 'does not'}"
        )
    verdict = "no framing verdict yet"
    try:
        rows, _ = _read("framing_hypothesis", d)
        verdict = "the gzip-gap verdict is " + next(
            r["verdict"] for r in rows if r["machine"] == "ALL"
        )
    except (MissingData, StopIteration):
        pass
    items = [
        (
            "Training-data contamination",
            "Model training data cannot be controlled, so resemblance is measured against "
            "negative and positive controls instead of assumed away. "
            + (stmt or pending("similarity_summary"))
            + " Similarity metrics are proxies; a low score does not prove independence, and a high one does not prove copying.",
        ),
        (
            "Machine variance and thermal effects",
            (
                "Timings come from two desktop-class machines that are not isolated "
                f"labs; runs are refused above a starting load of {cfg['perf']['max_start_load']} and each session is repeated "
                f"{cfg['perf']['runs']} times. {flagged} Governor and thermal state are recorded in the environment captures."
            ),
        ),
        (
            "Feature-scope mismatch",
            "cleanflate only decompresses, in safe Rust, with no SIMD and no C ABI; the "
            "comparators compress, some use SIMD and hardware CRC, and several expose a C ABI. "
            + PARITY_NOTE
            + " The zlib-rs context table states the scope difference for the effort comparison.",
        ),
        (
            "Fuzz budget limits",
            "Fuzzing finds divergences but cannot show their absence. "
            + budget
            + " Normalizations that hide API-semantics differences are listed in `fuzz/README.md`.",
        ),
        (
            "n=1 build effort",
            (
                "The effort data describes one pipeline building one library in three rounds on one "
                "operator's setup; model prices are unset, so cost is unavailable, and human time is only partly recorded "
                "(see EFFORT_GAPS.md). It is an existence proof, not a distribution."
            ),
        ),
        (
            "Hardware-CRC asymmetry",
            "Hardware CRC is not equal across subjects: "
            + "; ".join(crc or ["no pins recorded"])
            + f". On x86_64 the control build is identical to the default build, so the control only separates the two on "
            f"aarch64. Currently: {verdict}.",
        ),
    ]
    return section("Threats to validity", *[f"### {t}\n\n{p}" for t, p in items])


def paths_lock() -> dict:
    p = paths.ROOT / "subjects.lock.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def render_sections_part2(results_dir: Path | None = None, cfg: dict | None = None) -> str:
    d = Path(results_dir) if results_dir else paths.RESULTS
    cfg = cfg or config.load_config("full")
    parts = [
        correctness_section(d),
        size_section(d),
        similarity_section(d, cfg),
        effort_section(d),
        findings_section(d),
        threats_section(d, cfg),
    ]
    return "\n\n".join(parts) + "\n"


HEADER = "<!-- generated by cfbench.kits.results_md; do not edit -->"


def render(results_dir: Path | None = None, cfg: dict | None = None) -> str:
    return "\n".join(
        [
            HEADER,
            "",
            "# Results",
            "",
            render_sections_part1(results_dir, cfg),
            render_sections_part2(results_dir, cfg),
        ]
    )


def main() -> int:
    out = paths.RESULTS / "RESULTS.md"
    out.write_text(render(), encoding="utf-8")
    print(out)
    return 0


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


if __name__ == "__main__":
    sys.exit(main())
