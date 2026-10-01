import pytest

from cfbench.similarity import comments


def test_words_are_lowercase_alphanumeric_runs():
    assert comments.words("// Build the Huffman-table (RFC 1951 §3.2.2)!") == [
        "build", "the", "huffman", "table", "rfc", "1951", "3", "2", "2",
    ]  # fmt: skip


def test_comment_ngram_jaccard(tmp_path):
    a = tmp_path / "a.rs"
    b = tmp_path / "b.rs"
    a.write_text("// one two three four five six\nfn f() {}\n")
    b.write_text("/* one two three four five seven */\nfn g() {}\n")
    sa, ca = comments.comment_shingles([a], 5)
    sb, cb = comments.comment_shingles([b], 5)
    assert ca == cb == 1
    assert len(sa) == len(sb) == 2  # (one..five) (two..six) and (one..five) (two..five seven)
    r = comments.compare(sa, sb)
    assert r["jaccard"] == pytest.approx(1 / 3)  # one shared 5-gram out of three distinct
    assert r["containment"] == pytest.approx(1 / 2)
    assert r["size_left"] == r["size_right"] == 2


def test_ngrams_do_not_span_comments(tmp_path):
    f = tmp_path / "a.rs"
    f.write_text("// one two three\n// four five six\nfn f() {}\n")
    s, count = comments.comment_shingles([f], 5)
    assert count == 2 and s == set()  # neither comment has five words on its own
    s3, _ = comments.comment_shingles([f], 3)
    assert s3 == {("one", "two", "three"), ("four", "five", "six")}
