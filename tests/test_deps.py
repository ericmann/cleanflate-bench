import json

from cfbench import deps, paths, provenance

TREE = """\
0demo v0.1.0 (/x)
1alpha v1.2.0
2beta v0.3.1
2gamma v2.0.0
3beta v0.3.1 (*)
1delta v0.9.0 (proc-macro)
"""


def test_cargo_tree_depth_output_is_parsed():
    t = deps.parse_tree(TREE)
    assert t["direct"] == ["alpha@1.2.0", "delta@0.9.0"]
    assert t["transitive"] == ["alpha@1.2.0", "beta@0.3.1", "delta@0.9.0", "gamma@2.0.0"]
    assert deps.parse_tree("0solo v1.0.0\n") == {"direct": [], "transitive": []}


AUDIT = {
    "database": {"advisory-count": 3},
    "vulnerabilities": {
        "found": True,
        "list": [
            {
                "advisory": {"id": "RUSTSEC-0001", "title": "bad"},
                "package": {"name": "beta", "version": "0.3.1"},
            },
            {
                "advisory": {"id": "RUSTSEC-0002", "title": "elsewhere"},
                "package": {"name": "other", "version": "1.0.0"},
            },
        ],
    },
    "warnings": {
        "unmaintained": [
            {"kind": "unmaintained", "package": {"name": "alpha", "version": "1.2.0"},
             "advisory": {"id": "RUSTSEC-0003", "title": "old"}},
            {"kind": "unmaintained", "package": {"name": "alpha", "version": "0.1.0"},
             "advisory": {"id": "RUSTSEC-0004", "title": "other version"}},
        ]
    },
}  # fmt: skip


def test_advisories_filtered_to_subject_dependency_set():
    advisories = deps.parse_audit(AUDIT)
    assert {a["id"] for a in advisories} == {
        "RUSTSEC-0001",
        "RUSTSEC-0002",
        "RUSTSEC-0003",
        "RUSTSEC-0004",
    }
    dep_set = set(deps.parse_tree(TREE)["transitive"]) | {"demo@0.1.0"}
    hits = deps.filter_advisories(advisories, dep_set)
    assert [a["id"] for a in hits] == ["RUSTSEC-0003", "RUSTSEC-0001"]  # sorted by package
    assert {a["kind"] for a in hits} == {"unmaintained", "vulnerability"}


def test_audit_failure_is_recorded_as_gap():
    advisories, db, gaps = deps.run_audit(lambda cmd: (1, "", "error: could not fetch advisory db"))
    assert advisories is None and db == {}
    assert len(gaps) == 1 and gaps[0]["tool"] == "cargo-audit"
    assert set(gaps[0]) == {"tool", "version", "command", "error"}
    assert "advisory db" in gaps[0]["error"]
    ok, db, gaps = deps.run_audit(lambda cmd: (1, json.dumps(AUDIT), ""))  # exit 1 = found
    assert ok and not gaps and db == {"advisory-count": 3}


def fake_runner(cmd):
    name = cmd[cmd.index("-p") + 1].split("@")[0]
    trees = {"cleanflate": "0cleanflate v0.1.0\n", "libz-rs-sys": "0libz-rs-sys v0.6.8\n1zlib-rs v0.6.8\n",
             "zlib-rs": "0zlib-rs v0.6.8\n", "miniz_oxide": "0miniz_oxide v0.9.1\n1adler2 v2.0.1\n"}  # fmt: skip
    return 0, trees[name], ""


META = {
    "packages": [
        {"name": n, "version": v}
        for n, v in [("cleanflate", "0.1.0"), ("libz-rs-sys", "0.6.8"), ("zlib-rs", "0.6.8"),
                     ("miniz_oxide", "0.9.1")]
    ]
}  # fmt: skip


def test_collect_reports_what_is_found_including_zero_deps_and_gaps():
    payload = deps.collect(META, runner=fake_runner, audit_runner=lambda c: (2, "", "no network"))
    rows = {r["package"]: r for r in payload["rows"]}
    assert (
        rows["cleanflate@0.1.0"]["direct_count"] == 0
        and rows["cleanflate@0.1.0"]["transitive_count"] == 0
    )
    assert rows["miniz_oxide@0.9.1"]["direct"] == "adler2@2.0.1"
    assert rows["libz-rs-sys@0.6.8"]["transitive"] == "zlib-rs@0.6.8"
    assert all(r["advisories"] is None and "tool gap" in r["note"] for r in rows.values())
    assert payload["tool_gaps"]
    ok = deps.collect(META, runner=fake_runner, audit_runner=lambda c: (0, json.dumps(AUDIT), ""))
    assert all(r["advisories"] == "" for r in ok["rows"])  # none of the advisories hit a subject


def test_derive_table_pending_then_filled(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    deps.derive_table()
    assert provenance.read_table("deps")[1]["pending"] == deps.PENDING
    payload = deps.collect(
        META, runner=fake_runner, audit_runner=lambda c: (0, json.dumps(AUDIT), "")
    )
    deps.rawio.write_raw(
        "size", payload, machine="any", profile="full", script="t", environment=None
    )
    deps.derive_table()
    rows, side = provenance.read_table("deps")
    assert side["pending"] is None and len(rows) == 4
    assert [r["subject"] for r in rows] == ["cf", "mox", "zrs", "zrs"]
