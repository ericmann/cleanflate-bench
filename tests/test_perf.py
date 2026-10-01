import json
import sys
from pathlib import Path

import pytest

from cfbench import config, paths, perf, rawio, workloads
from cfbench.workloads import Workload

FAKE = str(Path(__file__).parent / "fixtures" / "fake_subject.py")


def wl(wid="canterbury/a", level=6, framing="raw", corpus="canterbury"):
    d = paths.DATA / "workloads" / wid
    return Workload(
        wid,
        corpus,
        wid.split("/")[-1],
        level,
        framing,
        d / "orig",
        d / f"l{level}.{framing}",
        20,
        None,
    )


def infos(**framings):
    base = {"modes": ["oneshot", "stream"], "framings": ["raw", "zlib", "gzip"]}
    return {s: {**base, "framings": f} if f else dict(base) for s, f in framings.items()}


def test_build_cells_marks_unsupported_framings():
    cfg = config.load_config("full")
    wls = [wl(framing="raw"), wl(framing="gzip")]
    cells = perf.build_cells(cfg, infos(cf=None, mox=["raw", "zlib"]), wls)
    mox_gzip = [c for c in cells if c["subject"] == "mox" and c["framing"] == "gzip"]
    assert mox_gzip and all(c["status"] == "unsupported" for c in mox_gzip)
    assert all("status" not in c for c in cells if c["subject"] == "cf")
    assert all("status" not in c for c in cells if c["subject"] == "mox" and c["framing"] == "raw")
    assert len(cells) == 2 * 2 * len(cfg["perf"]["modes"])


def test_oneshot_only_subject_gets_stream_cells_marked_unsupported():
    cfg = config.load_config("full")
    info = {"zlib": {"modes": ["oneshot"], "framings": ["raw"]}}
    cells = perf.build_cells(cfg, info, [wl()])
    status = {c["mode"]: c.get("status") for c in cells}
    assert status == {"oneshot": None, "stream_small": "unsupported", "stream_large": "unsupported"}


def test_stream_modes_use_config_chunk_sizes():
    cfg = config.load_config("full")
    cells = perf.build_cells(cfg, infos(cf=None), [wl()])
    by_mode = {c["mode"]: (c["in_chunk"], c["out_chunk"]) for c in cells}
    p = cfg["perf"]
    assert by_mode["oneshot"] == (0, 0)
    assert by_mode["stream_small"] == (p["small_in_chunk"], p["small_out_chunk"])
    assert by_mode["stream_large"] == (p["large_in_chunk"], p["large_out_chunk"])


def test_native_variant_labels_subjects_and_adds_zlib_baseline():
    cfg = config.load_config("full")
    assert perf.session_labels(cfg, "native") == ["cf@native", "zrs@native", "mox@native", "zlib"]
    assert perf.session_labels(cfg, "generic") == cfg["perf"]["subjects"]
    infos_ = infos(**{"cf@native": None, "zrs@native": None, "zlib": None, "zng": None, "cf": None})
    cells = perf.build_cells(cfg, infos_, [wl()], "native")
    assert {c["subject"] for c in cells} == {"cf@native", "zrs@native", "zlib"}


def test_shuffle_is_deterministic_per_seed_and_differs_between_runs():
    cells = [{"i": i} for i in range(50)]
    a1 = perf.shuffled(cells, 7, 1)
    assert a1 == perf.shuffled(cells, 7, 1)
    assert a1 != perf.shuffled(cells, 7, 2)
    assert a1 != perf.shuffled(cells, 8, 1)
    assert sorted(c["i"] for c in a1) == list(range(50))
    assert cells == [{"i": i} for i in range(50)]  # input untouched


def test_preconditions_warn_on_powersave_governor():
    cfg = config.load_config("full")
    w = perf.check_preconditions(
        {"governor": "powersave", "load_avg_start": [0.1, 0, 0]}, cfg, "Linux"
    )
    assert len(w) == 1 and "powersave" in w[0]
    assert (
        perf.check_preconditions({"governor": "performance", "load_avg_start": [0.1]}, cfg, "Linux")
        == []
    )
    busy = perf.check_preconditions({"governor": None, "load_avg_start": [9.0]}, cfg, "Linux")
    assert "load average" in busy[0]
    mac = perf.check_preconditions(
        {"power": {"on_ac": False, "low_power_mode": True}, "load_avg_start": [0.0]}, cfg, "Darwin"
    )
    assert len(mac) == 2


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "SMOKE", tmp_path / "smoke")
    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    monkeypatch.setenv("CFB_MACHINE", "M-T")
    wls = [wl("canterbury/a", framing="raw"), wl("canterbury/a", framing="gzip")]
    for w in wls:
        w.orig_path.parent.mkdir(parents=True, exist_ok=True)
        w.path.write_bytes(b"x")
        w.orig_path.write_bytes(b"y")
    monkeypatch.setattr(workloads, "list_workloads", lambda cfg: wls)
    cmd = {
        "cf": [sys.executable, FAKE],
        "mox": [sys.executable, FAKE, "--framings", "raw,zlib"],
        "zlib": [sys.executable, FAKE, "--fail"],
    }
    monkeypatch.setenv("CFB_SUBJECT_CMD", json.dumps(cmd))
    return wls


def test_run_writes_one_raw_per_run_with_shared_session(fake_env):
    cfg = config.load_config("full")
    cfg["perf"]["min_samples"] = 4
    out = perf.run(cfg, ["cf", "mox", "zlib"], profile="full", session="S1")
    assert len(out) == cfg["perf"]["runs"]
    docs = [rawio.load_raw(p) for p in out]
    assert {d["session"] for d in docs} == {"S1"}
    assert [d["run_index"] for d in docs] == list(range(1, cfg["perf"]["runs"] + 1))
    first, second = docs[0]["payload"], docs[1]["payload"]
    assert first["kind"] == "perf" and first["variant"] == "generic"
    assert set(first["subjects"]) == {"cf", "mox", "zlib"}
    ran = lambda p: [c for c in p["cells"] if c.get("status") != "unsupported"]
    order = lambda p: [c["order_index"] for c in ran(p)]
    assert sorted(order(first)) == list(range(len(ran(first))))
    keyed = lambda p: [(c["subject"], c["workload"], c["framing"], c["mode"]) for c in ran(p)]
    assert keyed(first) == keyed(second)  # stored sorted, order recorded separately
    assert order(first) != order(second)
    mox_gzip = [c for c in first["cells"] if c["subject"] == "mox" and c["framing"] == "gzip"]
    assert mox_gzip and all(c["status"] == "unsupported" and c["result"] is None for c in mox_gzip)
    cf = [c for c in ran(first) if c["subject"] == "cf"]
    assert all(c["result"]["ok"] and len(c["result"]["samples_ns"]) == 4 for c in cf)
    broken = [c for c in ran(first) if c["subject"] == "zlib"]
    assert broken and all(not c["result"]["ok"] for c in broken)
    assert "harness failure" in broken[0]["result"]["error"]
    assert "environment_end" in first and "preconditions" in first
    assert docs[0]["environment"]["machine"] == "M-T"


def test_quick_profile_writes_to_smoke(fake_env, tmp_path):
    cfg = config.load_config("quick")
    out = perf.run(cfg, ["cf"], profile="quick")
    assert all(str(tmp_path / "smoke") in str(p) for p in out)


def test_strict_refuses_on_precondition_warnings(fake_env, monkeypatch):
    cfg = config.load_config("full")
    monkeypatch.setattr(perf, "check_preconditions", lambda e, c, s=None: ["noisy"])
    with pytest.raises(RuntimeError, match="noisy"):
        perf.run(cfg, ["cf"], profile="full", strict=True)
    assert perf.run(cfg, ["cf"], profile="full", strict=False)


def test_missing_workloads_are_reported(fake_env):
    fake_env[0].path.unlink()
    with pytest.raises(RuntimeError, match="make workloads"):
        perf.run(config.load_config("full"), ["cf"], profile="full")


def test_native_run_records_labelled_subjects_and_generic_baseline(fake_env, monkeypatch):
    fake = [sys.executable, FAKE]
    monkeypatch.setenv(
        "CFB_SUBJECT_CMD", json.dumps({s: fake for s in ("cf", "zrs", "mox", "zlib")})
    )
    cfg = config.load_config("full")
    cfg["perf"]["min_samples"] = 3
    seen = []

    def runner(argv, path):
        seen.append(argv)
        return perf.exec_cell(argv, path)

    out = perf.run(cfg, ["cf", "zrs", "mox"], variant="native", profile="full", runner=runner)
    payload = rawio.load_raw(out[0])["payload"]
    assert payload["variant"] == "native" and payload["build"] == "native"
    assert set(payload["subjects"]) == {"cf@native", "zrs@native", "mox@native", "zlib"}
    assert {c["subject"] for c in payload["cells"]} == set(payload["subjects"])
