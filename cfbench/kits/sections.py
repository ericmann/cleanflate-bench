"""Blocks every kit shares: the claims map, the two-machine viability table, the cross-machine
checks and the threats to validity (SPEC 5, 6).

Every number is an `Evidence.display` from `kits.evidence.lookup`; a missing cell renders as
`pending` (or `n/a` when the subject does not support the framing), never as a guess. Each block
returns Markdown with the parity note after every table and a source line naming the tables.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from cfbench import config, paths
from cfbench.kits import claims as claims_mod
from cfbench.kits import evidence as ev
from cfbench.kits import pipeline
from cfbench.kits.evidence import Evidence, MissingData
from cfbench.kits.pipeline import CATEGORIES, EXAMPLE, PIPELINE_NAME
from cfbench.parity import PARITY_NOTE

PENDING, NA = "pending", "n/a"
FLAG_MARK = "†"
STATUS_LABEL = {"supported": "Supported", "rejected": "Not supported", "pending": "Pending"}
VARIANT_SUBJECT = {"generic": "cf", "native": "cf@native"}


@dataclass
class Block:
    """Rendered Markdown plus the evidence behind every number in it."""

    text: str
    evidence: list[Evidence] = field(default_factory=list)


def table(columns: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(columns) + " |"
    sep = "|" + "|".join(["---"] * len(columns)) + "|"
    body = ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body]) + f"\n\n*{PARITY_NOTE}*"


def sources(evid: list[Evidence]) -> str:
    """`Source: results/<table>.csv <- <raw files> via <script>` for each distinct table."""
    groups: OrderedDict[tuple, None] = OrderedDict()
    for e in evid:
        groups[(e.table, e.script, e.raw_files)] = None
    parts = []
    for tbl, script, raws in groups:
        raw = ", ".join(f"`{r}`" for r in raws) or "no raw file"
        parts.append(f"`results/{tbl}.csv` <- {raw} via `{script}`")
    return "Source: " + "; ".join(parts) if parts else ""


def pending_text(table_name: str, e: MissingData) -> str:
    """`Pending: run `make X` on M-A and M-B (why).`, the form every kit uses for missing data."""
    return f"Pending: run `{ev.TARGETS.get(table_name, 'make all')}` on M-A and M-B ({str(e).rstrip('.')})."


def _look(table_name, where, column, d, **kw) -> Evidence | None:
    try:
        return ev.lookup(table_name, where, column, results_dir=d, **kw)
    except MissingData:
        return None


def _unsupported(d: Path, machine: str, variant: str, subject: str, framing: str) -> bool:
    try:
        rows, _ = ev.table_rows("perf_cells", d)
    except MissingData:
        return False
    return any(r["machine"] == machine and r["variant"] == variant and r["subject"] == subject
               and r["framing"] == framing and r["status"] == "unsupported" for r in rows)  # fmt: skip


# ---- claims map ------------------------------------------------------------------------------


def claims_map(results: list, cfg: dict) -> Block:
    """Lead block: the thesis, a status table in category order, then each claim with its source."""
    by_cat: dict[str, list] = {c.key: [] for c in CATEGORIES}
    for c in results:
        if c.id in claims_mod.MAIN:
            by_cat[c.category].append(c)
    rows = []
    for cat in CATEGORIES:
        for c in by_cat[cat.key]:
            tables = sorted({e.table for e in c.evidence})
            rows.append([cat.title, f"`{c.id}`", STATUS_LABEL[c.status],
                         ", ".join(f"`{t}`" for t in tables) or "none yet"])  # fmt: skip
    lines = [
        pipeline.thesis(),
        "",
        table(["Category", "Claim", "Status", "Evidence tables"], rows),
        "",
    ]
    evid: list[Evidence] = []
    n = 0
    for cat in CATEGORIES:
        lines += [f"### {cat.title}", "", f"*{cat.question}*", ""]
        for c in by_cat[cat.key]:
            n += 1
            evid += c.evidence
            if c.status == claims_mod.SUPPORTED:
                lines += [
                    f"{n}. **Supported** (`{c.id}`): {c.text}",
                    f"   {sources(c.evidence)}",
                    "",
                ]
            elif c.status == claims_mod.REJECTED:
                lines += [f"{n}. **Not supported** (`{c.id}`): {c.reason.rstrip('.')}."]
                if c.evidence:
                    lines.append(f"   {sources(c.evidence)}")
                lines.append("")
            else:
                lines += [f"{n}. **Pending** (`{c.id}`): {c.reason.rstrip('.')}.", ""]
    return Block("\n".join(lines).rstrip("\n"), evid)


def overreach(results: list) -> str:
    """The overreach checks, stated whatever their outcome."""
    out = []
    for c in results:
        if c.id not in claims_mod.OVERREACH:
            continue
        body = c.text if c.status == claims_mod.SUPPORTED else c.reason
        out.append(f"- **{c.id}** ({STATUS_LABEL[c.status].lower()}): {body}")
    return "\n".join(out) or "None."


# ---- viability: both machines in one table --------------------------------------------------


def viability_table(d: Path, cfg: dict) -> Block:
    """cf ratio vs zlib for every corpus x framing at the paper level, one-shot, on both machines,
    generic and native, with the agreement flag (†) on cells the two runs disagree on."""
    p = cfg["paper"]
    machines = p["machines"]
    level, mode = p["figure_level"], p["figure_mode"]
    cols = ["Corpus", "Framing"] + [f"{m} {v}" for v in VARIANT_SUBJECT for m in machines]
    rows, evid, flagged_any = [], [], False
    for corpus in cfg["perf"]["corpora"]:
        for framing in cfg["perf"]["framings"]:
            row = [corpus.title(), framing]
            for variant, subject in VARIANT_SUBJECT.items():
                for m in machines:
                    key = {"machine": m, "variant": variant, "subject": subject, "corpus": corpus,
                           "level": level, "framing": framing, "mode": mode}  # fmt: skip
                    r = _look("perf_aggregates", key, "ratio_vs_zlib", d, fmt="{:.2f}x")
                    if r is None:
                        row.append(NA if _unsupported(d, m, variant, subject, framing) else PENDING)
                        continue
                    fs = [
                        _look("perf_agreement_aggregates", {**key, "subject": s}, "flagged", d)
                        for s in (subject, "zlib")
                    ]
                    evid += [r] + [f for f in fs if f]
                    mark = FLAG_MARK if any(f is not None and f.value == "true" for f in fs) else ""
                    flagged_any = flagged_any or bool(mark)
                    row.append(r.display + mark)
            rows.append(row)
    note = (f"{EXAMPLE}'s aggregate throughput as a ratio of stock zlib's (zlib = 1.00x) at level {level}, "
            f"{mode}, per machine and build variant (native = `target-cpu=native` Rust builds against the same zlib). "
            + (f"{FLAG_MARK} marks a ratio whose cf or zlib aggregate differs between the two runs by more than the agreement tolerance."
               if flagged_any else f"No cell in this table is flagged by run-to-run agreement ({FLAG_MARK} would mark one)."))  # fmt: skip
    return Block("\n\n".join([note, table(cols, rows), sources(evid)]), evid)


# ---- cross-machine checks -------------------------------------------------------------------


def _lock_note(machine: str) -> str:
    return f"`subjects.lock.json` machines.{machine}.builds.zlib.hw_crc"


def gzip_gap_block(d: Path, cfg: dict) -> Block:
    """gzip minus raw ratio per machine with each machine's hardware-CRC determination."""
    p = cfg["paper"]
    try:
        rows, _ = ev.table_rows("crossmachine_gzip_gap", d)
    except MissingData as e:
        return Block(pending_text("crossmachine_gzip_gap", e))
    body, evid, gaps = [], [], {}
    for r in rows:
        key = {k: r[k] for k in ("machine", "variant", "subject", "corpus")}
        raw = _look("crossmachine_gzip_gap", key, "ratio_raw", d, fmt="{:.2f}x")
        gz = _look("crossmachine_gzip_gap", key, "ratio_gzip", d, fmt="{:.2f}x")
        gap = _look("crossmachine_gzip_gap", key, "gap_gzip_minus_raw", d, fmt="{:+.3f}")
        zhw = _look("crossmachine_gzip_gap", key, "zlib_hw_crc", d)
        shw = _look("crossmachine_gzip_gap", key, "subject_hw_crc", d)
        got = [x for x in (raw, gz, gap, zhw, shw) if x]
        evid += got
        if gap:
            gaps[(r["variant"], r["corpus"], r["machine"])] = (gap, zhw)
        body.append(
            [
                r["machine"],
                r["variant"],
                r["corpus"].title(),
                *(x.display if x else PENDING for x in (raw, gz, gap, zhw, shw)),
            ]
        )
    machines = p["machines"]
    verdict = _look("framing_hypothesis", {"machine": "ALL"}, "verdict", d)
    if verdict:
        evid.append(verdict)
    lines = [
        f"{EXAMPLE}'s ratio vs zlib in raw and gzip framing at level {p['figure_level']}, {p['figure_mode']}. zlib is 1.00x in "
        "both framings, so the gap (gzip minus raw) is the gzip penalty cf pays beyond zlib's. The hardware-CRC "
        "columns are each machine's determination by disassembly and symbol inspection of the built binary ("
        + "; ".join(_lock_note(m) for m in machines) + ").",
        table(["Machine", "Variant", "Corpus", "cf raw", "cf gzip", "Gap", "zlib hardware CRC", "cf hardware CRC"], body),
    ]  # fmt: skip
    if len(machines) == 2:
        a, b = machines
        larger, hw_split = [], []
        for variant, corpus, m in gaps:
            if m != a or (variant, corpus, b) not in gaps:
                continue
            ga, za = gaps[(variant, corpus, a)]
            gb, zb = gaps[(variant, corpus, b)]
            larger.append(ga.value < gb.value)
            hw_split.append(
                bool(za and zb and za.display.startswith("yes") and zb.display.startswith("no"))
            )
        if larger:
            hw = (
                f" ({a}'s zlib has hardware CRC compiled in; {b}'s does not)"
                if all(hw_split)
                else ""
            )
            lines.append(f"In every compared row the gzip penalty is larger on {a} than on {b}{hw}." if all(larger)
                         else f"The gzip penalty is not consistently larger on {a} than on {b}{hw}.")  # fmt: skip
    if verdict:
        lines.append(
            f"This is descriptive. The pre-registered framing hypothesis (cf's gzip overhead matches stock zlib's with "
            f"hardware CRC disabled) came out **{verdict.display}**; see `framing_hypothesis` in RESULTS.md."
        )
    lines.append(sources(evid))
    return Block("\n\n".join(x for x in lines if x), evid)


def sleep_check_block(d: Path, cfg: dict) -> Block:
    """Round-3 trajectory ratio against the perf ratio, on every machine with both."""
    try:
        rows, _ = ev.table_rows("crossmachine_sleep_check", d)
    except MissingData as e:
        return Block(pending_text("crossmachine_sleep_check", e))
    body, evid, by_machine = [], [], {}
    for r in rows:
        key = {k: r[k] for k in ("machine", "corpus", "framing")}
        cells = [_look("crossmachine_sleep_check", key, c, d, fmt=f) for c, f in
                 (("trajectory_ratio", "{:.3f}x"), ("perf_ratio", "{:.3f}x"), ("rel_diff", "{:+.1%}"),
                  ("tolerance", "{:.0%}"), ("verdict", None), ("session_span_h", "{:.1f}"))]  # fmt: skip
        evid += [c for c in cells if c]
        by_machine.setdefault(r["machine"], []).append(cells[4].display if cells[4] else "")
        body.append(
            [
                r["machine"],
                r["corpus"].title(),
                r["framing"],
                *(c.display if c else PENDING for c in cells),
            ]
        )
    rnd = rows[0]["trajectory_round"] if rows else "3"
    lines = [
        (
            f"The trajectory stage rebuilds every round, including the round-{rnd} tag that the perf stage measures, so its round-{rnd} "
            f"ratio should repeat the perf ratio. A sleep or other interruption that distorted the trajectory run would "
            f"show up as a difference beyond the run-to-run agreement tolerance. The session span is the time from the "
            f"trajectory session's start to its raw file."
        ),
        table(["Machine", "Corpus", "Framing", f"Trajectory round {rnd}", "Perf session", "Difference", "Tolerance",
               "Verdict", "Session span (h)"], body),
    ]  # fmt: skip
    for m, vs in sorted(by_machine.items()):
        state = ("every row is within tolerance" if all(v == "within tolerance" for v in vs)
                 else "at least one row is outside tolerance")  # fmt: skip
        lines.append(f"- {m}: {state}.")
    sleep = pipeline.note_text("m-a-sleep")
    if sleep:
        lines.append(sleep)
    lines.append(sources(evid))
    return Block("\n\n".join(lines), evid)


def stability_block(d: Path, cfg: dict) -> Block:
    """Both machines' run-to-run agreement verdicts with flagged-cell and flagged-aggregate counts."""
    try:
        rows, _ = ev.table_rows("perf_agreement_summary", d)
    except MissingData as e:
        return Block(pending_text("perf_agreement_summary", e))
    body, evid = [], []
    for r in rows:
        key = {"machine": r["machine"], "variant": r["variant"]}
        cells = [_look("perf_agreement_summary", key, c, d, fmt=f) for c, f in
                 (("runs", "{:.0f}"), ("flagged_cells", "{:.0f}"), ("cells", "{:.0f}"), ("flagged_aggregates", "{:.0f}"),
                  ("aggregates", "{:.0f}"), ("max_abs_rel_diff", "{:.1%}"), ("verdict", None))]  # fmt: skip
        evid += [c for c in cells if c]
        runs, fc, nc, fa, na, mx, v = (c.display if c else PENDING for c in cells)
        body.append([r["machine"], r["variant"], runs, f"{fc} of {nc}", f"{fa} of {na}", mx, v])
    tol = cfg["perf"]["agreement_tolerance"]
    text = "\n\n".join([
        (
            f"Each machine ran the full perf session {cfg['perf']['runs']} times. SPEC 3.2 requires agreement within "
            f"{tol:.0%} of the median, or the result is flagged. A machine is `flagged` when any aggregate (a subject's whole "
            "corpus at one level, framing and mode) moves by more than that; flagged results are reported, not dropped."
        ),
        table(["Machine", "Variant", "Runs", "Flagged cells", "Flagged aggregates", "Max cell difference", "Verdict"], body),
        sources(evid),
    ])  # fmt: skip
    return Block(text, evid)


# ---- threats to validity --------------------------------------------------------------------


def _flagged_counts(d: Path) -> tuple[str, list[Evidence]]:
    try:
        rows, _ = ev.table_rows("perf_agreement_summary", d)
    except MissingData:
        return "Run-to-run agreement is pending (run `make perf` on M-A and M-B).", []
    parts, evid = [], []
    for r in rows:
        key = {"machine": r["machine"], "variant": r["variant"]}
        fa = _look("perf_agreement_summary", key, "flagged_aggregates", d, fmt="{:.0f}")
        na = _look("perf_agreement_summary", key, "aggregates", d, fmt="{:.0f}")
        v = _look("perf_agreement_summary", key, "verdict", d)
        if fa and na and v:
            evid += [fa, na, v]
            parts.append(
                f"{r['machine']} {r['variant']}: {fa.display} of {na.display} aggregates flagged ({v.display})"
            )
    return "; ".join(parts) + ".", evid


def _fuzz_rates(d: Path, cfg: dict) -> tuple[str, list[Evidence]]:
    try:
        rows, _ = ev.table_rows("fuzz_stats", d)
    except MissingData:
        return (
            f"No full fuzz run is recorded (configured budget {cfg['fuzz']['budget_cpu_hours']} CPU hours per pair).",
            [],
        )
    parts, evid = [], []
    for t in cfg["fuzz"]["targets"]:
        for r in [x for x in rows if x["target"] == t]:
            key = {"machine": r["machine"], "target": t}
            e = _look("fuzz_stats", key, "executions", d, fmt="{:,.0f}")
            s = _look("fuzz_stats", key, "exec_per_s", d, fmt="{:.0f}")
            h = _look("fuzz_stats", key, "budget_cpu_hours", d, fmt="{:g}")
            if e and s and h:
                evid += [e, s, h]
                parts.append(
                    f"{t} on {r['machine']} {e.display} executions at {s.display}/s in {h.display} CPU hours"
                )
    text = (f"Executions per pair, in run order: {'; '.join(parts)} (configured budget "
            f"{cfg['fuzz']['budget_cpu_hours']} CPU hours per pair).") if parts else ""  # fmt: skip
    return text, evid


def _claim_flags(d: Path, cfg: dict) -> str:
    """Whether the headline viability claim rests on any flagged cf or zlib aggregate."""
    try:
        cells = claims_mod._perf_ratios(d, cfg, "cf")
        flags = [claims_mod.flagged(d, cfg, s, *k) for k, _ in cells for s in ("cf", "zlib")]
    except MissingData:
        return "Whether the viability claim rests on a flagged aggregate is pending."
    p = cfg["paper"]
    scope = f"{p['perf_corpus'].title()} {' and '.join(p['perf_framings'])} at levels {' and '.join(map(str, p['perf_levels']))}"
    if any(f.value == "true" for f in flags):
        return f"The viability claim ({scope}) rests on at least one flagged aggregate."
    return f"The viability claim ({scope}) rests on none."


def threats(d: Path, cfg: dict) -> list[tuple[str, str, list[Evidence]]]:
    """(title, paragraph, evidence) for every threat; the order is fixed and nothing is omitted."""
    stmt_path = d / "similarity_statement.md"
    stmt_lines = stmt_path.read_text(encoding="utf-8").splitlines() if stmt_path.exists() else []
    stmt = next((ln.replace("**", "") for ln in stmt_lines if "T1 claim" in ln), None)
    flagged, flag_ev = _flagged_counts(d)
    fuzz, fuzz_ev = _fuzz_rates(d, cfg)
    span = {}
    for m in cfg["paper"]["machines"]:
        r = None
        try:
            rows, _ = ev.table_rows("crossmachine_sleep_check", d)
            r = next((x for x in rows if x["machine"] == m), None)
        except MissingData:
            pass
        if r:
            e = _look(
                "crossmachine_sleep_check",
                {k: r[k] for k in ("machine", "corpus", "framing")},
                "session_span_h",
                d,
                fmt="{:.1f}",
            )
            if e:
                span[m] = e
    span_txt = (
        (
            "Trajectory session spans: "
            + ", ".join(f"{m} {e.display} h" for m, e in sorted(span.items()))
            + ". "
        )
        if span
        else ""
    )
    lock_crc = []
    lock = pipeline_lock()
    for m, info in sorted(lock.get("machines", {}).items()):
        z = info["builds"].get("zlib", {}).get("hw_crc", {}).get("compiled_in")
        lock_crc.append(f"{m}: zlib hardware CRC {'compiled in' if z else 'not compiled in'}")
    items = [
        ("Single case study (n=1 target)",
         (f"Every claim about {PIPELINE_NAME} rests on one target library ({EXAMPLE}, replacing {pipeline.LEGACY}'s inflate) "
          "built once in three rounds by one operator. It is an existence proof that the pipeline can do this, not an "
          "estimate of how often it succeeds, how it fares on other libraries, or how its cost scales."), []),
        ("Run-to-run stability", (f"Flagged aggregates per machine and variant: {flagged} Flagged results stay in "
         f"every table. The viability table marks each ratio that rests on one. {_claim_flags(d, cfg)}"), flag_ev),
        ("M-A sleep during trajectory",
         " ".join(x for x in (pipeline.note_text("m-a-sleep"), span_txt +
         "The sleep-interruption check compares the round-3 trajectory ratios with the perf ratios.") if x), []),
        ("M-A High Power Mode",
         (pipeline.note_text("m-a-high-power") or "") + " Absolute M-A throughput is therefore a High Power Mode figure, "
         "and the default power mode may be slower; ratios against zlib were measured in the same mode and session.", []),
        ("M-B background load",
         (pipeline.note_text("m-b-background-load") or "") + " Background services add noise. Cells ran in randomized "
         "order, which spreads that interference across subjects instead of concentrating it on one, but does not remove it; "
         "it is one plausible source of M-B's flagged aggregates (above).", []),
        ("Fuzz budget and throttling",
         "Fuzzing finds divergences but cannot show their absence. " + fuzz + " " + (pipeline.note_text("fuzz-throttling") or "")
         + " Fewer executions on a pair means that comparison was explored less deeply.", fuzz_ev),
        ("Host-dependent gzip fixtures",
         f"{EXAMPLE}'s conformance corpus records host-dependent hashes for its gzip fixtures (the gzip header OS byte). "
         f"The build's review stage missed this because every review ran on Linux. It is recorded as a finding in "
         f"`results/findings.md`. " + (pipeline.note_text("m-a-fixtures") or ""), []),
        ("Training-data contamination",
         "Model training data cannot be controlled, so resemblance is measured against negative and positive controls "
         "instead of assumed away. " + (stmt or "The similarity statement is pending (run `make similarity`).")
         + " Similarity metrics are proxies: a low score does not prove independence and a high one does not prove copying.", []),
        ("Provenance coverage",
         ("The isolation evidence comes from cleanflate's tool log, which records top-level tool calls. Subprocesses of "
          "make targets and interpreter escapes are not individually logged (cleanflate's provenance/README.md lists the gaps), "
          "so the forbidden-read audit bounds what the pipeline read rather than proving it."), []),
        ("Feature-scope mismatch", f"{EXAMPLE} only decompresses, in safe Rust, with no SIMD and no C ABI. " + PARITY_NOTE, []),
        ("Hardware-CRC asymmetry",
         "Hardware CRC is not equal across subjects or machines (" + ("; ".join(lock_crc) or "no pins recorded")
         + "). The gzip-gap comparison uses that asymmetry as evidence; it is descriptive, not a controlled test.", []),
        ("Effort accounting",
         ("Wall-clock time is attributed from commit gaps, model cost is estimated from token counts and list prices, and "
          "human time is only partly recorded (EFFORT_GAPS.md)."), []),
    ]  # fmt: skip
    return [(t, p.strip(), e) for t, p, e in items]


THREAT_TITLES = ["Single case study (n=1 target)", "Run-to-run stability", "M-A sleep during trajectory",
                 "M-A High Power Mode", "M-B background load", "Fuzz budget and throttling",
                 "Host-dependent gzip fixtures", "Training-data contamination", "Provenance coverage",
                 "Feature-scope mismatch", "Hardware-CRC asymmetry", "Effort accounting"]  # fmt: skip


def pipeline_lock() -> dict:
    import json

    p = paths.ROOT / "subjects.lock.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def threats_markdown(d: Path, cfg: dict, level: int = 3) -> str:
    hashes = "#" * level
    return "\n\n".join(f"{hashes} {t}\n\n{p}" for t, p, _e in threats(d, cfg))


def load_cfg(cfg: dict | None) -> dict:
    return cfg or config.load_config("full")
