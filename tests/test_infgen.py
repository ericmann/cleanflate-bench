from pathlib import Path

import pytest

from cfbench.content import infgen

FIX = Path(__file__).parent / "fixtures" / "infgen"


def parse(name):
    text = (FIX / name).read_text(encoding="latin-1")
    return infgen.parse_lines(text.splitlines())


def test_parses_literal_and_match_lines():
    raw = infgen.parse_lines(
        [
            "! infgen 3.6 output",
            "!",
            "dynamic",
            "literal 13 10 13",  # three bytes as numbers
            "literal 'ab c",  # four bytes as a string (the space counts)
            "literal 13 10 'o",  # numbers then a string: 3 bytes
            "literal ' ",  # a single space
            "literal 'it's",  # a quote inside the string is a byte
            "literal 'tab\t! a comment after a tab",  # the tab ends the string
            "match 5 2",
            "match 258 1",
            "match 3 32768",
            "end",
        ]
    )
    assert raw["literals"] == 3 + 4 + 3 + 1 + 4 + 3
    assert raw["matches"] == 3 and raw["match_bytes"] == 5 + 258 + 3
    assert infgen.count_bytes(" 0 255 'xyz") == 5 and infgen.count_bytes(" 'a b ") == 4
    s = infgen.summarize(raw, compressed_bytes=100)
    assert s["literals"] == 18 and s["output_bytes"] == 18 + 266
    assert s["literal_fraction"] == pytest.approx(18 / 284) and s["ratio"] == pytest.approx(
        100 / 284
    )
    # histogram bins
    assert s["match_len_hist"] == {
        "3": 1,
        "4": 0,
        "5-8": 1,
        "9-16": 0,
        "17-32": 0,
        "33-64": 0,
        "65-128": 0,
        "129-258": 1,
    }
    assert s["match_dist_hist"] == {
        "1": 1,
        "2-7": 1,
        "8-64": 0,
        "65-512": 0,
        "513-4096": 0,
        "4097-32768": 1,
    }
    assert (
        list(s["match_len_hist"]) == infgen.LEN_BINS
        and list(s["match_dist_hist"]) == infgen.DIST_BINS
    )


def test_bin_edges_are_inclusive_upper_bounds():
    for length, want in (
        (3, "3"),
        (4, "4"),
        (5, "5-8"),
        (8, "5-8"),
        (9, "9-16"),
        (258, "129-258"),
        (129, "129-258"),
    ):
        raw = infgen.parse_lines([f"match {length} 1"])
        assert infgen.summarize(raw, 1)["match_len_hist"][want] == 1, length
    for dist, want in (
        (1, "1"),
        (2, "2-7"),
        (7, "2-7"),
        (8, "8-64"),
        (64, "8-64"),
        (65, "65-512"),
        (4096, "513-4096"),
        (4097, "4097-32768"),
    ):
        raw = infgen.parse_lines([f"match 10 {dist}"])
        assert infgen.summarize(raw, 1)["match_dist_hist"][want] == 1, dist


def test_block_type_counts():
    assert parse("stored.raw.infgen")["blocks"] == {"stored": 1, "fixed": 0, "dynamic": 0}
    assert parse("fixed.raw.infgen")["blocks"] == {"stored": 0, "fixed": 1, "dynamic": 0}
    assert parse("dynamic.raw.infgen")["blocks"]["dynamic"] >= 1
    mixed = infgen.parse_lines(
        [
            "stored",
            "data 'x",
            "end",
            "fixed",
            "end",
            "dynamic",
            "end",
            "last",
            "dynamic",
            "end",
            "block3",
        ]
    )
    assert mixed["blocks"] == {
        "stored": 1,
        "fixed": 1,
        "dynamic": 2,
    }  # block3 is invalid and not counted
    assert (
        mixed["stored_bytes"] == 1 and mixed["literals"] == 0
    )  # stored data is output, not coded literals


def test_overlap_and_short_distance_fractions():
    s = infgen.summarize(parse("zeros.raw.infgen"), 7)
    # "literal 0 0", "match 258 1", "match 40 1": every match overlaps itself and has distance 1
    assert s["matches"] == 2 and s["overlap_fraction"] == 1.0 and s["dist1_fraction"] == 1.0
    assert s["dist1_byte_fraction"] == pytest.approx(298 / 300) and s[
        "literal_fraction"
    ] == pytest.approx(2 / 300)
    assert s["dist2_7_fraction"] == 0.0
    fixed = infgen.summarize(parse("fixed.raw.infgen"), 15)
    # match 11 3 overlaps (11 > 3, distance in 2-7); match 6 6 does not (distance equals length)
    assert fixed["matches"] == 2 and fixed["overlap_fraction"] == pytest.approx(0.5)
    assert fixed["dist2_7_fraction"] == 1.0 and fixed["dist1_fraction"] == 0.0
    assert fixed["overlap_byte_fraction"] == pytest.approx(11 / 27)
    nothing = infgen.summarize(infgen.parse_lines(["stored", "data 'x", "end"]), 5)
    assert (
        nothing["matches"] == 0
        and nothing["dist1_fraction"] is None
        and nothing["overlap_fraction"] is None
    )


@pytest.mark.parametrize(
    "name",
    ["stored.raw", "fixed.raw", "dynamic.raw", "zeros.raw", "zlib_l9.zlib"],
)
def test_output_bytes_match_original_length(name):
    stem = name.split(".")[0]
    orig = (FIX / f"{stem}.orig").read_bytes()
    comp = (FIX / f"{name}.bin").read_bytes()
    s = infgen.summarize(parse(f"{name}.infgen"), len(comp))
    assert s["output_bytes"] == len(orig)
    assert s["compressed_bytes"] == len(comp) and s["ratio"] == pytest.approx(len(comp) / len(orig))
    assert s["literals"] <= s["output_bytes"]


def test_pinned_download_is_configured():
    s = infgen.spec()
    assert len(s["commit"]) == 40 and s["commit"] in s["url"] and len(s["sha256"]) == 64
    assert infgen.binary_path().name == "infgen"
