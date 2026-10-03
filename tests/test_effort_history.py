import json
from pathlib import Path

from cfbench import config
from cfbench.effort import history as h

FIX = Path(__file__).parent / "fixtures" / "effort"
CFG = config.load_config("full")
COMMITS = h.parse_git_log((FIX / "gitlog.txt").read_text())
ROUNDS = [
    {"round": 1, "tag": "v1", "sha": "a5"},
    {"round": 2, "tag": "v2", "sha": "b2"},
]


def test_round_windows_from_tag_commits():
    assert [c.sha for c in COMMITS] == ["a1", "a2", "a3", "a4", "a5", "b1", "b2"]  # committer order
    w = h.round_windows(COMMITS, ["a5", "b2"])
    assert [c.sha for c in w[0]] == ["a1", "a2", "a3", "a4", "a5"]  # first commit .. r1 inclusive
    assert [c.sha for c in w[1]] == ["b1", "b2"]  # after r1 .. r2 inclusive
    assert (
        h.milestone("P1-02") == "P1"
        and h.milestone("R1-01") == "R1"
        and h.milestone(None) == "other"
    )
    assert h.milestone("review") == "other"
    c = {c.sha: c for c in COMMITS}
    assert (c["a2"].stage, c["a2"].task) == ("implement", "P0-01") and c["a1"].stage is None
    assert c["a3"].defects == ("unit test for the bit reader found an off-by-one",)


def test_stage_wall_clock_attribution():
    w = h.round_windows(COMMITS, ["a5", "b2"])
    r1 = h.stage_wall_clock(w[0], None, idle_gap_seconds=3600)
    # gaps: a1 0 (untagged), a2 600, a3 600 (implement), a4 600 (review), a5 600 (fix)
    assert r1["by_stage"] == {"fix": 600, "implement": 1200, "review": 600, "untagged": 0}
    assert r1["by_milestone"] == {"P0": 600, "P1": 600, "R1": 600, "other": 600}
    assert r1["attributed_seconds"] == 2400 and r1["idle_seconds"] == 0
    assert (r1["start_ts"], r1["end_ts"], r1["commits"]) == (1000, 3400, 5)
    r2 = h.stage_wall_clock(w[1], w[0][-1].ts, idle_gap_seconds=3600)
    # b1 follows a5 by 16600 s, beyond the idle threshold: reported as idle, not attributed
    assert r2["idle_seconds"] == 16600 and r2["by_stage"] == {"untagged": 600}
    assert r2["commits_by_stage"] == {"implement": 1, "untagged": 1}
    assert h.stage_wall_clock(w[1], w[0][-1].ts, 10**6)["by_stage"]["implement"] == 16600


def test_denied_calls_grouped_by_category():
    entries = h.parse_tool_log((FIX / "tool-log.jsonl").read_text())
    s = h.tool_log_summary(entries, CFG["effort"]["denial_categories"])
    assert s["calls"] == 5
    assert s["denied"]["count"] == 4
    assert s["denied"]["categories"] == {
        "clean-room forbidden word": 1, "network lockdown": 1, "other": 1, "recursive grep": 1,
    }  # fmt: skip
    assert s["models_by_stage"] == {
        "implement": {"m-opus": 3},
        "review": {"m-sonnet": 1},
    }  # entries without a model are not counted; a null stage is 'unknown'
    assert (
        h.categorize_denial(
            "SPEC phase-2 section 2.2: profile only", CFG["effort"]["denial_categories"]
        )
        == "profiling rule"
    )
    assert h.categorize_denial(None, CFG["effort"]["denial_categories"]) == "other"


def test_defect_sources_from_trailers():
    kw = CFG["effort"]["defect_keywords"]
    assert h.defect_source("unit test caught an off-by-one", "implement", kw) == "unit_tests"
    assert (
        h.defect_source("conformance run vs the oracle found a bug", "implement", kw)
        == "conformance"
    )
    assert h.defect_source("fuzz crash in the parser", "implement", kw) == "fuzzing"
    assert h.defect_source("something odd happened", "implement", kw) == "other"
    assert (
        h.defect_source("something odd happened", "fix", kw) == "review"
    )  # review-fix commits are review
    # several keywords: a review-fix commit prefers review, an implement commit takes the priority order
    both = "reviewer noticed a missing fuzz seed and a test gap"
    assert h.defect_source(both, "fix", kw) == "review"
    assert h.defect_source(both, "implement", kw) == "fuzzing"
    w = h.round_windows(COMMITS, ["a5", "b2"])
    d1 = h.defects_summary(w[0], kw)
    assert d1 == {"by_source": {"review": 1, "unit_tests": 1}, "found": 2, "none": 1}
    assert h.defects_summary(w[1], kw)["by_source"] == {"conformance": 1}


def test_interventions_table_parsed_and_duration_gap_recorded():
    rows = h.parse_interventions((FIX / "interventions.md").read_text())
    assert [r["who"] for r in rows] == ["operator", "operator", "operator (via controller)"]
    assert (
        rows[0]["what"] == "Supplied a file by hand." and rows[0]["stage_task"] == "implement/P0-01"
    )
    bounds = [3400, 20600]
    assert [h.intervention_round(r, bounds) for r in rows] == [
        1,
        2,
        2,
    ]  # phase-2 mention wins for row 2
    # no durations anywhere in the rows; the payload says so
    assert all(set(r) == {"when", "who", "stage_task", "what", "why"} for r in rows)

    def fake_git(clone, *args):
        if args[0] == "log":
            return (FIX / "gitlog.txt").read_text()
        ref = args[1]
        if ref.endswith(h.SNAPSHOT):
            return (FIX / "tool-log.jsonl").read_text()
        if ref.endswith(h.INTERVENTIONS):
            return (FIX / "interventions.md").read_text()
        return (FIX / ("state-r1.json" if ref.startswith("a5") else "state-r2.json")).read_text()

    payload = h.collect(clone=Path("."), cfg=CFG, git=fake_git, rounds=ROUNDS)
    assert h.DURATION_GAP in payload["gaps"] and "durations are unavailable" in payload["gaps"][0]
    r1, r2 = payload["rounds"]
    assert r1["interventions"]["count"] == 1 and r2["interventions"]["count"] == 2
    assert r1["tool_log"]["denied"]["count"] == 3 and r2["tool_log"]["denied"]["count"] == 1
    assert r1["foundry"]["review_rounds"] == 2 and r1["foundry"]["reviews"][0]["fix_tasks"] == 2
    assert r2["foundry"]["verdict"] == "APPROVED"
    assert payload["method"]["idle_gap_hours"] == CFG["effort"]["idle_gap_hours"]
    assert json.dumps(payload)  # serialisable


RULES = CFG["effort"]["forbidden_reads"]


def entry(target, tool="Bash", decision="allowed", ts="2026-09-29T00:00:00.000Z"):
    return {"ts": ts, "tool": tool, "target": target, "decision": decision,
            "foundry_stage": "implement", "task_id": "P1-01"}  # fmt: skip


def test_path_tokens_split_shell_words_and_keep_file_targets():
    assert h.path_tokens("Read", "/x/y.rs") == ["/x/y.rs"]
    toks = h.path_tokens("Bash", "cat /a/b.c | grep x>/tmp/o; ls ~/.cargo/registry 'q'")
    assert toks == ["/a/b.c", "/tmp/o", "~/.cargo/registry"]
    assert h.path_tokens("Bash", "echo 'unbalanced") == []  # shlex failure falls back to whitespace


def test_forbidden_read_rules():
    root = RULES["repo_root"]
    # inside the build checkout a prior-art word is the project's own module name
    assert (
        h.forbidden_read_match(entry(f"{root}/crates/cleanflate/src/zlib.rs", tool="Read"), RULES)
        is None
    )
    # outside it, the word counts; so do the guard's forbidden roots, whatever the tool
    m = h.forbidden_read_match(entry("cat /opt/src/zlib-1.3/inflate.c"), RULES)
    assert m == {
        "path": "/opt/src/zlib-1.3/inflate.c",
        "rule": "word zlib outside the build checkout",
    }
    r = h.forbidden_read_match(
        entry("/home/u/.cargo/registry/src/libz-sys/lib.rs", tool="Read"), RULES
    )
    assert r["rule"].startswith("root ")
    assert h.forbidden_read_match(entry(f"cat {root}/target/release/build/x/out.c"), RULES)[
        "rule"
    ].startswith("root ")
    # denied calls and tools that cannot read are not candidates
    assert (
        h.forbidden_read_match(entry("cat /usr/include/zlib.h", decision="denied"), RULES) is None
    )
    assert h.forbidden_read_match(entry("/usr/include/zlib.h", tool="Write"), RULES) is None


def test_tool_log_summary_counts_read_calls_and_candidates():
    entries = [entry("ls /tmp"), entry("cat /usr/include/zlib.h", ts="t1"), entry("/x", tool="Write"),
               entry("cat /usr/include/zlib.h", decision="denied")]  # fmt: skip
    s = h.tool_log_summary(entries, CFG["effort"]["denial_categories"], RULES)
    fr = s["forbidden_reads"]
    assert fr["read_calls"] == 2
    assert [c["ts"] for c in fr["candidates"]] == ["t1"] and fr["candidates"][0]["task"] == "P1-01"
    assert "forbidden_reads" not in h.tool_log_summary(entries, CFG["effort"]["denial_categories"])
