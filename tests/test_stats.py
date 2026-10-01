import random

import pytest

from cfbench import config, stats


def test_median_even_and_odd():
    assert stats.median([3, 1, 2]) == 2
    assert stats.median([4, 1, 3, 2]) == 2.5
    assert stats.best([5.0, 2.0, 9.0]) == 2.0


def test_bootstrap_ci_is_deterministic_for_seed():
    xs = [100 + (i * 7) % 13 for i in range(30)]
    a = stats.bootstrap_ci(xs, 0.95, 500, random.Random(1))
    b = stats.bootstrap_ci(xs, 0.95, 500, random.Random(1))
    c = stats.bootstrap_ci(xs, 0.95, 500, random.Random(2))
    assert a == b
    assert a != c


def test_ci_brackets_median():
    xs = [100 + (i * 7) % 13 for i in range(30)]
    lo, hi = stats.bootstrap_ci(xs, 0.95, 1000, random.Random(3))
    assert lo <= stats.median(xs) <= hi
    narrow = stats.bootstrap_ci(xs, 0.5, 1000, random.Random(3))
    assert hi - lo >= narrow[1] - narrow[0]
    constant = stats.bootstrap_ci([5.0] * 10, 0.95, 100, random.Random(0))
    assert constant == (5.0, 5.0)


def test_mib_per_s_and_ns_per_byte():
    # 1 MiB in 1 ms is 1000 MiB/s
    assert stats.mib_per_s(1 << 20, 1e6) == pytest.approx(1000.0)
    assert stats.ns_per_byte(2000.0, 1000) == 2.0


def test_cell_stats_swaps_ci_for_throughput():
    cfg = config.load_config("full")
    samples = [1e6 + i * 1e4 for i in range(30)]
    s = stats.cell_stats(samples, 1 << 20, cfg, random.Random(cfg["run"]["seed"]))
    assert s.n == 30
    assert s.ci_lo_ns <= s.median_ns <= s.ci_hi_ns
    assert s.ci_lo_mib_s <= s.median_mib_s <= s.ci_hi_mib_s
    assert s.best_mib_s >= s.median_mib_s
    assert s.ns_per_byte == pytest.approx(s.median_ns / (1 << 20))


def cell(subject, mode="oneshot", mib=100.0, **kw):
    base = {
        "machine": "M-B",
        "session": "s1",
        "workload": "silesia/xml",
        "level": 6,
        "framing": "raw",
        "mode": mode,
        "subject": subject,
        "median_mib_s": mib,
    }
    return {**base, **kw}


def test_ratio_requires_same_mode_baseline():
    cells = [
        cell("zlib", "oneshot", 200.0),
        cell("cf", "oneshot", 100.0),
        cell("cf", "stream_small", 50.0),  # no zlib stream_small cell exists
        cell("cf", "oneshot", 90.0, level=9),  # different level
        cell("cf", "oneshot", 80.0, session="s2"),  # different session
    ]
    r = stats.ratios_vs_baseline(cells)
    assert r == [1.0, 0.5, None, None, None]


def test_ratio_vs_baseline_handles_missing_and_zero():
    assert stats.ratio_vs_baseline(1.0, None) is None
    assert stats.ratio_vs_baseline(None, 1.0) is None
    assert stats.ratio_vs_baseline(1.0, 0.0) is None
    assert stats.ratio_vs_baseline(3.0, 2.0) == 1.5


def test_like_for_like_key_fields():
    assert stats.like_for_like_key(cell("cf")) == ("M-B", "s1", "silesia/xml", 6, "raw", "oneshot")
