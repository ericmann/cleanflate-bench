"""Statistics used by every perf report (SPEC 3.2)."""

import random
from dataclasses import dataclass

import numpy as np

MIB = 1 << 20
NS_PER_S = 1e9


def median(xs) -> float:
    return float(np.median(np.asarray(xs, dtype=float)))


def best(xs) -> float:
    """Best time: the minimum ns, i.e. the best throughput."""
    return float(min(xs))


def bootstrap_ci(xs, level: float, resamples: int, rng: random.Random) -> tuple[float, float]:
    """Percentile bootstrap of the median. Deterministic for a given `rng` state."""
    arr = np.asarray(xs, dtype=float)
    gen = np.random.default_rng(rng.getrandbits(64))
    idx = gen.integers(0, len(arr), size=(resamples, len(arr)))
    meds = np.median(arr[idx], axis=1)
    tail = (1.0 - level) / 2.0
    lo, hi = np.quantile(meds, [tail, 1.0 - tail])
    return float(lo), float(hi)


def mib_per_s(output_bytes: int, ns: float) -> float:
    return output_bytes / (ns / NS_PER_S) / MIB


def ns_per_byte(ns: float, output_bytes: int) -> float:
    return ns / output_bytes


@dataclass(frozen=True)
class CellStats:
    median_ns: float
    best_ns: float
    ci_lo_ns: float
    ci_hi_ns: float
    median_mib_s: float
    best_mib_s: float
    ci_lo_mib_s: float
    ci_hi_mib_s: float
    ns_per_byte: float
    n: int


def cell_stats(samples_ns, output_bytes: int, cfg: dict, rng: random.Random) -> CellStats:
    perf = cfg["perf"]
    med = median(samples_ns)
    bst = best(samples_ns)
    lo, hi = bootstrap_ci(samples_ns, perf["ci_level"], perf["bootstrap_resamples"], rng)
    return CellStats(
        median_ns=med,
        best_ns=bst,
        ci_lo_ns=lo,
        ci_hi_ns=hi,
        median_mib_s=mib_per_s(output_bytes, med),
        best_mib_s=mib_per_s(output_bytes, bst),
        # a slower time is a lower throughput, so the bounds swap
        ci_lo_mib_s=mib_per_s(output_bytes, hi),
        ci_hi_mib_s=mib_per_s(output_bytes, lo),
        ns_per_byte=ns_per_byte(med, output_bytes),
        n=len(samples_ns),
    )


def like_for_like_key(cell: dict) -> tuple:
    """Cells are comparable only when every field here matches (CLAUDE.md: like for like)."""
    return (
        cell["machine"],
        cell["session"],
        cell["workload"],
        cell["level"],
        cell["framing"],
        cell["mode"],
    )


def ratio_vs_baseline(subject_mib_s: float | None, baseline_mib_s: float | None) -> float | None:
    """Throughput ratio; None when either side is missing (never zero, never a guess)."""
    if subject_mib_s is None or not baseline_mib_s:
        return None
    return subject_mib_s / baseline_mib_s


def ratios_vs_baseline(cells: list[dict], baseline: str = "zlib") -> list[float | None]:
    """Ratio of each cell's `median_mib_s` to the baseline subject's cell with the same key.

    A baseline in another mode, level, framing, session or machine is never substituted.
    """
    base = {like_for_like_key(c): c["median_mib_s"] for c in cells if c["subject"] == baseline}
    return [ratio_vs_baseline(c["median_mib_s"], base.get(like_for_like_key(c))) for c in cells]
