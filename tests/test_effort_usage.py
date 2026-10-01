import json
from pathlib import Path

import pytest

from cfbench import paths
from cfbench.effort import usage as u

ROOT = Path(__file__).parent / "fixtures" / "effort" / "transcripts"
ISO = lambda t: u._epoch(f"1970-01-01T{t}Z")
BOUNDS = [int(ISO("00:03:15")), int(ISO("01:00:00"))]  # round 1 ends at 00:03:15
FIRST_REVIEW = {
    1: None,
    2: int(ISO("00:04:00")),
}  # in round 2, after 00:04:00 an implementer is fixing
TOOL_LOG = [(int(ISO("00:04:20")), "plan"), (int(ISO("00:04:40")), "review")]


def records():
    recs, dupes = u.read_records(ROOT)
    return recs, dupes


def test_export_contains_no_content_fields():
    recs, _ = records()
    attributed = u.attribute(recs, BOUNDS, FIRST_REVIEW, TOOL_LOG)
    allowed = set(u.EXPORT_FIELDS) | set(u.DERIVED_FIELDS)
    for r in attributed:
        assert set(r) == allowed
    blob = json.dumps(attributed)
    assert "SYNTHETIC-SENTINEL-TEXT" not in blob
    assert '"content"' not in blob and '"text"' not in blob
    assert u.EXPORT_FIELDS == [
        "ts", "session_id", "transcript", "agent_type", "model", "input_tokens", "output_tokens",
        "cache_creation_5m", "cache_creation_1h", "cache_read_tokens", "message_id", "request_id",
    ]  # fmt: skip
    assert {r["transcript"] for r in recs} == {
        "sess1.jsonl", "sess1/subagents/agent-impl.jsonl", "sess1/subagents/agent-rev.jsonl",
    }  # fmt: skip


def test_duplicate_streaming_records_are_deduplicated():
    recs, dupes = records()
    assert dupes == 2  # m1 appeared three times
    m1 = [r for r in recs if r["message_id"] == "m1"]
    assert len(m1) == 1 and m1[0]["output_tokens"] == 40  # the most complete record is kept
    assert len(recs) == 8


def test_subagent_type_maps_to_stage():
    assert u.stage_from_agent("foundry:implementer") == "implement"
    assert u.stage_from_agent("foundry-reviewer") == "review"
    assert u.stage_from_agent("foundry:planner") == "plan"
    assert u.stage_from_agent("foundry-summarizer") == "summarize"
    assert u.stage_from_agent(None) is None
    recs, _ = records()
    got = {
        r["message_id"]: (r["stage"], r["round"])
        for r in u.attribute(recs, BOUNDS, FIRST_REVIEW, TOOL_LOG)
    }
    assert got["m1"] == ("controller", 1) and got["m2"] == ("controller", 1)
    assert got["m3"] == ("implement", 1)
    assert got["m4"] == ("fix", 2)  # after the first review, and past the round 1 boundary
    assert got["m5"] == ("review", 1) and got["m6"] == ("plan", 2) and got["m7"] == ("summarize", 2)
    assert got["m8"] == (
        "plan",
        2,
    )  # unknown agent type: nearest preceding tool-log entry (00:04:20)


def test_fallback_uses_nearest_preceding_tool_log_entry():
    recs, _ = records()
    m8 = next(r for r in recs if r["message_id"] == "m8")
    same = u.attribute(
        [m8], BOUNDS, FIRST_REVIEW, [(int(ISO("00:04:00")), "fix"), (int(ISO("00:09:00")), "plan")]
    )
    assert (
        same[0]["stage"] == "fix" and same[0]["stage_method"] == "nearest preceding tool-log entry"
    )
    none = u.attribute([m8], BOUNDS, FIRST_REVIEW, [])
    assert none[0]["stage"] == "unknown"


def test_missing_price_yields_null_cost_and_gap():
    recs, _ = records()
    attributed = u.attribute(recs, BOUNDS, FIRST_REVIEW, TOOL_LOG)
    unset = u.load_prices()
    assert all(not any(k in p for k in u.PRICE_KEYS) for p in unset.values())
    s = u.summarize(attributed, {"model-a": {}, "model-b": {}})
    assert all(c["cost_usd"] is None for c in s["cells"])
    assert any("no price for model model-a" in g for g in s["gaps"])
    priced = {k: 1.0 for k in u.PRICE_KEYS}
    s2 = u.summarize(attributed, {"model-a": priced, "model-b": {"input_per_mtok": 1.0}})
    a = [c for c in s2["cells"] if c["model"] == "model-a"]
    assert all(c["cost_usd"] is not None for c in a)
    assert all(c["cost_usd"] is None for c in s2["cells"] if c["model"] == "model-b")
    one = u.cost_of({"input_tokens": 1_000_000, "output_tokens": 0, "cache_creation_5m": 0,
                     "cache_creation_1h": 0, "cache_read_tokens": 0}, {**priced, "input_per_mtok": 3.0})  # fmt: skip
    assert one == pytest.approx(3.0)
    totals = {(c["round"], c["stage"], c["model"]): c for c in s["cells"]}
    c = totals[(1, "controller", "model-a")]
    assert (c["messages"], c["input_tokens"], c["output_tokens"], c["cache_read_tokens"]) == (
        1,
        10,
        40,
        1000,
    )


def test_missing_transcripts_dir_refuses_without_allow_gaps(tmp_path, monkeypatch, capsys):
    from cfbench import config

    cfg = config.load_config("full")
    cfg["effort"]["transcripts_dir"] = str(tmp_path / "nope")
    monkeypatch.setattr(u.config, "load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    assert u.main([]) == 1
    assert "--allow-gaps" in capsys.readouterr().err
    assert not (
        tmp_path / "raw"
    ).exists()  # nothing written, so no empty export can replace a real one
    assert u.main(["--allow-gaps"]) == 0
    files = list((tmp_path / "raw" / "effort" / "any").glob("*.json"))
    doc = json.loads(files[0].read_text())["payload"]
    assert doc["records"] == [] and "missing" in doc["gaps"][0]


def test_cache_creation_breakdown_falls_back_to_total():
    rec = {"type": "assistant", "timestamp": "1970-01-01T00:00:00Z", "sessionId": "s", "requestId": "r",
           "message": {"id": "m", "model": "x", "usage": {"input_tokens": 1, "output_tokens": 2,
                                                          "cache_creation_input_tokens": 9}}}  # fmt: skip
    out = u.export_record(rec, "f.jsonl")
    assert (out["cache_creation_5m"], out["cache_creation_1h"]) == (9, 0)
    assert u.export_record({"type": "user"}, "f") is None
