from pathlib import Path

from cfbench import loc, paths, provenance, rawio

DOC = {
    "Rust": {"blanks": 10, "code": 100, "comments": 20,
             "reports": [{"name": "a.rs"}, {"name": "b.rs"}],
             "children": {"Markdown": [{"name": "a.rs", "stats": {"code": 3, "comments": 0, "blanks": 1}},
                                       {"name": "b.rs", "stats": {"code": 2, "comments": 0, "blanks": 0}}]}},
    "Markdown": {"blanks": 1, "code": 5, "comments": 0, "reports": [{"name": "c.md"}], "children": {}},
    "Total": {"blanks": 11, "code": 105, "comments": 20, "reports": [], "children": {}},
}  # fmt: skip


def test_tokei_json_parsed_per_language():
    got = loc.parse_tokei(DOC)
    assert got["Rust"] == {"files": 2, "code": 100, "comments": 20, "blanks": 10}
    assert got["Markdown"]["files"] == 1
    assert got["Markdown (embedded)"] == {"files": 0, "code": 5, "comments": 0, "blanks": 1}
    assert got[loc.TOTAL] == {"files": 3, "code": 105, "comments": 20, "blanks": 11}
    rows = loc.table_rows({"subjects": {"cf": {"files": [], "languages": got}}})
    assert [r["language"] for r in rows] == [
        "Markdown",
        "Markdown (embedded)",
        "Rust",
        "Total",
    ]  # totals row last
    assert rows[-1]["subject"] == "cf" and list(rows[0]) == loc.COLUMNS


def test_only_manifest_files_are_counted(tmp_path, monkeypatch):
    manifest = {
        s: [tmp_path / f"{s}-1.c", tmp_path / f"{s}-2.c"] for s in loc.decomp_paths.SUBJECTS
    }
    monkeypatch.setattr(loc.decomp_paths, "files", lambda s: manifest[s])
    calls = []

    def runner(argv):
        calls.append(argv)
        return DOC

    payload = loc.collect("/bin/tokei", runner)
    assert len(calls) == len(manifest)
    for argv, s in zip(calls, loc.decomp_paths.SUBJECTS, strict=True):
        assert argv[:4] == ["/bin/tokei", "--no-ignore", "--output", "json"]
        assert argv[4:] == [str(p) for p in manifest[s]]  # nothing but the manifest files
    assert payload["subjects"]["cf"]["files"] == [
        str(tmp_path / "cf-1.c"),
        str(tmp_path / "cf-2.c"),
    ]


def test_derive_pending_then_table(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    loc.derive_table()
    assert provenance.read_table("loc")[1]["pending"] == loc.PENDING
    payload = {
        "kind": "loc",
        "subjects": {"cf": {"files": ["x"], "languages": loc.parse_tokei(DOC)}},
    }
    rawio.write_raw("size", payload, machine="any", profile="full", script="s", environment=None)
    loc.derive_table()
    rows, side = provenance.read_table("loc")
    assert side["pending"] is None and rows[-1]["language"] == "Total" and rows[-1]["code"] == "105"
    assert isinstance(tmp_path, Path)
