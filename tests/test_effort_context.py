import json
from pathlib import Path

from cfbench import paths, provenance
from cfbench.effort import context as ctx

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "effort" / "github" / "responses.json").read_text()
)


def fake_fetch(url):
    r = FIX[url]  # a KeyError means the collector asked for a URL that was never recorded
    return r["headers"], json.dumps(r["body"])


def test_last_page_from_link_header():
    link = (
        '<https://api.github.com/repos/x/y/commits?per_page=1&page=2>; rel="next", '
        '<https://api.github.com/repos/x/y/commits?per_page=1&page=1083>; rel="last"'
    )
    assert ctx.last_page(link) == 1083
    assert ctx.last_page('<https://api.github.com/x?page=2&per_page=1>; rel="last"') == 2
    assert ctx.last_page('<https://api.github.com/x?page=2>; rel="next"') is None
    assert ctx.last_page(None) is None and ctx.last_page("") is None
    assert ctx.count_via_last_page(lambda u: ({}, "[1]"), "u") == 1  # no Link header: one page
    assert ctx.count_via_last_page(lambda u: ({}, "[]"), "u") == 0


def test_first_releases_extracted():
    p = ctx.collect(fake_fetch)
    assert p["kind"] == "context" and p["commit_count"] > 100 and p["contributor_count"] > 1
    assert p["first_commit"]["date"] <= p["repo_info"]["created_at"] or p["first_commit"]["sha"]
    rel = p["releases"]
    assert rel == sorted(rel, key=lambda r: r["published_at"]) and rel[0]["tag"].startswith("v")
    for name in ctx.CRATES:
        versions = p["crates"][name]
        assert versions == sorted(versions, key=lambda v: v["created_at"])
        assert versions[0]["num"] == "0.0.1"  # the first published version
    rows = {r["fact"]: r for r in ctx.table_rows(p, "20260101T000000Z")}
    assert rows["first_published_version_zlib-rs"]["value"].startswith("0.0.1 (2024-")
    assert rows["first_published_version_libz-rs-sys"]["value"].startswith("0.0.1")
    assert rows["commit_count"]["value"] == p["commit_count"]
    assert all(r["fetched_at"] == "20260101T000000Z" and r["source_url"] for r in rows.values())
    stable = rows["stable_1_0_release_zlib-rs"]["value"]
    versions = p["crates"]["zlib-rs"]
    if any(not v["num"].startswith("0.") for v in versions):
        assert "(" in stable  # a 1.x or later version exists
    else:
        assert stable.startswith("none: no 1.0")


def test_stable_release_statement_for_synthetic_histories():
    base = {
        "repo_info": {"created_at": "x"}, "first_commit": {"date": "d", "sha": "s"}, "commit_count": 1,
        "contributor_count": 1, "releases": [],
        "sources": {"repo": "r", "commits": "c", "contributors": "u", "releases": "l",
                    "crates": {"zlib-rs": "z", "libz-rs-sys": "s"}},
    }  # fmt: skip
    v = lambda num, at: {"num": num, "created_at": at, "yanked": False}
    only_zero = {
        **base,
        "crates": {"zlib-rs": [v("0.1.0", "a"), v("0.2.0", "b")], "libz-rs-sys": [v("0.1.0", "a")]},
    }
    rows = {r["fact"]: r["value"] for r in ctx.table_rows(only_zero, "t")}
    assert rows["stable_1_0_release_zlib-rs"].startswith("none")
    with_one = {
        **base,
        "crates": {"zlib-rs": [v("0.9.0", "a"), v("1.0.0", "c")], "libz-rs-sys": []},
    }
    rows = {r["fact"]: r["value"] for r in ctx.table_rows(with_one, "t")}
    assert rows["stable_1_0_release_zlib-rs"] == "1.0.0 (c)"
    assert rows["stable_1_0_release_libz-rs-sys"].startswith("none")


def test_scope_note_row_present(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    ctx.derive()
    rows, side = provenance.read_table("zlibrs_context")
    assert rows == [] and side["pending"] == ctx.PENDING
    rawio_path = ctx.rawio.write_raw(
        "effort",
        ctx.collect(fake_fetch),
        machine="any",
        profile="full",
        script="t",
        environment=None,
    )
    ctx.derive()
    rows, side = provenance.read_table("zlibrs_context")
    by = {r["fact"]: r for r in rows}
    note = by["scope_note"]["value"]
    for needle in ("not a head-to-head", "C ABI", "compression", "SIMD", "performance parity"):
        assert needle in note, needle
    assert side["pending"] is None and list(rows[0]) == ctx.COLUMNS
    assert by["scope_note"]["fetched_at"] == ctx.rawio.load_raw(rawio_path)["timestamp"]


def test_token_is_sent_only_to_github_and_never_stored(monkeypatch):
    seen = []

    class R:
        def __init__(self):
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def fake_open(req, timeout):
        seen.append((req.full_url, dict(req.header_items())))
        return R()

    monkeypatch.setattr(ctx, "open_url", fake_open)
    monkeypatch.setenv("GITHUB_TOKEN", "SECRET-TOKEN")
    ctx.http_fetch(f"{ctx.GITHUB}/repos/x/y")
    ctx.http_fetch(f"{ctx.CRATES_IO}/zlib-rs")
    gh, cr = seen
    assert (
        gh[1]["Authorization"] == "Bearer SECRET-TOKEN"
        and gh[1]["User-agent"] == "cleanflate-bench"
    )
    assert "Authorization" not in cr[1]
    assert "SECRET-TOKEN" not in json.dumps(ctx.collect(fake_fetch))
