"""RESULTS.md: every result of SPEC 3, organised around the pipeline's claims (SPEC 5 T3, 6).

The document leads with the claims map (`sections.claims_map`), then one section per claim
category in order (equivalence, safety, clean-room, effort, viability, iteration), the findings,
the threats to validity, and an appendix (environments, pins, per-file tables, tiny inputs,
content correlations, binary size). Tables are copied from derived tables read through
`kits.evidence.table_rows` (which refuses pending tables), each followed by a source line (table,
raw files, script). Pending data becomes an explicit "Pending: run `make X` on M-Y" paragraph, and
a measurement deliberately skipped on a machine says so with its recorded reason. Figures are
embedded relative to `results/`.
"""

import csv
import json
import sys
from importlib import metadata
from pathlib import Path

from cfbench import config, paths, rawio
from cfbench.kits import claims as claims_mod
from cfbench.kits import evidence as ev
from cfbench.kits import pipeline, sections
from cfbench.kits.evidence import MissingData
from cfbench.kits.pipeline import EXAMPLE, PIPELINE_NAME
from cfbench.parity import PARITY_NOTE
from cfbench.similarity import pairs as similarity_pairs

MACHINES = "M-A and M-B"


def pending(table: str, machines: str = MACHINES, detail: str = "") -> str:
    target = ev.TARGETS.get(table, "make all")
    extra = f" ({detail})" if detail else ""
    return f"Pending: run `{target}` on {machines}.{extra}"


def md_table(columns: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(columns) + " |"
    sep = "|" + "|".join(["---"] * len(columns)) + "|"
    body = ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body]) + f"\n\n*{PARITY_NOTE}*"


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


def section(title: str, *blocks: str, level: int = 2) -> str:
    return "\n\n".join([f"{'#' * level} {title}", *[b for b in blocks if b]])


def not_run_lines(table: str, machines_present: set[str], cfg: dict) -> list[str]:
    """One line per configured machine with no rows: its recorded reason, or a pending line."""
    out = []
    for m in cfg["paper"]["machines"]:
        if m in machines_present:
            continue
        why = pipeline.not_run_reason(m, table)
        out.append(f"Not run on {m}: {why}." if why else pending(table, m))
    return out


def machines_in(table: str, d: Path) -> set[str]:
    try:
        rows, _ = _read(table, d)
    except MissingData:
        return set()
    return {r.get("machine", "") for r in rows}


# ---- environments and pins ------------------------------------------------------------------


def environments(d: Path, level: int = 2) -> str:
    newest: dict[str, dict] = {}
    for p in rawio.list_raw("env"):
        doc = rawio.load_raw(p)
        cap = doc["payload"].get("capture") or {}
        m = cap.get("machine") or doc["machine"]
        if m not in newest or doc["timestamp"] > newest[m]["timestamp"]:
            newest[m] = {"timestamp": doc["timestamp"], "cap": cap, "path": p}
    if not newest:
        return section("Environments", pending("env"), level=level)
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
        level=level,
    )


def subjects_and_pins(lock_path: Path | None = None, level: int = 2) -> str:
    p = lock_path or paths.ROOT / "subjects.lock.json"
    if not p.exists():
        return section(
            "Subjects and pins",
            "Pending: run `make pins` (writes `subjects.lock.json`).",
            level=level,
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
    return section(
        "Subjects and pins", *blocks, note, "*Source: `subjects.lock.json`.*", level=level
    )


# ---- performance ----------------------------------------------------------------------------


def methodology(cfg: dict, level: int = 2) -> str:
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
        (
            f"The starting load average is checked against {p['max_start_load']} and a higher value is "
            "recorded as a precondition warning; a run is refused for it only under `--strict`."
        ),
        (
            f"Levels {', '.join(str(x) for x in p['levels'])}; framings {', '.join(p['framings'])}; modes "
            f"{', '.join(p['modes'])}. Small streaming feeds {p['small_in_chunk']}-byte input chunks into "
            f"{p['small_out_chunk']}-byte output buffers; large streaming uses {p['large_in_chunk']}-byte input and "
            f"{p['large_out_chunk']}-byte output chunks."
        ),
        (
            "Aggregates are total output bytes divided by summed per-file time; ratios are against stock zlib "
            "(zlib = 1.00x) and are only formed within the same mode."
        ),
    ]
    return section("Performance methodology", "\n".join(f"- {i}" for i in items), level=level)


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


# ---- framing, content, trajectory ------------------------------------------------------------


def framing_section(d: Path, level: int = 2) -> str:
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
    return section("Framing decomposition", *blocks, level=level)


def content_section(d: Path, level: int = 2) -> str:
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
    return section("Content analysis", *blocks, level=level)


def trajectory_section(d: Path, cfg: dict, level: int = 2) -> str:
    try:
        rows, side = _read("trajectory", d)
    except MissingData:
        return section("Trajectory", pending("trajectory"), level=level)
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
    return section("Trajectory", tbl, source("trajectory", side), *figs, level=level)


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
        [
            num(r.get(c, ""), digits) if _numeric(r.get(c, "")) else (r.get(c) or "n/a")
            for c in columns
        ]
        for r in sel
    ]
    head = f"**{title}**\n\n" if title else ""
    return head + md_table(heads, body) + "\n\n" + source(table, side)


def _numeric(s: str) -> bool:
    try:
        float(s)
    except ValueError:
        return False
    return s != ""


def equivalence_section(d: Path, cfg: dict, level: int = 2) -> str:
    """Conformance, malformed inputs, differential fuzzing and the bomb sweep, on both machines."""
    fixtures = pipeline.note_text("m-a-fixtures")
    return section(
        "Equivalence",
        f"*Does {EXAMPLE} decode exactly what {pipeline.LEGACY} decodes?* Valid streams must decode "
        "byte-identically; malformed streams are compared on accept versus reject.",
        table_block(
            "conformance",
            ["machine", "subject", "streams", "passed", "failed", "unsupported", "pass_rate"],
            ["Machine", "Subject", "Streams", "Passed", "Failed", "Unsupported", "Pass rate"],
            d,
            digits=4,
            title="Conformance over the shared corpus",
        ),
        *not_run_lines("conformance", machines_in("conformance", d), cfg),
        fixtures,
        table_block(
            "conformance_disagreements",
            ["machine", "entry", "framing", "subject", "outcome", "error"],
            ["Machine", "Entry", "Framing", "Subject", "Outcome", "Error"],
            d,
            title="Conformance disagreements (an empty table means none)",
        ),
        table_block(
            "malformed_summary",
            [
                "machine",
                "files",
                "subjects",
                "cf_expected_files",
                "cf_matches_expected",
                "cf_mismatches",
                "disagreements",
                "disagreements_cf_stricter",
            ],
            [
                "Machine",
                "Files",
                "Subjects",
                "Files with a cf expectation",
                "cf matches EXPECTED.tsv",
                "cf mismatches",
                "Subjects disagree",
                "cf the stricter decoder",
            ],
            d,
            digits=0,
            title="Malformed inputs per machine",
        ),
        *not_run_lines("malformed_summary", machines_in("malformed_summary", d), cfg),
        table_block(
            "malformed_disagreements",
            ["machine", "file", "framing", "outcomes_by_subject", "cf_expected"],
            ["Machine", "File", "Framing", "Outcomes by subject", "cf expected"],
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
        *not_run_lines("fuzz_stats", machines_in("fuzz_stats", d), cfg),
        pipeline.note_text("fuzz-throttling"),
        table_block(
            "fuzz_divergences",
            ["machine", "target", "artifact_sha256", "classification", "outcomes_by_subject"],
            ["Machine", "Target", "Artifact SHA-256", "Classification", "Outcomes"],
            d,
            title="Fuzz divergences after triage (an empty table means none)",
        ),
        figure("fuzz_stats", "Fuzzing executions and divergences.", d),
        table_block(
            "bombs",
            [
                "machine",
                "subject",
                "case",
                "ratio",
                "overall_ratio",
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
                "Overall ratio (nested)",
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
        *not_run_lines("bombs", machines_in("bombs", d), cfg),
        level=level,
    )


def safety_section(d: Path, level: int = 2) -> str:
    """Unsafe surface, dependencies and the size of the decompression path."""
    return section(
        "Safety",
        "*Is the replacement memory-safe by construction?*",
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
        level=level,
    )


def isolation_block(d: Path) -> str:
    """Guard denials and the forbidden-read audit of cleanflate's provenance log."""
    return "\n\n".join(
        [
            (
                f"**Mechanical isolation.** {PIPELINE_NAME}'s guard hook refuses tool calls that would reach prior art "
                "(forbidden words in paths, recursive searches, network fetches outside an allowlist, forbidden tools). "
                "Every refusal is logged and classified by hand in `config/denial_verdicts.toml` as a prior-art attempt, "
                "a false positive (a rule matched a call that sought no prior art) or an offline test. Retries are merged "
                "into distinct attempts: a denial within `effort.denial_retry_seconds` of the previous one in the same task "
                "joins its attempt, and an attempt takes its most serious verdict. "
                "The audit below re-reads the allowed calls for any that touched a prior-art path "
                "anyway (method in `docs/methods/effort.md`)."
            ),
            table_block(
                "effort_totals",
                [
                    "round",
                    "denied_calls",
                    "denied_attempts",
                    "denied_prior_art_attempts",
                    "denied_false_positive_attempts",
                    "denied_offline_test_attempts",
                    "read_calls",
                    "forbidden_read_candidates",
                    "forbidden_reads",
                    "interventions",
                ],
                [
                    "Round",
                    "Denied calls",
                    "Distinct attempts",
                    "Prior-art attempts",
                    "False positives",
                    "Offline tests",
                    "Allowed read-capable calls",
                    "Forbidden-read candidates",
                    "Forbidden reads",
                    "Human interventions",
                ],
                d,
                digits=0,
                title="Guard and audit totals per round",
            ),
            table_block(
                "effort_denied",
                ["round", "category", "verdict", "count"],
                ["Round", "Category", "Verdict", "Denied calls"],
                d,
                digits=0,
                title="Denied tool calls by category and verdict",
            ),
            table_block(
                "effort_denials",
                ["round", "ts", "stage", "task", "category", "attempt", "verdict", "note"],
                ["Round", "When", "Stage", "Task", "Category", "Attempt", "Verdict", "Note"],
                d,
                digits=0,
                title="Every denied call, its attempt and its classification (`config/denial_verdicts.toml`)",
            ),
            table_block(
                "effort_forbidden_reads",
                ["round", "ts", "tool", "stage", "path", "rule", "verdict", "note"],
                ["Round", "When", "Tool", "Stage", "Path", "Rule", "Verdict", "Note"],
                d,
                title="Forbidden-read candidates and their classification (`config/forbidden_read_verdicts.toml`)",
            ),
        ]
    )


def clean_room_section(d: Path, cfg: dict, level: int = 2) -> str:
    body = similarity_section(
        d, cfg, level=level + 1, title="Similarity against negative and positive controls"
    )
    return section(
        "Clean-room",
        "*Was the build isolated from prior art, and does the code show it?*",
        isolation_block(d),
        body,
        level=level,
    )


def viability_section(d: Path, cfg: dict, level: int = 2) -> str:
    h = "#" * (level + 1)
    viab = sections.viability_table(d, cfg)
    gap = sections.gzip_gap_block(d, cfg)
    stab = sections.stability_block(d, cfg)
    try:
        _rows, side = _read("perf_aggregates", d)
        agg_src = ""
    except MissingData:
        side, agg_src = None, pending("perf_aggregates")
    return section(
        "Viability",
        "*Is the replacement fast enough to matter, on both machines?*",
        methodology(cfg, level=level + 1),
        f"{h} Both machines in one table\n\n{viab.text}",
        f"{h} Run-to-run stability\n\n{stab.text}",
        pipeline.note_text("m-a-high-power"),
        pipeline.note_text("m-b-background-load"),
        f"{h} Hardware-CRC evidence: the gzip gap on each machine\n\n{gap.text}",
        f"{h} Aggregates per machine and build variant\n\n"
        + (aggregates_block(d, cfg) if side else agg_src),
        framing_section(d, level=level + 1),
        level=level,
    )


def iteration_section(d: Path, cfg: dict, level: int = 2) -> str:
    h = "#" * (level + 1)
    sleep = sections.sleep_check_block(d, cfg)
    return section(
        "Iteration",
        f"*Did {PIPELINE_NAME}'s later rounds improve it?*",
        trajectory_section(d, cfg, level=level + 1),
        f"{h} Sleep-interruption check\n\n{sleep.text}",
        level=level,
    )


def appendix_binary_size(d: Path, level: int = 3) -> str:
    return section(
        "Binary size",
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
        level=level,
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


def similarity_section(
    d: Path, cfg: dict, level: int = 2, title: str = "Clean-room verification"
) -> str:
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
        "`config/rfc_identifiers.txt` (effective list: `results/similarity_identifier_exclusions.txt`). "
        "A post-hoc sensitivity analysis, added after the first full run and not pre-registered, repeats "
        "the identifier metrics (`ident_*_filtered`) with the extended list "
        "`config/identifier_exclusions_posthoc.txt` (Rust attribute, lint and std names, and names built "
        "only from RFC-defined terms), applied to every pair including the controls. The T1 claim is "
        "decided on the pre-registered metrics alone. Reference pairs ("
        + ", ".join(similarity_pairs.reference_labels(cfg))
        + "), added after the pre-registered analysis, give cross-language baselines and are shown "
        "separately below."
    )
    stmt = _statement_lines(d)
    claim = next((ln for ln in stmt if "T1 claim" in ln), None)
    sensitivity = next((ln for ln in stmt if ln.startswith("**Post-hoc sensitivity")), None)
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
            where=lambda r: r["role"] != "reference",
            digits=4,
            title="Scores against the controls (negative zrs-mox, positive zrs-zng)",
        ),
        ("**Result statement:** " + claim.replace("**", ""))
        + (f"\n\n**Sensitivity:** {sensitivity.replace('**', '')}" if sensitivity else "")
        if claim
        else pending("similarity_summary"),
        figure("similarity_controls", "Where cleanflate falls between the controls.", d),
        sections.similarity_supplement(d, cfg).text,
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
    return section(title, *blocks, level=level)


def effort_section(d: Path, level: int = 2) -> str:
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
    return section("Effort, cost and provenance", *blocks, level=level)


def findings_section(d: Path, level: int = 2) -> str:
    p = d / "findings.md"
    body = "See [findings.md](findings.md) for bugs found in cleanflate. They are recorded there and never patched in this repo."
    if p.exists():
        entries = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith("- ")]
        body += (
            f" The file currently lists {len(entries)} entries."
            if entries
            else " The file currently lists no entries."
        )
    return section("Findings for the cleanflate repo", body, level=level)


def threats_section(d: Path, cfg: dict, level: int = 2) -> str:
    return section(
        "Threats to validity", sections.threats_markdown(d, cfg, level=level + 1), level=level
    )


def claims_section(d: Path, cfg: dict, level: int = 2) -> str:
    results = claims_mod.evaluate(d, cfg)
    lead = sections.claims_map(results, cfg)
    return section(
        "Claims and evidence",
        lead.text,
        f"{'#' * (level + 1)} Checked and not claimed\n\n" + sections.overreach(results),
        level=level,
    )


def appendix(d: Path, cfg: dict) -> str:
    perfile = section("Per-file throughput", *(
        [per_file_block(d, cfg)] if machines_in("perf_cells", d) else [pending("perf_cells")]), level=3)  # fmt: skip
    tiny = section("Tiny inputs (setup cost)", tiny_block(d), level=3)
    return section(
        "Appendix",
        "Supporting detail behind the sections above: the setup, per-file tables, tiny-input timing, content "
        "correlations and binary size.",
        environments(d, level=3),
        subjects_and_pins(level=3),
        perfile,
        tiny,
        content_section(d, level=3),
        appendix_binary_size(d, level=3),
    )


TITLES = ["Claims and evidence", "Equivalence", "Safety", "Clean-room", "Effort, cost and provenance",
          "Viability", "Iteration", "Findings for the cleanflate repo", "Threats to validity", "Appendix"]  # fmt: skip


def render_sections(results_dir: Path | None = None, cfg: dict | None = None) -> str:
    d = Path(results_dir) if results_dir else paths.RESULTS
    cfg = cfg or config.load_config("full")
    parts = [
        claims_section(d, cfg),
        equivalence_section(d, cfg),
        safety_section(d),
        clean_room_section(d, cfg),
        effort_section(d),
        viability_section(d, cfg),
        iteration_section(d, cfg),
        findings_section(d),
        threats_section(d, cfg),
        appendix(d, cfg),
    ]
    return "\n\n".join(parts) + "\n"


HEADER = "<!-- generated by cfbench.kits.results_md; do not edit -->"


def render(results_dir: Path | None = None, cfg: dict | None = None) -> str:
    intro = (
        f"Results for {PIPELINE_NAME}, organised around its claims. {EXAMPLE} is the worked example; every "
        "number traces to a derived table, a committed raw file and a script (the source line under each table)."
    )
    return "\n".join(
        [
            HEADER,
            "",
            f"# Results: {PIPELINE_NAME}",
            "",
            intro,
            "",
            render_sections(results_dir, cfg),
        ]
    )


def main() -> int:
    out = paths.RESULTS / "RESULTS.md"
    out.write_text(render(), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
