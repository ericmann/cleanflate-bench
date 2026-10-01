import pytest

from cfbench import paths, rawio


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "SMOKE", tmp_path / "smoke")
    return tmp_path


def _w(profile, **kw):
    return rawio.write_raw(
        "perf",
        kw.pop("payload", {"kind": "x"}),
        machine="M-B",
        profile=profile,
        script="t",
        environment={"a": 1},
        **kw,
    )


def test_full_profile_writes_under_data_raw(dirs):
    p = _w("full")
    assert p.parent == dirs / "raw" / "perf" / "M-B"
    doc = rawio.load_raw(p)
    assert doc["schema"] == "cfbench.raw/1"
    assert doc["payload"] == {"kind": "x"}
    assert set(doc) >= {"bench_git", "argv", "environment", "session", "run_index", "script"}


def test_quick_profile_writes_under_data_smoke(dirs):
    p = _w("quick")
    assert p.parent == dirs / "smoke" / "perf" / "M-B"
    assert rawio.list_raw("perf", profile="quick") == [p]
    assert rawio.list_raw("perf", profile="full") == []


def test_timestamp_collision_gets_suffix(dirs, monkeypatch):
    monkeypatch.setattr(rawio, "utc_timestamp", lambda: "20260101T000000Z")
    a, b, c = _w("full"), _w("full"), _w("full")
    assert [x.name for x in (a, b, c)] == [
        "20260101T000000Z.json",
        "20260101T000000Z-1.json",
        "20260101T000000Z-2.json",
    ]


def test_latest_session_groups_by_session_and_orders_runs(dirs, monkeypatch):
    ts = iter(["20260101T000000Z", "20260101T000001Z", "20260102T000000Z", "20260102T000001Z"])
    monkeypatch.setattr(rawio, "utc_timestamp", lambda: next(ts))
    _w("full", session="s1", run_index=0)
    _w("full", session="s1", run_index=1)
    _w("full", session="s2", run_index=1)
    _w("full", session="s2", run_index=0)
    docs = rawio.latest_session("perf", "M-B")
    assert [(d["session"], d["run_index"]) for d in docs] == [("s2", 0), ("s2", 1)]
    assert len(rawio.list_raw("perf", machine="M-B", kind="x")) == 4
    assert rawio.list_raw("perf", machine="M-B", kind="y") == []
