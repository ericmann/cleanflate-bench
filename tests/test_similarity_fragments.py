import pytest

from cfbench.similarity import fragments as fr
from cfbench.similarity.tokens import Token


def toks(words, start_line=1):
    """Tokens that are their own normalised form; one per line unless the word has a newline."""
    return [Token("TOK", w, start_line + i) for i, w in enumerate(words)]


def run(left, right, min_len=4, **kw):
    return fr.find_fragments(
        {n: toks(w) for n, w in left.items()}, {n: toks(w) for n, w in right.items()}, min_len, **kw
    )


def test_maximal_runs_are_found_and_ranked():
    common_long = list("ABCDEFGHIJ")  # 10 tokens
    common_short = list("PQRSTU")  # 6 tokens
    left = {"l.rs": ["x1", *common_short, "x2", "x3", *common_long, "x4"]}
    right = {"r.rs": [*common_long, "y1", "y2", *common_short, "y3"]}
    frags, skipped = run(left, right)
    assert skipped == 0
    assert [f.tokens for f in frags] == [10, 6]  # maximal, longest first, not 7 windows of 4
    long_, short = frags
    assert (long_.left_file, long_.left_start, long_.left_end) == ("l.rs", 10, 19)
    assert (long_.right_file, long_.right_start, long_.right_end) == ("r.rs", 1, 10)
    assert (short.left_start, short.left_end, short.right_start, short.right_end) == (2, 7, 13, 18)
    assert long_.run == tuple(common_long)
    only_top = run(left, right, top_k=1)[0]
    assert len(only_top) == 1 and only_top[0].tokens == 10


def test_ties_break_by_file_then_line():
    run_ = list("WXYZ")
    left = {"b.rs": run_, "a.rs": ["q", *run_]}
    right = {"r.rs": run_}
    frags, _ = run(left, right)
    assert [f.left_file for f in frags] == ["a.rs", "b.rs"]


def test_runs_do_not_span_files():
    left = {"l1.rs": list("ABCDE"), "l2.rs": list("FGHIJ")}
    right = {"r.rs": list("ABCDEFGHIJ")}
    frags, _ = run(left, right, min_len=4)
    assert sorted(f.tokens for f in frags) == [5, 5]  # the 10-token run is split at the file edge


def test_repeated_windows_are_skipped_above_the_cap():
    left = {"l.rs": ["a", "b", "c", "d"] * 30}
    right = {"r.rs": ["a", "b", "c", "d"] * 30}
    frags, skipped = run(left, right, min_len=4, max_occurrences=10)
    assert frags == [] and skipped > 0
    frags_all, skipped_all = run(left, right, min_len=4)
    assert frags_all and skipped_all == 0


def test_fragment_id_is_stable():
    left = {"l.rs": list("ABCDE")}
    a = run(left, {"r.rs": list("ABCDE")})[0][0]
    b = run(left, {"r.rs": list("ABCDE")})[0][0]
    assert fr.fragment_id(a) == fr.fragment_id(b)
    assert len(fr.fragment_id(a)) == 12 and int(fr.fragment_id(a), 16) >= 0
    moved = run(left, {"other.rs": list("ABCDE")})[0][0]
    assert fr.fragment_id(moved) != fr.fragment_id(a)  # file paths are part of the id
    different = run({"l.rs": list("ABCDX")}, {"r.rs": list("ABCDX")})[0][0]
    assert fr.fragment_id(different) != fr.fragment_id(a)


TOML = """
[cf_zrs]
"66f174b99c8d" = { verdict = "RFC-forced", note = "Adler-32 per RFC 1950" }
"""


def test_stored_verdict_is_merged():
    stored = fr.parse_verdicts(TOML)["cf_zrs"]
    rows = [
        {"fragment_id": "66f174b99c8d", "rank": 1},
        {"fragment_id": "ffffffffffff", "rank": 2},
    ]
    merged = fr.merge_verdicts(rows, stored)
    assert merged[0]["verdict"] == "RFC-forced" and merged[0]["note"] == "Adler-32 per RFC 1950"
    assert merged[1]["verdict"] == "" and merged[1]["note"] == ""  # unknown id stays empty
    assert fr.merge_verdicts(rows, {}) == [{**r, "verdict": "", "note": ""} for r in rows]


def test_invalid_verdict_value_raises():
    with pytest.raises(ValueError, match="not in"):
        fr.parse_verdicts('[cf_zrs]\n"abc" = { verdict = "looks fine" }\n')
    with pytest.raises(ValueError):
        fr.parse_verdicts('[cf_zrs]\n"abc" = { note = "no verdict" }\n')
    assert set(fr.VERDICTS) == {"RFC-forced", "idiomatic-inevitable", "suspicious"}


def test_shipped_verdict_file_is_valid():
    assert fr.load_verdicts() == {}


def test_markdown_lists_verdict_and_excerpts():
    pair = {"left": "cf", "right": "zrs", "role": "test"}
    row = {"rank": 1, "fragment_id": "abc", "tokens": 12, "left_file": "a.rs", "left_lines": "1-2",
           "right_file": "b.rs", "right_lines": "3-4", "left_excerpt": "fn a() {}",
           "right_excerpt": "fn b() {}", "verdict": "suspicious", "note": "look"}  # fmt: skip
    md = fr.markdown(pair, [row])
    assert "Verdict: suspicious - look" in md and "fn a() {}" in md and "fn b() {}" in md
    assert "(none yet)" in fr.markdown(pair, [{**row, "verdict": "", "note": ""}])
