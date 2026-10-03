"""Claims about the pipeline, checked against the derived tables (SPEC 5 T1, 6).

The subject is the pipeline (`pipeline.PIPELINE_NAME`); cleanflate is the worked example. Each
claim belongs to one category, in the order `pipeline.CATEGORIES` gives (equivalence, safety,
clean-room, effort, viability, iteration). Each comes out `supported`, `rejected` or `pending`.
Every number in a claim's text is an `Evidence.display`, so it traces to a table row, raw files
and a script. The overreach checks after the main claims are rejected unless the data supports
them.
"""

from dataclasses import dataclass, field
from pathlib import Path

from cfbench import config, paths
from cfbench.kits import evidence as ev
from cfbench.kits import pipeline
from cfbench.kits.evidence import Evidence, MissingData
from cfbench.kits.pipeline import EXAMPLE, PIPELINE_NAME

SUPPORTED, REJECTED, PENDING = "supported", "rejected", "pending"
CATEGORY = {
    "conformance": "equivalence",
    "fuzz": "equivalence",
    "malformed": "equivalence",
    "safety": "safety",
    "similarity": "clean_room",
    "isolation": "clean_room",
    "effort": "effort",
    "perf_range": "viability",
    "trajectory": "iteration",
    "parity_with_zlib": "viability",
    "faster_than_zrs": "viability",
    "faster_than_mox": "viability",
    "gzip_gap_is_hw_crc": "viability",
}
MAIN = ["conformance", "fuzz", "malformed", "safety", "similarity", "isolation", "effort",
        "perf_range", "trajectory"]  # fmt: skip
OVERREACH = ["parity_with_zlib", "faster_than_zrs", "faster_than_mox", "gzip_gap_is_hw_crc"]
ORDER = MAIN + OVERREACH
UNSAFE_COUNTS = [
    "unsafe_blocks",
    "unsafe_fns",
    "unsafe_impls",
    "unsafe_traits",
    "target_feature_attrs",
]
X = "{:.2f}x"
INT = "{:.0f}"
THOUSANDS = "{:,.0f}"


@dataclass(frozen=True)
class ClaimResult:
    id: str
    status: str
    text: str
    evidence: list[Evidence] = field(default_factory=list)
    reason: str = ""

    @property
    def category(self) -> str:
        return CATEGORY[self.id]


def _pending(cid: str, e: MissingData, text: str = "") -> ClaimResult:
    return ClaimResult(cid, PENDING, text, [], str(e))


def _machines(cfg) -> list[str]:
    return cfg["paper"]["machines"]


def _not_run(machine: str, table: str) -> str:
    why = pipeline.not_run_reason(machine, table)
    return (
        f"not run on {machine} ({why})"
        if why
        else f"not run on {machine} (run `{ev.TARGETS.get(table, 'make all')}` there)"
    )


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


# ---- equivalence ----------------------------------------------------------------------------


def _conformance(d, cfg) -> ClaimResult:
    try:
        rows, _ = ev.table_rows("conformance", d)
        dis, _ = ev.table_rows("conformance_disagreements", d)
    except MissingData as e:
        return _pending("conformance", e)
    measured = {r["machine"] for r in rows if r["subject"] == "cf"}
    if not measured:
        return _pending(
            "conformance", MissingData("no cleanflate row in conformance: run `make conformance`")
        )
    evid, parts, gaps, problems = [], [], [], []
    for m in _machines(cfg):
        if m not in measured:
            gaps.append(_not_run(m, "conformance"))
            continue
        key = {"machine": m, "subject": "cf"}
        streams = ev.lookup("conformance", key, "streams", results_dir=d, fmt=INT)
        passed = ev.lookup("conformance", key, "passed", results_dir=d, fmt=INT)
        rate = ev.lookup("conformance", key, "pass_rate", results_dir=d, fmt="{:.4f}")
        evid += [streams, passed, rate]
        parts.append(f"{passed.display} of {streams.display} streams on {m}")
        if not (rate.value == 1.0 and streams.value > 0):
            problems.append(f"{m}: pass rate {rate.display}")
    cf_dis = [x for x in dis if x["subject"] == "cf"]
    if cf_dis:
        problems.append(f"{len(cf_dis)} cleanflate disagreements listed")
    if problems:
        return ClaimResult("conformance", REJECTED, "", evid, "; ".join(problems))
    text = (
        f"{EXAMPLE}'s output matched the expected SHA-256 and length for {_join(parts)}, with no "
        "disagreement" + (f"; {_join(gaps)}" if gaps else "") + "."
    )
    return ClaimResult("conformance", SUPPORTED, text, evid)


def _fuzz(d, cfg) -> ClaimResult:
    try:
        rows, _ = ev.table_rows("fuzz_stats", d)
    except MissingData as e:
        return _pending("fuzz", e)
    targets = cfg["fuzz"]["targets"]
    evid, parts, gaps, problems = [], [], [], []
    for m in _machines(cfg):
        mine = {r["target"] for r in rows if r["machine"] == m}
        if not mine:
            gaps.append(_not_run(m, "fuzz_stats"))
            continue
        per, budgets = [], []
        for t in targets:
            if t not in mine:
                gaps.append(f"{t} not run on {m}")
                continue
            key = {"machine": m, "target": t}
            execs = ev.lookup("fuzz_stats", key, "executions", results_dir=d, fmt=THOUSANDS)
            div = ev.lookup("fuzz_stats", key, "divergences", results_dir=d, fmt=INT)
            hours = ev.lookup("fuzz_stats", key, "budget_cpu_hours", results_dir=d, fmt="{:g}")
            evid += [execs, div, hours]
            budgets.append(hours)
            per.append(f"{div.display} divergences in {execs.display} executions for {t}")
            if div.value != 0:
                problems.append(f"{t} on {m}: {div.display} divergences")
        if per:
            same = len({b.display for b in budgets}) == 1
            budget = (
                f"{budgets[0].display} CPU-hours per pair" if same else "budgets as in fuzz_stats"
            )
            parts.append(f"on {m} it found {_join(per)} ({budget})")
    if not parts:
        return _pending(
            "fuzz", MissingData("no fuzz rows for the configured targets: run `make fuzz`")
        )
    if problems:
        return ClaimResult("fuzz", REJECTED, "", evid, "; ".join(problems))
    text = (
        f"Differential fuzzing of {EXAMPLE} against each reference decoder: "
        + "; ".join(parts)
        + (f". Fuzzing was {_join(gaps)}." if gaps else ".")
    )
    return ClaimResult("fuzz", SUPPORTED, text, evid)


def _malformed(d, cfg) -> ClaimResult:
    try:
        rows, _ = ev.table_rows("malformed_summary", d)
    except MissingData as e:
        return _pending("malformed", e)
    measured = {r["machine"] for r in rows}
    evid, parts, gaps, problems = [], [], [], []
    for m in _machines(cfg):
        if m not in measured:
            gaps.append(_not_run(m, "malformed_summary"))
            continue
        key = {"machine": m}
        files = ev.lookup("malformed_summary", key, "cf_expected_files", results_dir=d, fmt=INT)
        match = ev.lookup("malformed_summary", key, "cf_matches_expected", results_dir=d, fmt=INT)
        dis = ev.lookup("malformed_summary", key, "disagreements", results_dir=d, fmt=INT)
        strict = ev.lookup(
            "malformed_summary", key, "disagreements_cf_stricter", results_dir=d, fmt=INT
        )
        evid += [files, match, dis, strict]
        how = ("all of them cf rejecting what every other supported decoder accepts" if strict.value == dis.value
               else f"{strict.display} of them cf being the stricter decoder")  # fmt: skip
        parts.append(
            f"on {m} cf's outcome matched EXPECTED.tsv for {match.display} of {files.display} files, and "
            f"subjects disagreed on accept versus reject for {dis.display} files, {how}"
        )
        if match.value != files.value:
            problems.append(
                f"{m}: cf matched EXPECTED.tsv for {match.display} of {files.display} files"
            )
    if not parts:
        return _pending("malformed", MissingData("no malformed summary rows: run `make malformed`"))
    if problems:
        return ClaimResult("malformed", REJECTED, "", evid, "; ".join(problems))
    text = (
        f"On {EXAMPLE}'s malformed-input suite, " + "; ".join(parts)
        + (f"; {_join(gaps)}" if gaps else "")
        + ". The strictness is a documented default (trailing data and a bad second gzip member are errors), not a decoding difference."
    )  # fmt: skip
    return ClaimResult("malformed", SUPPORTED, text, evid)


# ---- safety ---------------------------------------------------------------------------------


def _safety(d, cfg) -> ClaimResult:
    try:
        rows, _ = ev.table_rows("unsafe", d)
        ev.table_rows("deps", d)
    except MissingData as e:
        return _pending("safety", e)
    evid, problems = [], []
    subj = [r for r in rows if r["subject"] == "cf" and r["role"] == "subject"]
    if not subj:
        return _pending("safety", MissingData("no cleanflate row in unsafe: run `make size`"))
    key = {"subject": "cf", "role": "subject"}
    for c in UNSAFE_COUNTS:
        e = ev.lookup("unsafe", key, c, results_dir=d, fmt=INT)
        evid.append(e)
        if e.value != 0:
            problems.append(f"{c} = {e.display}")
    forbid = ev.lookup("unsafe", key, "forbid_unsafe_code", results_dir=d)
    evid.append(forbid)
    if forbid.value != "true":
        problems.append("forbid_unsafe_code is not set")
    deps_key = {"subject": "cf"}
    direct = ev.lookup("deps", deps_key, "direct_count", results_dir=d, fmt=INT)
    trans = ev.lookup("deps", deps_key, "transitive_count", results_dir=d, fmt=INT)
    evid += [direct, trans]
    if direct.value != 0 or trans.value != 0:
        problems.append(
            f"{direct.display} direct and {trans.display} transitive runtime dependencies"
        )
    if problems:
        return ClaimResult("safety", REJECTED, "", evid, "; ".join(problems))
    text = (
        f"{EXAMPLE} has {evid[0].display} unsafe blocks, functions, impls, traits and target-feature "
        f"attributes, forbids unsafe code, and has {direct.display} direct and {trans.display} transitive "
        "runtime dependencies."
    )
    return ClaimResult("safety", SUPPORTED, text, evid)


# ---- clean room -----------------------------------------------------------------------------


def _similarity(d: Path, cfg) -> ClaimResult:
    stmt = d / "similarity_statement.md"
    if not stmt.exists():
        return _pending(
            "similarity", MissingData("similarity_statement.md is missing: run `make similarity`")
        )
    text = stmt.read_text(encoding="utf-8")
    if "Pending" in text and "T1 claim" not in text:
        return _pending(
            "similarity", MissingData("similarity statement is pending: run `make similarity`")
        )
    evid, detail = _similarity_scores(d)
    if "T1 claim allowed" in text and "NOT allowed" not in text:
        claim = (f"{EXAMPLE}'s code similarity to zlib-rs and miniz_oxide sits at or near the independent-implementation "
                 "baseline" + (f": {detail}." if detail else "."))  # fmt: skip
        return ClaimResult("similarity", SUPPORTED, claim, evid)
    why = next(
        (ln for ln in text.splitlines() if "T1 claim" in ln),
        "the generated statement does not allow the claim",
    )
    reason = why.replace("**", "").strip().rstrip(".")
    return ClaimResult(
        "similarity", REJECTED, "", evid, f"{reason}. Scores: {detail}" if detail else reason
    )


def _similarity_scores(d: Path) -> tuple[list[Evidence], str]:
    """Pre-registered metrics whose controls separate: each cf pair's score and position between
    the negative control (0) and the positive control (1), with both control scores."""
    try:
        rows, _ = ev.table_rows("similarity_summary", d)
    except MissingData:
        return [], ""
    metrics = list(dict.fromkeys(r["metric"] for r in rows if r["role"] == "test" and r["position"] != ""
                                 and not r["metric"].endswith("_filtered")))  # fmt: skip
    evid, parts = [], []
    for m in metrics:
        neg = next((r for r in rows if r["metric"] == m and r["role"] == "negative"), None)
        pos = next((r for r in rows if r["metric"] == m and r["role"] == "positive"), None)
        if not neg:
            continue
        ne = ev.lookup(
            "similarity_summary",
            {"metric": m, "pair": neg["pair"]},
            "score",
            results_dir=d,
            fmt="{:.3g}",
        )
        pe = (ev.lookup("similarity_summary", {"metric": m, "pair": pos["pair"]}, "score", results_dir=d, fmt="{:.3g}")
              if pos else None)  # fmt: skip
        evid += [ne] + ([pe] if pe else [])
        pos_txt = (
            f"positive control {pos['pair']} {pe.display}" if pos and pe else "no positive control"
        )
        pairs = []
        for pair in ("cf-zrs", "cf-mox"):
            if not any(r["metric"] == m and r["pair"] == pair for r in rows):
                continue
            sc = ev.lookup(
                "similarity_summary",
                {"metric": m, "pair": pair},
                "score",
                results_dir=d,
                fmt="{:.3g}",
            )
            cl = ev.lookup(
                "similarity_summary", {"metric": m, "pair": pair}, "classification", results_dir=d
            )
            evid += [sc, cl]
            pairs.append(f"{pair} {sc.display} ({cl.display})")
        parts.append(
            f"`{m}` negative control {neg['pair']} {ne.display}, {pos_txt}, " + ", ".join(pairs)
        )
    return evid, "; ".join(parts)


def _isolation(d, cfg) -> ClaimResult:
    key = {"round": "total"}
    try:
        denied = ev.lookup("effort_totals", key, "denied_calls", results_dir=d, fmt=INT)
        reads = ev.lookup("effort_totals", key, "read_calls", results_dir=d, fmt=THOUSANDS)
        cands = ev.lookup("effort_totals", key, "forbidden_read_candidates", results_dir=d, fmt=INT)
        forbidden = ev.lookup("effort_totals", key, "forbidden_reads", results_dir=d, fmt=INT)
    except MissingData as e:
        return _pending("isolation", e)
    evid = [denied, reads, cands, forbidden]
    if forbidden.value != 0:
        return ClaimResult("isolation", REJECTED, "", evid,
                           f"the provenance audit found {forbidden.display} forbidden reads among {reads.display} read-capable calls")  # fmt: skip
    text = (
        f"{PIPELINE_NAME}'s guard denied {denied.display} tool calls during the build. An audit of the "
        f"{reads.display} allowed read-capable calls in {EXAMPLE}'s provenance log found {forbidden.display} reads of "
        f"prior art ({cands.display} {'candidate' if cands.value == 1 else 'candidates'}, classified by hand in "
        "`config/forbidden_read_verdicts.toml`). "
        "The log sees top-level tool calls only, so this bounds isolation rather than proving it."
    )
    return ClaimResult("isolation", SUPPORTED, text, evid)


# ---- effort ---------------------------------------------------------------------------------


def _effort(d, cfg) -> ClaimResult:
    try:
        wall = ev.lookup(
            "effort_totals",
            {"round": "total"},
            "wall_clock_s",
            results_dir=d,
            fmt="{:.1f}",
            transform=lambda s: s / 3600,
        )
    except MissingData as e:
        return _pending("effort", e)
    evid = [wall]
    cost = inter = None
    try:
        cost = ev.lookup(
            "effort_totals", {"round": "total"}, "cost_usd", results_dir=d, fmt="${:,.0f}"
        )
    except MissingData:
        pass
    try:
        inter = ev.lookup(
            "effort_totals", {"round": "total"}, "interventions", results_dir=d, fmt=INT
        )
    except MissingData:
        pass
    text = f"{PIPELINE_NAME}'s three rounds building {EXAMPLE} took {wall.display} hours of attributed wall-clock time"
    if cost is not None:
        evid.append(cost)
        text += f", an estimated {cost.display} of model cost"
    else:
        text += ", unpriced model cost (see EFFORT_GAPS.md)"
    if inter is not None:
        evid.append(inter)
        text += f" and {inter.display} recorded human interventions."
    else:
        text += "; human interventions are not tallied in the effort table."
    return ClaimResult("effort", SUPPORTED, text, evid)


# ---- viability ------------------------------------------------------------------------------


def _grid(cfg: dict) -> list[tuple[str, str, int]]:
    p = cfg["paper"]
    return [
        (m, f, lv) for m in p["machines"] for f in p["perf_framings"] for lv in p["perf_levels"]
    ]


def _key(cfg, subject, machine, framing, level) -> dict:
    p = cfg["paper"]
    return {"machine": machine, "variant": p["perf_variant"], "subject": subject, "corpus": p["perf_corpus"],
            "level": level, "framing": framing, "mode": p["perf_mode"]}  # fmt: skip


def _ratio(
    d, cfg, subject: str, machine: str, framing: str, level: int
) -> tuple[Evidence, Evidence]:
    key = _key(cfg, subject, machine, framing, level)
    ratio = ev.lookup("perf_aggregates", key, "ratio_vs_zlib", results_dir=d, fmt=X)
    complete = ev.lookup("perf_aggregates", key, "complete", results_dir=d)
    return ratio, complete


def flagged(d, cfg, subject: str, machine: str, framing: str, level: int) -> Evidence:
    """Whether the run-to-run agreement flagged this aggregate (SPEC 3.2: report, flagged)."""
    return ev.lookup("perf_agreement_aggregates", _key(cfg, subject, machine, framing, level),
                     "flagged", results_dir=d)  # fmt: skip


def _perf_ratios(d, cfg, subject: str) -> list[tuple[tuple, Evidence]]:
    """Ratios for the whole grid, or MissingData; requires complete aggregates on every machine.

    A machine whose runs disagree is not a reason to withhold its numbers: SPEC 3.2 says results
    outside +-5% are flagged, so callers report per-cell flags next to the ratios.
    """
    out = []
    for m, f, lv in _grid(cfg):
        ratio, complete = _ratio(d, cfg, subject, m, f, lv)
        if complete.value != "true":
            raise MissingData(
                f"{subject} aggregate for {m} {f} level {lv} is incomplete: rerun `make perf`"
            )
        out.append(((m, f, lv), ratio))
    return out


def _perf_range(d, cfg) -> ClaimResult:
    try:
        cells = _perf_ratios(d, cfg, "cf")
        flags = [flagged(d, cfg, s, *k) for k, _ in cells for s in ("cf", "zlib")]
        verdicts = [ev.lookup("perf_agreement_summary", {"machine": m, "variant": cfg["paper"]["perf_variant"]},
                              "verdict", results_dir=d) for m in _machines(cfg)]  # fmt: skip
    except MissingData as e:
        return _pending("perf_range", e)
    vals = [e for _, e in cells]
    lo, hi = min(vals, key=lambda e: e.value), max(vals, key=lambda e: e.value)
    n_flag = sum(1 for f in flags if f.value == "true")
    p = cfg["paper"]
    stab = ", ".join(f"{m} {v.display}" for m, v in zip(_machines(cfg), verdicts, strict=True))
    flag_txt = ("no cf or zlib aggregate behind these ratios is flagged by run-to-run agreement" if n_flag == 0
                else "some cf or zlib aggregates behind these ratios are flagged by run-to-run agreement (see the viability table)")  # fmt: skip
    text = (
        f"On the {p['perf_corpus'].title()} corpus, {EXAMPLE}'s {p['perf_mode']} decompression throughput at levels "
        f"{' and '.join(map(str, p['perf_levels']))} in {' and '.join(p['perf_framings'])} framing is "
        f"{lo.display} to {hi.display} that of stock zlib (zlib = 1.00x) on {' and '.join(p['machines'])}; "
        f"{flag_txt} (session verdicts: {stab})."
    )
    return ClaimResult("perf_range", SUPPORTED, text, vals + flags + verdicts)


# ---- iteration ------------------------------------------------------------------------------


def _trajectory(d, cfg) -> ClaimResult:
    p = cfg["paper"]
    evid, parts, problems = [], [], []
    try:
        for m in p["machines"]:
            series = []
            for rnd in (1, 2, 3):
                key = {"machine": m, "round": rnd, "corpus": p["perf_corpus"], "framing": p["trajectory_framing"],
                       "mode": p["trajectory_mode"], "level": p["trajectory_level"]}  # fmt: skip
                series.append(ev.lookup("trajectory", key, "ratio_vs_zlib", results_dir=d, fmt=X))
            evid += series
            r1, r2, r3 = series
            note = "" if r1.value <= r2.value <= r3.value else " (not monotonic)"
            parts.append(f"{m}: {r1.display}, {r2.display}, {r3.display}{note}")
            if not r3.value > r1.value:
                problems.append(f"{m}: round 3 ({r3.display}) is not above round 1 ({r1.display})")
    except MissingData as e:
        return _pending("trajectory", e)
    if problems:
        return ClaimResult("trajectory", REJECTED, "", evid, "; ".join(problems))
    text = (
        f"On {p['perf_corpus'].title()} {p['trajectory_framing']} level {p['trajectory_level']} {p['trajectory_mode']}, "
        f"{EXAMPLE}'s throughput relative to zlib across {PIPELINE_NAME} rounds 1, 2 and 3 was "
        + "; ".join(parts)
        + "."
    )
    return ClaimResult("trajectory", SUPPORTED, text, evid)


# ---- overreach checks -----------------------------------------------------------------------


def _reject_by_default(cid: str, reason: str) -> ClaimResult:
    return ClaimResult(cid, REJECTED, "", [], reason)


def _parity(d, cfg) -> ClaimResult:
    try:
        cells = _perf_ratios(d, cfg, "cf")
    except MissingData as e:
        return _reject_by_default("parity_with_zlib", f"no data supports it ({e})")
    threshold = cfg["paper"]["parity_ratio"]
    below = [(k, e) for k, e in cells if e.value < threshold]
    if below:
        worst = min(cells, key=lambda c: c[1].value)[1]
        return ClaimResult("parity_with_zlib", REJECTED, "", [e for _, e in cells],
                           f"{len(below)} of {len(cells)} cells are below {threshold:.2f}x; the lowest is {worst.display}")  # fmt: skip
    return ClaimResult("parity_with_zlib", SUPPORTED,
                       f"{EXAMPLE} reaches at least {threshold:.2f}x of zlib's throughput in every measured cell.",
                       [e for _, e in cells])  # fmt: skip


def _faster_than(cid: str, other: str, d, cfg) -> ClaimResult:
    try:
        cf = _perf_ratios(d, cfg, "cf")
        theirs = _perf_ratios(d, cfg, other)
    except MissingData as e:
        return _reject_by_default(cid, f"no data supports it ({e})")
    evid, slower = [], []
    for (k, a), (_k, b) in zip(cf, theirs, strict=True):
        evid += [a, b]
        if not a.value > b.value:
            slower.append(f"{k[0]} {k[1]} L{k[2]}: cf {a.display} vs {other} {b.display}")
    if slower:
        return ClaimResult(
            cid,
            REJECTED,
            "",
            evid,
            f"{EXAMPLE} is not faster in {len(slower)} cells, e.g. {slower[0]}",
        )
    return ClaimResult(
        cid, SUPPORTED, f"{EXAMPLE} is faster than {other} in every measured cell.", evid
    )


def _gzip_gap(d, cfg) -> ClaimResult:
    try:
        v = ev.lookup("framing_hypothesis", {"machine": "ALL"}, "verdict", results_dir=d)
    except MissingData as e:
        return _pending("gzip_gap_is_hw_crc", e)
    if v.value == "confirmed":
        return ClaimResult("gzip_gap_is_hw_crc", SUPPORTED,
                           f"{EXAMPLE}'s gzip framing penalty is consistent with stock zlib's penalty with hardware CRC disabled.", [v])  # fmt: skip
    return ClaimResult(
        "gzip_gap_is_hw_crc", REJECTED, "", [v], f"the framing hypothesis verdict is {v.display}"
    )


FNS = {
    "conformance": _conformance,
    "fuzz": _fuzz,
    "malformed": _malformed,
    "safety": _safety,
    "similarity": _similarity,
    "isolation": _isolation,
    "effort": _effort,
    "perf_range": _perf_range,
    "trajectory": _trajectory,
    "parity_with_zlib": _parity,
    "faster_than_zrs": lambda d, c: _faster_than("faster_than_zrs", "zrs", d, c),
    "faster_than_mox": lambda d, c: _faster_than("faster_than_mox", "mox", d, c),
    "gzip_gap_is_hw_crc": _gzip_gap,
}


def evaluate(results_dir: Path | None = None, cfg: dict | None = None) -> list[ClaimResult]:
    d = Path(results_dir) if results_dir else paths.RESULTS
    cfg = cfg or config.load_config("full")
    return [FNS[cid](d, cfg) for cid in ORDER]
