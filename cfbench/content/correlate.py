"""H1 and H2: correlate cf's ratio against zlib with content features (SPEC 3.4 and 6).

The perf ratio is cf's generic oneshot throughput over zlib's (`perf_cells.ratio_vs_zlib`), joined
with `content_features` on workload, level and framing. Spearman rho comes from scipy; its p-value
is a seeded two-sided permutation test.
"""

import math
import random
import sys
from pathlib import Path

import numpy as np
from scipy import stats as sps

from cfbench import charts, config, parity, paths, provenance

COLUMNS = ["hypothesis", "machine", "feature", "n", "rho", "p", "expected_sign", "verdict"]
PENDING = "no perf data; run make perf then make content"
CONFIRMED, REFUTED, INCONCLUSIVE = "confirmed", "refuted", "inconclusive"
STRENGTH = {REFUTED: 0, INCONCLUSIVE: 1, CONFIRMED: 2}
COMBINED = "(combined)"
SCRIPT = "cfbench.content.correlate"
# hypothesis -> (subset description, features); both expect a negative sign
HYPOTHESES = {
    "H1": ("canterbury, raw framing, all levels", ["short_dist_fraction", "overlap_fraction"]),
    "H2": ("level 1, raw framing, both corpora", ["literal_fraction"]),
}
OTHER_FEATURES = ["dist1_fraction", "dist2_7_fraction", "mean_match_len", "ratio"]


def _f(x) -> float | None:
    if x is None or x == "":
        return None
    v = float(x)
    return None if math.isnan(v) else v


def join(cells: list[dict], feats: list[dict]) -> list[dict]:
    """cf generic oneshot cells joined with content features; adds `short_dist_fraction`."""
    by = {(r["workload"], int(r["level"]), r["framing"]): r for r in feats}
    out = []
    for c in cells:
        if c["subject"] != "cf" or c["variant"] != "generic" or c["mode"] != "oneshot":
            continue
        ratio = _f(c.get("ratio_vs_zlib"))
        f = by.get((c["workload"], int(c["level"]), c["framing"]))
        if ratio is None or f is None:
            continue
        row = {"machine": c["machine"], "workload": c["workload"], "corpus": c["corpus"],
               "level": int(c["level"]), "framing": c["framing"], "perf_ratio": ratio}  # fmt: skip
        for k, v in f.items():
            if k not in row:
                row[k] = _f(v) if k not in ("corpus", "framing_analysed") else v
        d1, d2 = row.get("dist1_fraction"), row.get("dist2_7_fraction")
        row["short_dist_fraction"] = None if d1 is None or d2 is None else d1 + d2
        out.append(row)
    return out


def subset(rows: list[dict], hypothesis: str) -> list[dict]:
    if hypothesis == "H1":
        return [r for r in rows if r["corpus"] == "canterbury" and r["framing"] == "raw"]
    return [r for r in rows if r["level"] == 1 and r["framing"] == "raw"]


def spearman(xs, ys, permutations: int, seed: int) -> tuple[float, float]:
    """Spearman rho (scipy) and a two-sided permutation p-value, deterministic for a seed."""
    rho = float(sps.spearmanr(xs, ys).statistic)
    if math.isnan(rho):
        return float("nan"), float("nan")
    rx = sps.rankdata(xs)
    ry = list(sps.rankdata(ys))
    rx = (rx - rx.mean()) / np.linalg.norm(rx - rx.mean())
    rng = random.Random(seed)
    hits = 0
    for _ in range(permutations):
        rng.shuffle(ry)
        y = np.asarray(ry)
        y = (y - y.mean()) / np.linalg.norm(y - y.mean())
        if abs(float(rx @ y)) >= abs(rho) - 1e-12:
            hits += 1
    return rho, (hits + 1) / (permutations + 1)


def verdict(rho: float, p: float, cfg: dict) -> str:
    """confirmed, refuted or inconclusive for an expected-negative correlation."""
    c = cfg["content"]
    if math.isnan(rho):
        return INCONCLUSIVE
    if rho < 0 and abs(rho) >= c["min_abs_rho"] and p < c["alpha"]:
        return CONFIRMED
    if (rho > 0 and p < c["alpha"]) or abs(rho) < c["null_abs_rho"]:
        return REFUTED
    return INCONCLUSIVE


def weaker(verdicts: list[str]) -> str:
    return min(verdicts, key=STRENGTH.__getitem__) if verdicts else INCONCLUSIVE


def correlate(
    xs_rows: list[dict], feature: str, cfg: dict
) -> tuple[int, float | None, float | None]:
    pts = [(r[feature], r["perf_ratio"]) for r in xs_rows if r.get(feature) is not None]
    if len(pts) < 3:
        return len(pts), None, None
    rho, p = spearman(
        [a for a, _ in pts], [b for _, b in pts], cfg["content"]["permutations"], cfg["run"]["seed"]
    )
    return len(pts), (None if math.isnan(rho) else rho), (None if math.isnan(p) else p)


def hypothesis_rows(joined: list[dict], cfg: dict) -> list[dict]:
    """Per-feature and combined rows per machine, plus an overall (machine ALL) row; never omitted."""
    machines = sorted({r["machine"] for r in joined})
    out = []
    for h, (_desc, feats) in HYPOTHESES.items():
        combined = {}
        for m in machines:
            sub = subset([r for r in joined if r["machine"] == m], h)
            vs = []
            for feat in feats:
                n, rho, p = correlate(sub, feat, cfg)
                v = verdict(rho, p, cfg) if rho is not None else INCONCLUSIVE
                vs.append(v)
                out.append({"hypothesis": h, "machine": m, "feature": feat, "n": n, "rho": rho,
                            "p": p, "expected_sign": "negative", "verdict": v})  # fmt: skip
            combined[m] = weaker(vs)
            out.append({"hypothesis": h, "machine": m, "feature": COMBINED, "n": None, "rho": None,
                        "p": None, "expected_sign": "negative", "verdict": combined[m]})  # fmt: skip
        kinds = set(combined.values())
        overall = kinds.pop() if len(kinds) == 1 else INCONCLUSIVE
        out.append({"hypothesis": h, "machine": "ALL", "feature": COMBINED, "n": None, "rho": None,
                    "p": None, "expected_sign": "negative", "verdict": overall})  # fmt: skip
    return out


def strongest_other(joined: list[dict], cfg: dict) -> dict[str, tuple[str, int, float]]:
    """Per machine, the other feature (raw framing, all rows) with the largest |rho|."""
    best = {}
    for m in sorted({r["machine"] for r in joined}):
        sub = [r for r in joined if r["machine"] == m and r["framing"] == "raw"]
        for feat in OTHER_FEATURES:
            n, rho, _p = correlate(sub, feat, cfg)
            if rho is not None and (m not in best or abs(rho) > abs(best[m][2])):
                best[m] = (feat, n, rho)
    return best


def scatter(joined: list[dict], machine: str, feature: str, hypothesis: str, out_dir=None):
    sub = [r for r in subset([r for r in joined if r["machine"] == machine], hypothesis)
           if r.get(feature) is not None]  # fmt: skip
    if not sub:
        return None
    fig = charts.new_figure("default")
    ax = fig.subplots()
    ax.scatter([r[feature] for r in sub], [r["perf_ratio"] for r in sub], s=14)
    ax.set_xlabel(feature)
    ax.set_ylabel("cf throughput / zlib throughput")
    ax.set_title(f"{hypothesis} on {machine}: {HYPOTHESES[hypothesis][0]}")
    return charts.save_figure(fig, f"content_scatter_{feature}_{machine}",
                              parity_note=parity.with_context(machine, "generic"), out_dir=out_dir)  # fmt: skip


def findings(rows: list[dict], other: dict, pending: bool) -> str:
    lines = ["# Content findings", "", "Generated by `cfbench.content.correlate`; do not edit.", ""]
    if pending:
        lines += [f"Pending: {PENDING}. Both verdicts are inconclusive until perf data exists.", ""]
    for h, (desc, feats) in HYPOTHESES.items():
        overall = next(r for r in rows if r["hypothesis"] == h and r["machine"] == "ALL")
        lines += [
            f"## {h}: {overall['verdict']}",
            "",
            f"Subset: {desc}. Expected sign: negative.",
            "",
        ]
        for r in rows:
            if r["hypothesis"] == h and r["machine"] != "ALL" and r["feature"] != COMBINED:
                lines.append(f"- {r['machine']} `{r['feature']}`: n={r['n']}, rho={_fmt(r['rho'])}, "
                             f"p={_fmt(r['p'])}, {r['verdict']}")  # fmt: skip
        lines.append("")
    lines += ["## Strongest other correlation", ""]
    if other:
        for m, (feat, n, rho) in other.items():
            lines.append(f"- {m}: `{feat}` (n={n}, rho={rho:.3f}), raw framing, all workloads")
    else:
        lines.append("- none (no perf data)")
    lines += [
        "",
        "## Caveats",
        "",
        "- Spearman rank correlation shows association, not cause.",
        "- Workloads are few and not independent (levels of one file share content).",
        "- Features come from the raw-framed stream and are copied to the zlib and gzip rows.",
        "- Throughput ratios inherit the parity note: cf is decompress-only and no comparison is apples-to-apples.",
        "",
    ]
    return "\n".join(lines)


def _fmt(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def _raw_paths(sidecar: dict) -> list[Path]:
    return [paths.ROOT / e["path"] for e in sidecar["raw_files"]]


def run(cfg: dict | None = None, out_dir=None) -> list[dict]:
    cfg = cfg or config.load_config("full")
    try:
        cells, cs = provenance.read_table("perf_cells")
        feats, fs = provenance.read_table("content_features")
    except FileNotFoundError:
        cells, feats, cs, fs = [], [], {"raw_files": []}, {"raw_files": []}
    joined = join(cells, feats)
    pending = not joined
    rows = hypothesis_rows(joined, cfg)
    if pending:
        rows = [{"hypothesis": h, "machine": "ALL", "feature": COMBINED, "n": 0, "rho": None,
                 "p": None, "expected_sign": "negative", "verdict": INCONCLUSIVE}
                for h in HYPOTHESES]  # fmt: skip
    raw = _raw_paths(cs) + _raw_paths(fs)
    provenance.write_table("content_hypotheses", COLUMNS, rows, script=SCRIPT, raw_files=raw,
                           pending=PENDING if pending else None)  # fmt: skip
    for m in sorted({r["machine"] for r in joined}):
        for h, (_d, fts) in HYPOTHESES.items():
            for feat in fts:
                scatter(joined, m, feat, h, out_dir)
    text = findings(rows, strongest_other(joined, cfg), pending)
    (paths.RESULTS / "CONTENT_FINDINGS.md").write_text(text, encoding="utf-8")
    return rows


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
