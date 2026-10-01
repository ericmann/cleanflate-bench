import copy

import pytest

from cfbench import config, paths, provenance
from cfbench.content import correlate

CFG = copy.deepcopy(config.load_config("full"))
CFG["content"]["permutations"] = 500


def make(machine, n, slope, corpus="canterbury", noise=None):
    """n canterbury raw rows, level 1 and 6 alternating; perf ratio follows x * slope."""
    out = []
    for i in range(n):
        x = (i + 1) / (n + 1)
        y = 0.8 + slope * x if noise is None else noise[i % len(noise)]
        out.append({"machine": machine, "workload": f"{corpus}/f{i}", "corpus": corpus,
                    "level": 1, "framing": "raw", "perf_ratio": y, "literal_fraction": x,
                    "dist1_fraction": x, "dist2_7_fraction": x / 2, "overlap_fraction": x,
                    "mean_match_len": x, "ratio": x})  # fmt: skip
    for r in out:
        r["short_dist_fraction"] = r["dist1_fraction"] + r["dist2_7_fraction"]
    return out


def overall(rows, h):
    return next(r for r in rows if r["hypothesis"] == h and r["machine"] == "ALL")["verdict"]


def test_confirmed_on_strong_negative_correlation():
    rows = correlate.hypothesis_rows(make("M-B", 20, -0.5), CFG)
    assert overall(rows, "H1") == "confirmed" and overall(rows, "H2") == "confirmed"
    r = next(r for r in rows if r["feature"] == "overlap_fraction")
    assert r["rho"] == pytest.approx(-1.0) and r["p"] < 0.05 and r["expected_sign"] == "negative"


def test_refuted_on_null_correlation():
    noise = [0.5, 0.9, 0.2, 0.7, 0.4, 0.8, 0.3, 0.6, 0.1, 1.0]  # uncorrelated with the ramp
    rows = correlate.hypothesis_rows(make("M-B", 10, 0, noise=noise), CFG)
    h2 = next(r for r in rows if r["feature"] == "literal_fraction")
    assert abs(h2["rho"]) < 0.5
    pos = correlate.hypothesis_rows(make("M-B", 20, 0.5), CFG)
    assert overall(pos, "H2") == "refuted"  # significant, opposite sign
    assert correlate.verdict(0.1, 0.9, CFG) == "refuted"
    assert correlate.verdict(-0.35, 0.3, CFG) == "inconclusive"


def test_machine_disagreement_is_inconclusive():
    joined = make("M-A", 20, -0.5) + make("M-B", 20, 0.5)
    rows = correlate.hypothesis_rows(joined, CFG)
    by = {
        r["machine"]: r["verdict"]
        for r in rows
        if r["hypothesis"] == "H2" and r["feature"] == "(combined)"
    }
    assert by == {"M-A": "confirmed", "M-B": "refuted", "ALL": "inconclusive"}


def test_permutation_p_value_is_deterministic():
    xs = [1, 2, 3, 4, 5, 6, 7, 8]
    ys = [2, 1, 4, 3, 6, 5, 8, 7]
    a = correlate.spearman(xs, ys, 300, 7)
    assert a == correlate.spearman(xs, ys, 300, 7)
    assert a[0] == pytest.approx(0.9048, abs=1e-3) and 0 < a[1] < 0.05


def test_pending_without_perf_data_still_lists_both_hypotheses(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", tmp_path)
    rows = correlate.run(CFG, out_dir=tmp_path / "f")
    assert [(r["hypothesis"], r["verdict"]) for r in rows] == [
        ("H1", "inconclusive"),
        ("H2", "inconclusive"),
    ]
    side = provenance.read_table("content_hypotheses")[1]
    assert side["pending"] == correlate.PENDING
    text = (tmp_path / "CONTENT_FINDINGS.md").read_text()
    assert "## H1: inconclusive" in text and "## H2: inconclusive" in text and "Pending" in text
    assert not (tmp_path / "f").exists()


def test_join_filters_cf_generic_oneshot():
    cell = {"machine": "M-B", "variant": "generic", "subject": "cf", "corpus": "canterbury",
            "workload": "canterbury/a", "level": "1", "framing": "raw", "mode": "oneshot",
            "ratio_vs_zlib": "0.7"}  # fmt: skip
    feat = {"workload": "canterbury/a", "corpus": "canterbury", "level": "1", "framing": "raw",
            "dist1_fraction": "0.1", "dist2_7_fraction": "0.2", "literal_fraction": "0.3"}  # fmt: skip
    got = correlate.join([cell, {**cell, "subject": "zrs"}, {**cell, "mode": "stream"}], [feat])
    assert len(got) == 1 and got[0]["short_dist_fraction"] == pytest.approx(0.3)


def test_verdict_threshold_edges():
    c = CFG["content"]
    p_hit, p_miss = c["alpha"] / 2, c["alpha"] * 2
    between = -(c["null_abs_rho"] + c["min_abs_rho"]) / 2
    assert correlate.verdict(between, p_hit, CFG) == "inconclusive"  # needs abs(rho) >= min_abs_rho
    assert correlate.verdict(-(c["null_abs_rho"] / 2), p_hit, CFG) == "refuted"
    assert correlate.verdict(0.6, p_hit, CFG) == "refuted"  # significant positive correlation
    assert correlate.verdict(-0.6, p_miss, CFG) == "inconclusive"  # strong but not significant
    assert correlate.verdict(-0.6, p_hit, CFG) == "confirmed"
