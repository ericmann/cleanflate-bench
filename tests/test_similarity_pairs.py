from cfbench import config
from cfbench.similarity import pairs


def test_pairs_loaded_with_roles():
    ps = pairs.load_pairs(config.load_config("full"))
    by_role = {}
    for p in ps:
        by_role.setdefault(p["role"], []).append((p["left"], p["right"]))
    assert by_role["negative"] == [("zrs", "mox")]
    assert by_role["positive"] == [("zrs", "zng")]
    assert by_role["test"] == [("cf", "zrs"), ("cf", "mox"), ("cf", "zlib"), ("cf", "zng")]
    assert len(ps) == 6


def test_ngrams_do_not_span_files():
    f1, f2 = list("ABCDE"), list("FGHIJ")
    separate = pairs.shingle_union([f1, f2], 3)
    joined = pairs.shingle_union([f1 + f2], 3)
    assert len(separate) == 6  # three per file
    assert len(joined) == 8  # the concatenation adds ('D','E','F') and ('E','F','G')
    assert ("D", "E", "F") not in separate and ("E", "F", "G") not in separate
    assert separate < joined


def test_every_n_in_range_is_reported():
    cfg = config.load_config("full")
    rows = pairs.compare_pair([list("abcdefghijklm")], [list("abcdefghijklm")], cfg)
    sim = cfg["similarity"]
    assert [r["n"] for r in rows] == list(range(sim["ngram_min"], sim["ngram_max"] + 1))
    assert all(r["jaccard"] == 1.0 and r["containment"] == 1.0 for r in rows)
    assert rows[0]["size_left"] == rows[0]["size_right"] == 13 - sim["ngram_min"] + 1
    assert set(rows[0]) == {"n", "jaccard", "containment", "size_left", "size_right"}


def test_cross_language_flag():
    ps = {(p["left"], p["right"]): p for p in pairs.load_pairs(config.load_config("full"))}
    assert ps[("zrs", "mox")]["cross_language"] is False
    assert ps[("cf", "zrs")]["cross_language"] is False
    assert ps[("zrs", "zng")]["cross_language"] is True
    assert ps[("cf", "zlib")]["cross_language"] is True
    assert ps[("cf", "zng")]["cross_language"] is True


def test_file_token_lists_normalise_and_keep_file_order(tmp_path):
    (tmp_path / "b.rs").write_text("fn bee() { loop {} }")
    (tmp_path / "a.c").write_text("int a(void) { return 1; }")
    lists = pairs.file_token_lists([tmp_path / "b.rs", tmp_path / "a.c"])
    assert "LOOP" in lists[0] and "return" in lists[1]
    assert "bee" not in lists[0]
