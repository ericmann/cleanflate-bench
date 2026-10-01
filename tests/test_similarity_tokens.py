import pytest

from cfbench.similarity import tokens

RUST = """
// a comment
fn f(count: u32) -> u32 {
    for i in 0..count { if i == 3 { break; } }
    /* block */
    match count { 1 => 2, _ => 3 }
}
"""

C = """
/* a comment */
int f(int count) {
    for (int i = 0; i < count; i++) { if (i == 3) break; }
    switch (count) { case 1: return 2; default: return 3; }
}
"""


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def norms(path):
    return [t.norm for t in tokens.tokenize(path)]


def test_rust_and_c_loops_map_to_same_class(tmp_path):
    rs = norms(write(tmp_path, "a.rs", "fn f() { for i in x {} while c {} loop {} }"))
    c = norms(write(tmp_path, "a.c", "void f() { for (;;) {} while (c) {} do {} while (0); }"))
    assert rs.count("LOOP") == 3
    assert c.count("LOOP") == 4
    assert "for" not in rs and "while" not in c
    rs_sw = norms(write(tmp_path, "b.rs", "fn f() { match x { _ => 1 } }"))
    c_sw = norms(write(tmp_path, "b.c", "void f() { switch (x) { default: break; } }"))
    assert "SWITCH" in rs_sw and "SWITCH" in c_sw
    assert "FN" in rs and "FN" in c  # Rust `fn`, synthetic head token for C definitions


def test_impl_for_is_not_a_loop(tmp_path):
    n = norms(write(tmp_path, "i.rs", "impl Trait for Type {}"))
    assert "LOOP" not in n and "for" in n


def test_identifiers_are_abstracted(tmp_path):
    a = norms(write(tmp_path, "a.rs", 'fn alpha(x: u8) -> u8 { let s = "one"; x + 1 }'))
    b = norms(write(tmp_path, "b.rs", 'fn beta(yy: u32) -> u32 { let t = "two"; yy + 99 }'))
    assert a == b
    assert {"ID", "NUM", "STR", "TYPE", "FN"} <= set(a)
    toks = tokens.tokenize(tmp_path / "a.rs")
    assert [t.text for t in toks if t.kind == "ID"][:2] == ["alpha", "x"]  # real text is kept


def test_comments_are_separated(tmp_path):
    rs = write(tmp_path, "a.rs", RUST)
    c = write(tmp_path, "a.c", C)
    for p, want in ((rs, ["// a comment", "/* block */"]), (c, ["/* a comment */"])):
        found = tokens.comments(p)
        assert [text.strip() for _line, text in found] == want
        assert all("comment" not in t.text and "block" not in t.text for t in tokens.tokenize(p))
    assert tokens.comments(rs)[0][0] == 2


def test_char_and_number_literals(tmp_path):
    n = norms(write(tmp_path, "l.rs", "fn f() { let c = 'x'; let n = 1_u8; let f = 2.5; }"))
    assert n.count("CHAR") == 1 and n.count("NUM") == 2


def test_unknown_extension_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        tokens.tokenize(write(tmp_path, "a.txt", "x"))


def test_token_lines_are_one_based(tmp_path):
    toks = tokens.tokenize(write(tmp_path, "a.rs", "\n\nfn f() {}\n"))
    assert toks[0].line == 3


def test_deeply_nested_source_does_not_overflow_the_stack(tmp_path):
    depth = 3000
    src = "fn f() { " + "if x { " * depth + "y" + " }" * depth + " }"
    toks = tokens.tokenize(write(tmp_path, "deep.rs", src))
    assert sum(1 for t in toks if t.norm == "if") == depth
    chain = "int f(int x) { " + "if (x) {} else " * depth + "{} }"
    assert (
        sum(1 for t in tokens.tokenize(write(tmp_path, "chain.c", chain)) if t.norm == "else")
        == depth
    )
