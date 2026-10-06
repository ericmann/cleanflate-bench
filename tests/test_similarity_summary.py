import pytest

from cfbench import config
from cfbench.similarity import summary as sm

CFG = config.load_config("full")
NEAR = CFG["similarity"]["near_fraction"]


def test_position_and_classification_bands():
    assert NEAR == 0.25
    assert sm.position(0.5, 0.2, 0.6) == pytest.approx(0.75)
    cases = {
        -0.1: "below negative",
        0.0: "at or near negative",
        0.25: "at or near negative",
        0.26: "between",
        0.74: "between",
        0.75: "at or near positive",
        1.0: "at or near positive",
        1.2: "above positive",
    }
    for pos, want in cases.items():
        assert sm.classify(pos, NEAR) == want, pos


def scores(neg, pos, **tests):
    d = {"zrs-mox": {"role": "negative", "score": neg}}
    if pos is not None:
        d["zrs-zng"] = {"role": "positive", "score": pos}
    for k, v in tests.items():
        d[k.replace("_", "-")] = {"role": "test", "score": v}
    return d


def test_summary_rows_carry_controls_and_position():
    rows = sm.summarize({"m": scores(0.2, 0.6, cf_zrs=0.3, cf_mox=0.7)}, CFG)
    by = {r["pair"]: r for r in rows}
    assert (
        by["cf-zrs"]["position"] == pytest.approx(0.25)
        and by["cf-zrs"]["classification"] == "at or near negative"
    )
    assert by["cf-mox"]["classification"] == "above positive"
    assert (
        by["zrs-mox"]["position"] == 0.0 and by["zrs-mox"]["classification"] == "negative control"
    )
    assert by["zrs-zng"]["position"] == 1.0
    assert by["cf-zrs"]["neg_score"] == 0.2 and by["cf-zrs"]["pos_score"] == 0.6


def test_unseparated_controls_are_reported():
    rows = sm.summarize(
        {"m": scores(0.2, 0.05, cf_zrs=0.21)}, CFG
    )  # positive control below negative
    t = next(r for r in rows if r["pair"] == "cf-zrs")
    assert t["classification"] == sm.UNSEPARATED and t["position"] is None
    equal = sm.summarize({"m": scores(0.2, 0.2, cf_zrs=0.21)}, CFG)
    assert next(r for r in equal if r["pair"] == "cf-zrs")["classification"] == sm.UNSEPARATED
    missing = sm.summarize({"m": scores(0.2, None, cf_zrs=0.21)}, CFG)
    assert next(r for r in missing if r["pair"] == "cf-zrs")["classification"] == sm.NO_POS


def test_claim_allowed_only_when_all_metrics_near_negative():
    good = sm.summarize(
        {"a": scores(0.1, 0.5, cf_zrs=0.12, cf_mox=0.05), "b": scores(0.2, 0.9, cf_zrs=0.25)}, CFG
    )
    assert "T1 claim allowed" in sm.statement(good) and "NOT allowed" not in sm.statement(good)
    bad = sm.summarize(
        {"a": scores(0.1, 0.5, cf_zrs=0.12), "b": scores(0.2, 0.9, cf_zrs=0.6, cf_mox=0.1)}, CFG
    )
    text = sm.statement(bad)
    assert "T1 claim NOT allowed" in text and "`b`" in text.split("NOT allowed")[1].splitlines()[0]
    assert sm.failing_metrics(bad)[0] == ["b"]
    # a metric that does not separate the controls is excluded, not counted as passing or failing
    mixed = sm.summarize(
        {"a": scores(0.1, 0.5, cf_zrs=0.12), "u": scores(0.5, 0.1, cf_zrs=0.5)}, CFG
    )
    text = sm.statement(mixed)
    assert "T1 claim allowed" in text and "do not separate the controls" in text and "`u`" in text
    # if nothing separates the controls there is nothing to support the claim
    none = sm.summarize({"u": scores(0.5, 0.1, cf_zrs=0.5)}, CFG)
    assert "T1 claim NOT allowed" in sm.statement(none) and "no metric separates" in sm.statement(
        none
    )


def test_statement_is_deterministic():
    rows = sm.summarize(
        {"a": scores(0.1, 0.5, cf_zrs=0.12), "b": scores(0.2, 0.9, cf_zrs=0.6)}, CFG
    )
    s1, s2 = sm.statement(rows), sm.statement(list(rows))
    assert s1 == s2 and s1.startswith(sm.HEADER)
    assert sm.statement([]).count("Pending") == 1


def test_collect_scores_reads_every_metric_family():
    pair = {"left": "cf", "right": "zrs", "role": "test", "cross_language": False}
    neg = {"left": "zrs", "right": "mox", "role": "negative", "cross_language": False}
    payloads = {
        "ngram": {"pairs": [{**p, "results": [{"n": n, "jaccard": 0.1 * n, "containment": 0.2}
                                              for n in range(5, 11)]} for p in (pair, neg)]},
        "identifiers": {"pairs": [{**pair, "ident_jaccard": 0.3, "ident_match_rate_left": 0.4}]},
        "comments": {"pairs": [{**pair, "jaccard": 0.01}]},
        "jplag": {"pairs": [{**pair, "status": "ok", "avg": 0.18},
                            {**neg, "status": "not applicable (cross-language)"}]},
    }  # fmt: skip
    got = sm.collect_scores(payloads, CFG)
    assert set(got) == set(sm.metric_names(CFG))
    assert got["ngram_jaccard@5"]["cf-zrs"]["score"] == pytest.approx(0.5)
    assert got["ngram_containment@5"]["cf-zrs"]["score"] == 0.2 and "ngram_containment@6" not in got
    assert got["jplag_avg"] == {"cf-zrs": {"role": "test", "score": 0.18}}
    assert got["comment_jaccard"]["cf-zrs"]["score"] == 0.01


def test_figure_draws_only_separable_metrics():
    rows = sm.summarize(
        {"a": scores(0.1, 0.5, cf_zrs=0.12), "u": scores(0.5, 0.1, cf_zrs=0.5)}, CFG
    )
    fig = sm.draw(rows)
    ax = fig.axes[0]
    assert [t.get_text() for t in ax.get_yticklabels()] == ["a"]


def test_posthoc_metrics_never_decide_the_claim():
    # pre-registered identifier metric fails; its filtered stand-in passes
    rows = sm.summarize(
        {
            "a": scores(0.1, 0.5, cf_zrs=0.12),
            "ident_jaccard": scores(0.04, 0.14, cf_mox=0.075),
            "ident_jaccard_filtered": scores(0.04, 0.14, cf_mox=0.05),
        },
        CFG,
    )
    text = sm.statement(rows)
    claim = next(ln for ln in text.splitlines() if "T1 claim" in ln)
    sens = next(ln for ln in text.splitlines() if ln.startswith("**Post-hoc sensitivity"))
    assert "T1 claim NOT allowed" in claim and "`ident_jaccard`" in claim
    assert "ident_jaccard_filtered" not in claim
    assert "would be allowed" in sens and "T1 claim" not in sens
    # and the reverse: a failing filtered metric cannot revoke an allowed claim
    rows = sm.summarize(
        {
            "ident_jaccard": scores(0.04, 0.14, cf_mox=0.05),
            "ident_jaccard_filtered": scores(0.04, 0.14, cf_mox=0.1),
        },
        CFG,
    )
    text = sm.statement(rows)
    assert "**T1 claim allowed**" in text and "would still not be allowed" in text
    assert "NOT allowed" not in text


def test_no_sensitivity_line_without_filtered_metrics():
    rows = sm.summarize({"a": scores(0.1, 0.5, cf_zrs=0.12)}, CFG)
    assert "Post-hoc sensitivity" not in sm.statement(rows)


def test_reference_pairs_are_reported_after_the_claim_and_never_tested():
    d = scores(0.2, 0.6, cf_zrs=0.25, cf_zlib=0.1)
    d["zrs-zlib"] = {"role": "reference", "score": 0.55}  # would fail the claim if it were a test
    rows = sm.summarize({"ident_jaccard": d}, CFG)
    ref = next(r for r in rows if r["pair"] == "zrs-zlib")
    assert ref["classification"] == "at or near positive"
    assert sm.failing_metrics(rows) == ([], [])
    text = sm.statement(rows, ["cf-zlib", "zrs-zlib"])
    claim_at = text.index("T1 claim allowed")
    ref_at = text.index(sm.REFERENCE_HEADING)
    assert claim_at < ref_at and "T1 claim" not in text[ref_at:]
    assert "- `ident_jaccard`: cf-zlib 0.1 (below negative, position -0.25); zrs-zlib 0.55" in text
    assert sm.REFERENCE_HEADING not in sm.statement(rows)  # no labels, no reference block
