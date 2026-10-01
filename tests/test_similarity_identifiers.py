from cfbench.similarity import identifiers as ids

SRC_A = """
const MAX_BITS: usize = 15;
struct TableBuilder { bl_count: [u16; 16], next_code: [u16; 16], window_size: usize }
fn build_table(hlit: usize, BFINAL: bool, short: u8) {}
"""
SRC_B = """
fn buildTable() { let windowSize = 1; let table_builder = 2; let blCount = 3; }
"""


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_snake_and_camel_normalize_equal():
    assert ids.normalize("window_size") == ids.normalize("windowSize") == "windowsize"
    assert ids.normalize("BitReader") == ids.normalize("bit_reader")


def test_rfc_names_are_excluded(tmp_path):
    excl = ids.load_exclusions()
    excluded = excl["rfc"] | excl["language"]
    for name in ("hlit", "hdist", "hclen", "bfinal", "btype", "len", "nlen", "blcount", "nextcode"):
        assert name in excl["rfc"], name
    f = write(tmp_path, "a.rs", SRC_A)
    everything = ids.collect([f], 1, set())
    kept = ids.collect([f], 1, excluded)
    assert {"blcount", "nextcode", "maxbits", "bfinal", "hlit"} <= everything
    assert not ({"blcount", "nextcode", "maxbits", "bfinal", "hlit"} & kept)
    assert "windowsize" in kept and "tablebuilder" in kept


def test_short_identifiers_are_ignored(tmp_path):
    f = write(tmp_path, "a.rs", SRC_A)
    got = ids.collect([f], 6, set())
    assert "short" not in got and "windowsize" in got and "tablebuilder" in got
    assert all(len(n) >= 6 for n in got)
    assert ids.min_ident_len() == 6


def test_overlap_metrics_and_shared_list(tmp_path):
    a = ids.collect([write(tmp_path, "a.rs", SRC_A)], 6, set())
    b = ids.collect([write(tmp_path, "b.rs", SRC_B)], 6, set())
    r = ids.compare(a, b)
    assert {"windowsize", "tablebuilder", "blcount"} <= set(r["shared"])
    assert r["ident_match_rate_left"] == len(r["shared"]) / r["size_left"]
    assert r["ident_match_rate_right"] == len(r["shared"]) / r["size_right"]
    assert r["ident_jaccard"] == len(r["shared"]) / len(a | b)
    assert ids.compare(set(), set())["ident_jaccard"] == 0.0


def test_exclusion_file_sections_parse():
    text = "# header\nLEN # RFC 1951 §3.2.4\nbl_count\n# language\nunwrap_or\n"
    got = ids.parse_exclusions(text)
    assert got["rfc"] == {"len", "blcount"}
    assert got["language"] == {"unwrapor"}
