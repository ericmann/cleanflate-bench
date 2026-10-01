import shutil
from pathlib import Path

import pytest

from cfbench import config, provenance
from cfbench.kits import claims, evidence

FIX = Path(__file__).parent / "fixtures" / "results"
CFG = config.load_config("full")


@pytest.fixture
def results(tmp_path):
    d = tmp_path / "results"
    shutil.copytree(FIX, d)
    return d


def by_id(results_dir):
    return {c.id: c for c in claims.evaluate(results_dir, CFG)}


def rewrite(d, table, edit):
    """Rewrite one fixture table through the real writer, applying `edit(rows) -> rows`."""
    rows, side = provenance.read_table(table, d)
    new = edit([dict(r) for r in rows])
    # keep the sidecar's script and columns; write CSV directly to avoid touching raw files
    import csv

    with open(provenance.table_path(table, d), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(side["columns"])
        for r in new:
            w.writerow([r.get(c, "") for c in side["columns"]])


def test_conformance_supported_with_full_pass(results):
    c = by_id(results)["conformance"]
    assert c.status == claims.SUPPORTED
    assert "100 of 100 streams on M-B" in c.text and "no disagreement" in c.text
    # a failure or a listed disagreement rejects the claim
    rewrite(
        results,
        "conformance",
        lambda rows: [
            {**r, "failed": "1", "pass_rate": "0.99"} if r["subject"] == "cf" else r for r in rows
        ],
    )
    rejected = by_id(results)["conformance"]
    assert rejected.status == claims.REJECTED and "pass rate 0.9900" in rejected.reason
    rewrite(
        results,
        "conformance_disagreements",
        lambda rows: [
            {
                "machine": "M-B",
                "entry": "x",
                "framing": "raw",
                "subject": "cf",
                "outcome": "fail",
                "error": "e",
            }
        ],
    )
    assert "disagreements" in by_id(results)["conformance"].reason


def test_safety_supported_then_rejected_on_any_unsafe(results):
    c = by_id(results)["safety"]
    assert (
        c.status == claims.SUPPORTED
        and "0 unsafe blocks" in c.text
        and "0 direct and 0 transitive" in c.text
    )
    rewrite(
        results,
        "unsafe",
        lambda rows: [{**r, "unsafe_blocks": "1"} if r["subject"] == "cf" else r for r in rows],
    )
    r = by_id(results)["safety"]
    assert r.status == claims.REJECTED and "unsafe_blocks = 1" in r.reason
    rewrite(
        results,
        "deps",
        lambda rows: [
            {**r, "direct_count": "1", "transitive_count": "1"} if r["subject"] == "cf" else r
            for r in rows
        ],
    )
    assert "direct and 1 transitive" in by_id(results)["safety"].reason


def test_perf_range_pending_without_both_machines(results):
    c = by_id(results)["perf_range"]
    assert c.status == claims.SUPPORTED
    assert (
        "0.76x to 0.89x" in c.text
    )  # min and max over both machines, raw and zlib, levels 6 and 9
    assert len(c.evidence) == 2 * 2 * 2
    rewrite(results, "perf_aggregates", lambda rows: [r for r in rows if r["machine"] != "M-A"])
    rewrite(
        results, "perf_agreement_summary", lambda rows: [r for r in rows if r["machine"] != "M-A"]
    )
    p = by_id(results)["perf_range"]
    assert p.status == claims.PENDING and "M-A" in p.reason and "make perf" in p.reason
    # a machine whose runs disagree also leaves the claim pending
    shutil.rmtree(results)
    shutil.copytree(FIX, results)
    rewrite(
        results,
        "perf_agreement_summary",
        lambda rows: [{**r, "verdict": "flagged"} if r["machine"] == "M-B" else r for r in rows],
    )
    f = by_id(results)["perf_range"]
    assert f.status == claims.PENDING and "not pass" in f.reason


def test_trajectory_supported_and_non_monotonic_stated(results):
    t = by_id(results)["trajectory"]
    assert t.status == claims.SUPPORTED
    assert "M-A: 0.40x, 0.60x, 0.80x" in t.text and "M-B: 0.30x, 0.50x, 0.70x" in t.text
    rewrite(
        results,
        "trajectory",
        lambda rows: [
            {**r, "ratio_vs_zlib": "0.9"} if r["machine"] == "M-A" and r["round"] == "2" else r
            for r in rows
        ],
    )
    n = by_id(results)["trajectory"]
    assert n.status == claims.SUPPORTED and "(not monotonic)" in n.text  # stated, not hidden
    rewrite(
        results,
        "trajectory",
        lambda rows: [
            {**r, "ratio_vs_zlib": "0.2"} if r["machine"] == "M-B" and r["round"] == "3" else r
            for r in rows
        ],
    )
    assert by_id(results)["trajectory"].status == claims.REJECTED


def test_similarity_rejected_when_statement_disallows(results):
    assert by_id(results)["similarity"].status == claims.SUPPORTED
    (results / "similarity_statement.md").write_text(
        "# s\n\n**T1 claim NOT allowed**: a cf pair is not at or near the negative control for `ident_jaccard` (cf-mox between).\n"
    )
    r = by_id(results)["similarity"]
    assert r.status == claims.REJECTED and "NOT allowed" in r.reason and r.text == ""
    assert len(r.evidence) == 3  # the controls and pairs stay visible next to the rejection
    (results / "similarity_statement.md").unlink()
    assert by_id(results)["similarity"].status == claims.PENDING


def test_effort_cost_only_when_priced(results):
    e = by_id(results)["effort"]
    assert e.status == claims.SUPPORTED and "30.0 hours" in e.text
    assert "cost not priced (see EFFORT_GAPS.md)" in e.text
    rewrite(
        results,
        "effort_totals",
        lambda rows: [{**r, "cost_usd": "1234.5"} if r["round"] == "total" else r for r in rows],
    )
    priced = by_id(results)["effort"]
    assert "$1,234" in priced.text and "not priced" not in priced.text and len(priced.evidence) == 2


def test_overreach_claims_rejected_by_default(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    got = by_id(empty)
    for cid in ("parity_with_zlib", "faster_than_zrs", "faster_than_mox"):
        assert got[cid].status == claims.REJECTED and "no data supports it" in got[cid].reason
    assert got["gzip_gap_is_hw_crc"].status == claims.PENDING  # until the framing data exists
    for cid in ("conformance", "safety", "perf_range", "trajectory", "similarity", "effort"):
        assert got[cid].status == claims.PENDING, cid
    assert [c.id for c in claims.evaluate(empty, CFG)] == claims.ORDER


def test_overreach_claims_follow_the_data(results):
    got = by_id(results)
    assert (
        got["parity_with_zlib"].status == claims.REJECTED
        and "below 0.95x" in got["parity_with_zlib"].reason
    )
    assert (
        got["faster_than_zrs"].status == claims.REJECTED
        and "not faster" in got["faster_than_zrs"].reason
    )
    assert (
        got["faster_than_mox"].status == claims.SUPPORTED
    )  # fixture: cf 0.7-0.9x against mox 0.45-0.5x
    assert got["gzip_gap_is_hw_crc"].status == claims.SUPPORTED
    rewrite(results, "framing_hypothesis", lambda rows: [{**r, "verdict": "refuted"} for r in rows])
    refuted = by_id(results)["gzip_gap_is_hw_crc"]
    assert refuted.status == claims.REJECTED and "refuted" in refuted.reason
    rewrite(
        results,
        "perf_aggregates",
        lambda rows: [{**r, "ratio_vs_zlib": "0.97"} if r["subject"] == "cf" else r for r in rows],
    )
    assert by_id(results)["parity_with_zlib"].status == claims.SUPPORTED


def test_every_supported_claim_has_evidence_with_raw_and_script(results):
    got = by_id(results)
    supported = [c for c in got.values() if c.status == claims.SUPPORTED]
    assert {c.id for c in supported} >= {"conformance", "safety", "perf_range", "trajectory", "similarity", "effort",
                                           "faster_than_mox", "gzip_gap_is_hw_crc"}  # fmt: skip
    for c in supported:
        assert c.evidence and c.text, c.id
        for e in c.evidence:
            assert e.raw_files and all(p.endswith(".json") for p in e.raw_files), (c.id, e.table)
            assert e.script.startswith("cfbench"), (c.id, e.table)
            assert e.display
    # every number printed in a text comes from an evidence display
    perf = got["perf_range"]
    shown = {e.display for e in perf.evidence}
    assert "0.76x" in shown and "0.89x" in shown and "0.76x" in perf.text


def test_evidence_can_only_be_built_by_lookup(results):
    with pytest.raises(TypeError):
        evidence.Evidence(1.0, "1", "t", (), "c", (), "s", "1")
    e = evidence.lookup(
        "conformance",
        {"machine": "M-B", "subject": "cf"},
        "streams",
        results_dir=results,
        fmt="{:.0f}",
    )
    assert e.value == 100.0 and e.display == "100" and e.cell == "100" and e.table == "conformance"
    assert "conformance.csv [machine=M-B, subject=cf] streams <- cfbench.conformance" in e.source()
    with pytest.raises(evidence.MissingData, match="make conformance"):
        evidence.lookup("conformance", {"machine": "M-X"}, "streams", results_dir=results)
    with pytest.raises(evidence.MissingData, match="no column"):
        evidence.lookup(
            "conformance", {"machine": "M-B", "subject": "cf"}, "nope", results_dir=results
        )
    with pytest.raises(evidence.MissingData, match="not unique"):
        evidence.lookup("conformance", {"machine": "M-B"}, "streams", results_dir=results)
    with pytest.raises(evidence.MissingData, match="empty"):
        evidence.lookup("effort_totals", {"round": "total"}, "cost_usd", results_dir=results)


def test_pending_tables_raise_missing_data(tmp_path, monkeypatch):
    from cfbench import paths

    d = tmp_path / "r"
    d.mkdir()
    monkeypatch.setattr(paths, "RESULTS", d)
    provenance.write_table(
        "trajectory",
        ["machine"],
        [],
        script="s",
        raw_files=[],
        pending="Pending: run make trajectory",
    )
    with pytest.raises(evidence.MissingData, match="pending: Pending: run make trajectory"):
        evidence.lookup("trajectory", {"machine": "M-A"}, "machine", results_dir=d)
