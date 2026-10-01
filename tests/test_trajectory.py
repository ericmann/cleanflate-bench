import json
import sys
from pathlib import Path

import pytest

from cfbench import config, paths, perf_report, provenance, rawio, trajectory, workloads
from cfbench.workloads import Workload

FAKE = str(Path(__file__).parent / "fixtures" / "fake_subject.py")


def make_workloads(tmp):
    wls = []
    for corpus, name in (("silesia", "xml"), ("canterbury", "alice29.txt")):
        for framing in ("raw", "gzip"):
            d = tmp / "workloads" / corpus / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "orig").write_bytes(b"y")
            (d / f"l6.{framing}").write_bytes(b"x")
            wls.append(
                Workload(
                    f"{corpus}/{name}",
                    corpus,
                    name,
                    6,
                    framing,
                    d / "orig",
                    d / f"l6.{framing}",
                    1,
                    1,
                )
            )
    return wls


@pytest.fixture
def env_(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "SMOKE", tmp_path / "smoke")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setenv("CFB_MACHINE", "M-T")
    wls = make_workloads(tmp_path)
    monkeypatch.setattr(workloads, "list_workloads", lambda cfg: wls)
    fake = [sys.executable, FAKE]
    monkeypatch.setenv(
        "CFB_SUBJECT_CMD", json.dumps({s: fake for s in ("cf-r1", "cf-r2", "cf-r3", "zlib")})
    )
    return tmp_path


def cfg_small():
    cfg = config.load_config("full")
    cfg["perf"]["min_samples"] = 3
    cfg["trajectory"]["levels"] = [6]
    cfg["trajectory"]["modes"] = ["oneshot"]
    return cfg


def test_rounds_and_zlib_share_one_session(env_):
    out = trajectory.run(cfg_small(), profile="full", session="S")
    assert len(out) == 1  # trajectory.runs = 1
    docs = [rawio.load_raw(p) for p in out]
    assert all("/trajectory/" in str(p) for p in out)
    assert {d["session"] for d in docs} == {"S"}
    payload = docs[0]["payload"]
    assert payload["kind"] == "trajectory" and payload["variant"] == "rounds"
    assert set(payload["subjects"]) == {"cf-r1", "cf-r2", "cf-r3", "zlib"}
    assert {c["subject"] for c in payload["cells"]} == {"cf-r1", "cf-r2", "cf-r3", "zlib"}
    assert {c["mode"] for c in payload["cells"]} == {"oneshot"}  # trajectory.modes, not perf.modes
    assert rawio.list_raw("perf") == []  # the perf category is untouched


def agg(subject, ratio, round_ok=True, corpus="silesia", framing="raw", mode="oneshot", level=6):
    return {"machine": "M-T", "subject": subject, "corpus": corpus, "framing": framing, "mode": mode,
            "level": level, "agg_mib_s": 100.0 * (ratio or 1), "ratio_vs_zlib": ratio, "complete": round_ok}  # fmt: skip


def test_ratio_uses_same_session_zlib(env_):
    mib = 1 << 20

    def row(subject, ns, variant="rounds", workload="silesia/a"):
        r = {"machine": "M-T", "variant": variant, "subject": subject, "corpus": "silesia", "workload": workload,
             "level": 6, "framing": "raw", "mode": "oneshot", "status": "ok", "output_bytes": mib,
             "median_mib_s": mib / (ns / 1e9) / mib, "_median_ns": ns, "_best_ns": ns}  # fmt: skip
        return r

    rows = [row("zlib", 1e9), row("cf-r1", 4e9), row("cf-r2", 2e9), row("cf-r3", 1.25e9)]
    perf_report.add_ratios(rows)
    table = trajectory.table_rows(perf_report.aggregates(rows), trajectory.round_info())
    got = {r["round"]: r["ratio_vs_zlib"] for r in table}
    assert got == pytest.approx({1: 0.25, 2: 0.5, 3: 0.8})
    # a zlib cell from a different variant (another session) is never used as the baseline
    other = [row("cf-r1", 4e9), row("zlib", 1e9, variant="generic")]
    perf_report.add_ratios(other)
    assert other[0]["ratio_vs_zlib"] is None
    only = [a for a in perf_report.aggregates(other) if a["subject"] == "cf-r1"]
    assert len(only) == 1 and only[0]["ratio_vs_zlib"] is None
    # and the real derivation path reads the trajectory category with the rounds variant
    cfg = cfg_small()
    trajectory.run(cfg, profile="full", session="S")
    loaded, _ = perf_report.compute_rows(cfg, "trajectory", "trajectory")
    assert {r["variant"] for r in loaded} == {"rounds"}


def test_table_has_one_row_per_round_corpus_framing_mode_level(env_):
    cfg = cfg_small()
    trajectory.run(cfg, profile="full", session="S")
    table = trajectory.derive(cfg, out_dir=env_ / "figs")
    keys = [(r["round"], r["corpus"], r["framing"], r["mode"], r["level"]) for r in table]
    assert len(keys) == len(set(keys)) == 3 * 2 * 2 * 1 * 1  # rounds x corpora x framings
    assert {r["round"] for r in table} == {1, 2, 3}
    info = trajectory.round_info()
    for r in table:
        assert r["tag"] == info[r["round"]]["tag"] and r["sha"] == info[r["round"]]["sha"]
    assert all(r["complete"] is True for r in table)
    rows, side = provenance.read_table("trajectory")
    assert len(rows) == 12 and side["pending"] is None
    assert list(rows[0]) == trajectory.COLUMNS
    assert (env_ / "figs" / "trajectory_M-T.svg").exists() and (
        env_ / "figs" / "trajectory_M-T.png"
    ).exists()


def test_table_excludes_the_zlib_baseline_row():
    aggs = [agg("zlib", 1.0), agg("cf-r1", 0.5), agg("cf-r2", 0.7), agg("cf-r3", 0.9)]
    table = trajectory.table_rows(aggs, trajectory.round_info())
    assert [r["round"] for r in table] == [1, 2, 3]
    series = trajectory.figure_series(table, "M-T")
    assert series == {"silesia raw": [(1, 0.5), (2, 0.7), (3, 0.9)]}
    assert trajectory.figure_series(table, "M-X") == {}


def test_no_data_is_pending(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(paths, "RAW", tmp_path / "none")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    assert trajectory.derive(config.load_config("full"), out_dir=tmp_path / "figs") == []
    rows, side = provenance.read_table("trajectory")
    assert rows == [] and side["pending"] == trajectory.PENDING
    assert not (tmp_path / "figs").exists()
    assert "pending" in capsys.readouterr().out
