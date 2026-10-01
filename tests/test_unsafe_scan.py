from cfbench import unsafe_scan as u

SRC = """
#![deny(clippy::unwrap_used)]
// unsafe { in a comment } and unsafe fn nope
/* block unsafe { } /* nested unsafe impl X */ still comment */
const S: &str = "unsafe { not code }";
const R: &str = r#"unsafe fn raw "quoted" "#;
fn a() { unsafe { core::hint::unreachable_unchecked() } }
unsafe fn b() {}
pub unsafe extern "C" fn c() {}
unsafe impl Send for T {}
unsafe trait Marker {}
#[target_feature(enable = "avx2")]
fn d() { let _c = '"'; unsafe { x() } }
"""


def test_counts_blocks_fns_impls_ignoring_comments_and_strings():
    c = u.count_text(SRC)
    assert c == {
        "unsafe_blocks": 2,
        "unsafe_fns": 2,
        "unsafe_impls": 1,
        "unsafe_traits": 1,
        "target_feature": 1,
    }


def test_detects_forbid_unsafe_code(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("#![forbid(unsafe_code)]\nfn main() {}\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.rs").write_text("fn t() { unsafe { } }\n")
    r = u.scan_crate(tmp_path)
    assert r["forbid_unsafe_code"] is True
    assert r["deny_unsafe_code"] is False
    assert r["totals"]["unsafe_blocks"] == 0
    assert list(r["files"]) == ["src/lib.rs"]


def test_commented_forbid_is_not_detected_and_deny_is(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(
        "// #![forbid(unsafe_code)]\n#![deny(missing_docs, unsafe_code)]\nfn f() { unsafe { } }\n"
    )
    r = u.scan_crate(tmp_path)
    assert r["forbid_unsafe_code"] is False
    assert r["deny_unsafe_code"] is True
    assert r["totals"]["unsafe_blocks"] == 1
