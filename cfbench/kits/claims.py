"""Candidate paper claims checked against the derived tables (SPEC 5 T1, 6).

Each claim comes out `supported`, `rejected` or `pending`. Every number in a claim's text is an
`Evidence.display`, so it traces to a table row, raw files and a script. Overreach claims are
rejected unless the data supports them.
"""

from dataclasses import dataclass, field
from pathlib import Path

from cfbench import config, paths
from cfbench.kits import evidence as ev
from cfbench.kits.evidence import Evidence, MissingData

SUPPORTED, REJECTED, PENDING = "supported", "rejected", "pending"
ORDER = [
    "conformance",
    "safety",
    "perf_range",
    "trajectory",
    "similarity",
    "effort",
    "parity_with_zlib",
    "faster_than_zrs",
    "faster_than_mox",
    "gzip_gap_is_hw_crc",
]
UNSAFE_COUNTS = [
    "unsafe_blocks",
    "unsafe_fns",
    "unsafe_impls",
    "unsafe_traits",
    "target_feature_attrs",
]
X = "{:.2f}x"


@dataclass(frozen=True)
class ClaimResult:
    id: str
    status: str
    text: str
    evidence: list[Evidence] = field(default_factory=list)
    reason: str = ""


def _pending(cid: str, e: MissingData, text: str = "") -> ClaimResult:
    return ClaimResult(cid, PENDING, text, [], str(e))


def _conformance(d, cfg) -> ClaimResult:
    try:
        rows, _ = ev.table_rows("conformance", d)
        dis, _ = ev.table_rows("conformance_disagreements", d)
    except MissingData as e:
        return _pending("conformance", e)
    cf_rows = [r for r in rows if r["subject"] == "cf"]
    if not cf_rows:
        return _pending(
            "conformance", MissingData("no cleanflate row in conformance: run `make conformance`")
        )
    evid, parts, problems = [], [], []
    for r in cf_rows:
        m = r["machine"]
        key = {"machine": m, "subject": "cf"}
        streams = ev.lookup("conformance", key, "streams", results_dir=d, fmt="{:.0f}")
        passed = ev.lookup("conformance", key, "passed", results_dir=d, fmt="{:.0f}")
        rate = ev.lookup("conformance", key, "pass_rate", results_dir=d, fmt="{:.4f}")
        evid += [streams, passed, rate]
        parts.append(f"{passed.display} of {streams.display} streams on {m}")
        if not (rate.value == 1.0 and streams.value > 0):
            problems.append(f"{m}: pass rate {rate.display}")
    cf_dis = [x for x in dis if x["subject"] == "cf"]
    if cf_dis:
        problems.append(f"{len(cf_dis)} cleanflate disagreements listed")
    text = (
        "cleanflate's output matched the expected SHA-256 and length for "
        + "; ".join(parts)
        + ", with no disagreement."
    )
    if problems:
        return ClaimResult("conformance", REJECTED, "", evid, "; ".join(problems))
    return ClaimResult("conformance", SUPPORTED, text, evid)


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
        e = ev.lookup("unsafe", key, c, results_dir=d, fmt="{:.0f}")
        evid.append(e)
        if e.value != 0:
            problems.append(f"{c} = {e.display}")
    forbid = ev.lookup("unsafe", key, "forbid_unsafe_code", results_dir=d)
    evid.append(forbid)
    if forbid.value != "true":
        problems.append("forbid_unsafe_code is not set")
    deps_key = {"subject": "cf"}
    direct = ev.lookup("deps", deps_key, "direct_count", results_dir=d, fmt="{:.0f}")
    trans = ev.lookup("deps", deps_key, "transitive_count", results_dir=d, fmt="{:.0f}")
    evid += [direct, trans]
    if direct.value != 0 or trans.value != 0:
        problems.append(
            f"{direct.display} direct and {trans.display} transitive runtime dependencies"
        )
    if problems:
        return ClaimResult("safety", REJECTED, "", evid, "; ".join(problems))
    text = (
        f"cleanflate has {evid[0].display} unsafe blocks, functions, impls, traits and target-feature "
        f"attributes, forbids unsafe code, and has {direct.display} direct and {trans.display} transitive "
        "runtime dependencies."
    )
    return ClaimResult("safety", SUPPORTED, text, evid)


def _grid(cfg: dict) -> list[tuple[str, str, int]]:
    p = cfg["paper"]
    return [
        (m, f, lv) for m in p["machines"] for f in p["perf_framings"] for lv in p["perf_levels"]
    ]


def _ratio(
    d, cfg, subject: str, machine: str, framing: str, level: int
) -> tuple[Evidence, Evidence]:
    p = cfg["paper"]
    key = {"machine": machine, "variant": p["perf_variant"], "subject": subject, "corpus": p["perf_corpus"],
           "level": level, "framing": framing, "mode": p["perf_mode"]}  # fmt: skip
    ratio = ev.lookup("perf_aggregates", key, "ratio_vs_zlib", results_dir=d, fmt=X)
    complete = ev.lookup("perf_aggregates", key, "complete", results_dir=d)
    return ratio, complete


def _perf_ratios(d, cfg, subject: str) -> list[tuple[tuple, Evidence]]:
    """Ratios for the whole grid, or MissingData; also requires agreement pass and complete data."""
    p = cfg["paper"]
    out = []
    for m in p["machines"]:
        v = ev.lookup(
            "perf_agreement_summary",
            {"machine": m, "variant": p["perf_variant"]},
            "verdict",
            results_dir=d,
        )
        if v.value != "pass":
            raise MissingData(
                f"run-to-run agreement verdict for {m} is {v.display}, not pass: rerun `make perf`"
            )
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
    except MissingData as e:
        return _pending("perf_range", e)
    vals = [e for _, e in cells]
    lo, hi = min(vals, key=lambda e: e.value), max(vals, key=lambda e: e.value)
    p = cfg["paper"]
    text = (
        f"On the {p['perf_corpus'].title()} corpus, cleanflate's {p['perf_mode']} decompression throughput at levels "
        f"{' and '.join(map(str, p['perf_levels']))} in {' and '.join(p['perf_framings'])} framing is "
        f"{lo.display} to {hi.display} that of stock zlib (zlib = 1.00x) on {' and '.join(p['machines'])}."
    )
    return ClaimResult("perf_range", SUPPORTED, text, vals)


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
        "cleanflate's throughput relative to zlib across rounds 1, 2 and 3 was "
        + "; ".join(parts)
        + "."
    )
    return ClaimResult("trajectory", SUPPORTED, text, evid)


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
    evid = []
    try:
        for pair in ("zrs-mox", "cf-zrs", "cf-mox"):
            evid.append(
                ev.lookup(
                    "similarity_summary",
                    {"metric": "ident_jaccard", "pair": pair},
                    "score",
                    results_dir=d,
                    fmt="{:.3f}",
                )
            )
    except MissingData:
        evid = []
    if "T1 claim allowed" in text and "NOT allowed" not in text:
        claim = "cleanflate's code similarity to zlib-rs and miniz_oxide sits at or near the independent-implementation baseline."
        return ClaimResult("similarity", SUPPORTED, claim, evid)
    why = next(
        (ln for ln in text.splitlines() if "T1 claim" in ln),
        "the generated statement does not allow the claim",
    )
    return ClaimResult("similarity", REJECTED, "", evid, why.replace("**", "").strip())


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
    cost = None
    try:
        cost = ev.lookup(
            "effort_totals", {"round": "total"}, "cost_usd", results_dir=d, fmt="${:,.0f}"
        )
    except MissingData:
        pass
    text = f"Building cleanflate's three rounds took {wall.display} hours of attributed wall-clock time"
    if cost is not None:
        evid.append(cost)
        text += f" and an estimated {cost.display} of model cost."
    else:
        text += "; cost not priced (see EFFORT_GAPS.md)."
    return ClaimResult("effort", SUPPORTED, text, evid)


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
                       f"cleanflate reaches at least {threshold:.2f}x of zlib's throughput in every measured cell.",
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
            f"cleanflate is not faster in {len(slower)} cells, e.g. {slower[0]}",
        )
    return ClaimResult(
        cid, SUPPORTED, f"cleanflate is faster than {other} in every measured cell.", evid
    )


def _gzip_gap(d, cfg) -> ClaimResult:
    try:
        v = ev.lookup("framing_hypothesis", {"machine": "ALL"}, "verdict", results_dir=d)
    except MissingData as e:
        return _pending("gzip_gap_is_hw_crc", e)
    if v.value == "confirmed":
        return ClaimResult("gzip_gap_is_hw_crc", SUPPORTED,
                           "cleanflate's gzip framing penalty is consistent with stock zlib's penalty with hardware CRC disabled.", [v])  # fmt: skip
    return ClaimResult(
        "gzip_gap_is_hw_crc", REJECTED, "", [v], f"the framing hypothesis verdict is {v.display}"
    )


def evaluate(results_dir: Path | None = None, cfg: dict | None = None) -> list[ClaimResult]:
    d = Path(results_dir) if results_dir else paths.RESULTS
    cfg = cfg or config.load_config("full")
    fns = {
        "conformance": _conformance,
        "safety": _safety,
        "perf_range": _perf_range,
        "trajectory": _trajectory,
        "similarity": _similarity,
        "effort": _effort,
        "parity_with_zlib": _parity,
        "faster_than_zrs": lambda d, c: _faster_than("faster_than_zrs", "zrs", d, c),
        "faster_than_mox": lambda d, c: _faster_than("faster_than_mox", "mox", d, c),
        "gzip_gap_is_hw_crc": _gzip_gap,
    }
    return [fns[cid](d, cfg) for cid in ORDER]
