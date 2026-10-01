from cfbench.similarity import ngram


def test_identical_streams_jaccard_one():
    a = ngram.shingles(list("abcdefgh"), 3)
    assert ngram.jaccard(a, ngram.shingles(list("abcdefgh"), 3)) == 1.0


def test_disjoint_streams_jaccard_zero():
    a = ngram.shingles(list("abcdef"), 3)
    b = ngram.shingles(list("uvwxyz"), 3)
    assert ngram.jaccard(a, b) == 0.0
    assert ngram.containment(a, b) == 0.0


def test_containment_uses_smaller_set():
    small = ngram.shingles(list("abcd"), 2)  # ab bc cd
    big = ngram.shingles(list("abcdxyzxyz"), 2)
    assert ngram.containment(small, big) == 1.0
    assert ngram.jaccard(small, big) < 1.0
    assert ngram.containment(big, small) == ngram.containment(small, big)


def test_short_streams_have_no_shingles_and_score_zero():
    assert ngram.shingles(list("ab"), 5) == set()
    assert ngram.jaccard(set(), set()) == 0.0
    assert ngram.containment(set(), {("a",)}) == 0.0


def test_compare_unions_per_file_shingles_without_spanning_files(tmp_path):
    (tmp_path / "a1.rs").write_text("fn f() { let x = 1; }")
    (tmp_path / "a2.rs").write_text("fn g() { let y = 2; }")
    (tmp_path / "b.rs").write_text("fn h() { let z = 3; }")
    r = ngram.compare([tmp_path / "a1.rs", tmp_path / "a2.rs"], [tmp_path / "b.rs"], 5)
    assert r["jaccard"] == 1.0  # identifiers and literals are abstracted
    assert r["size_a"] == r["size_b"] > 0
    assert set(r) == {"jaccard", "containment", "size_a", "size_b"}
