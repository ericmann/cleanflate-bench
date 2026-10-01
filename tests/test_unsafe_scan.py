import json

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


def _crate(root, name, lib):
    d = root / name
    (d / "src").mkdir(parents=True)
    (d / "src" / "lib.rs").write_text(lib)
    return d


def _metadata(root):
    mox = _crate(root, "miniz_oxide", "fn f() { unsafe { } }\n")
    adler = _crate(root, "adler2", "#![forbid(unsafe_code)]\n")
    buildy = _crate(root, "cc", "fn b() { unsafe { } unsafe { } }\n")
    devy = _crate(root, "criterion", "fn d() {}\n")
    pk = lambda n, d: {
        "name": n, "version": "1.0.0", "id": n, "manifest_path": str(d / "Cargo.toml"),
    }  # fmt: skip
    return {
        "packages": [
            pk("miniz_oxide", mox),
            pk("adler2", adler),
            pk("cc", buildy),
            pk("criterion", devy),
        ],
        "resolve": {
            "nodes": [
                {
                    "id": "miniz_oxide",
                    "deps": [
                        {"pkg": "adler2", "dep_kinds": [{"kind": None}]},
                        {"pkg": "cc", "dep_kinds": [{"kind": "build"}]},
                        {"pkg": "criterion", "dep_kinds": [{"kind": "dev"}]},
                    ],
                },
                {"id": "adler2", "deps": []},
                {"id": "cc", "deps": []},
                {"id": "criterion", "deps": []},
            ]
        },
    }


def test_dependency_rows_are_included(tmp_path, monkeypatch):
    meta = _metadata(tmp_path)
    monkeypatch.setattr(u.sources, "source_root", lambda s, m=None: tmp_path / "miniz_oxide")
    monkeypatch.setattr(u.sources, "extra_roots", lambda s, m=None: [])
    rows = u.scan_subject("mox", meta)
    by = {r["crate"]: r for r in rows}
    assert set(by) == {"miniz_oxide", "adler2"}  # build and dev dependencies are excluded
    assert by["miniz_oxide"]["role"] == "subject" and by["miniz_oxide"]["unsafe_blocks"] == 1
    assert by["adler2"]["role"] == "dependency" and by["adler2"]["forbid_unsafe_code"] is True
    assert by["adler2"]["unsafe_blocks"] == 0 and by["adler2"]["version"] == "1.0.0"


def test_geiger_failure_is_recorded_as_gap():
    counts, gaps = u.geiger_counts("mox", runner=lambda cmd: (1, "", "error: no lockfile\n"))
    assert counts == {}
    assert len(gaps) == 1
    assert set(gaps[0]) == {"tool", "version", "command", "error"}
    assert gaps[0]["tool"] == "cargo-geiger" and "no lockfile" in gaps[0]["error"]
    _, gaps2 = u.geiger_counts("mox", runner=lambda cmd: (0, "garbage", ""))
    assert gaps2 and gaps2[0]["tool"] == "cargo-geiger"


def test_geiger_output_is_parsed_past_cargo_noise():
    pkg = {
        "package": {"id": {"name": "miniz_oxide", "version": "0.9.1"}},
        "unsafety": {
            "used": {"exprs": {"safe": 5, "unsafe_": 3}},
            "unused": {"exprs": {"safe": 1, "unsafe_": 7}},
        },
    }
    out = json.dumps({"packages": [pkg]}) + '\n{"$message_type":"artifact"}\n'
    counts, gaps = u.geiger_counts("mox", runner=lambda cmd: (0, out, ""))
    assert gaps == [] and counts == {"miniz_oxide": (3, 7)}


def test_c_subjects_get_language_note():
    for s in ("zlib", "zng", "zsys"):
        (row,) = u.scan_subject(s)
        assert row["note"] == "C: entire codebase memory-unsafe by language"
        assert row.get("unsafe_blocks") is None and row["role"] == "subject"


def test_table_and_lock_status_come_from_the_latest_raw(tmp_path, monkeypatch):
    from cfbench import paths, provenance

    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    u.derive_table()
    assert provenance.read_table("unsafe")[1]["pending"] == u.PENDING
    assert u.status_from_latest_raw("cf") is None
    row = {"subject": "cf", "crate": "cleanflate", "version": "0.1.0", "role": "subject",
           "forbid_unsafe_code": True, "deny_unsafe_code": False, "unsafe_blocks": 0, "unsafe_fns": 0,
           "unsafe_impls": 0, "unsafe_traits": 0, "target_feature_attrs": 0, "geiger_used": 0,
           "geiger_unused": 0, "note": ""}  # fmt: skip
    u.rawio.write_raw("size", {"kind": "unsafe", "rows": [row], "tool_gaps": []}, machine="any",
                      profile="full", script="t", environment=None)  # fmt: skip
    u.derive_table()
    rows, side = provenance.read_table("unsafe")
    assert side["pending"] is None and rows[0]["crate"] == "cleanflate"
    st = u.status_from_latest_raw("cf")
    assert (
        st["forbid_unsafe_code"] is True
        and st["unsafe_blocks"] == 0
        and st["roots"] == ["cleanflate"]
    )
