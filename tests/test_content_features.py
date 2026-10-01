import json

import pytest

from cfbench import config, paths, provenance, rawio, workloads
from cfbench.content import features, infgen
from cfbench.workloads import Workload

CFG = config.load_config("full")


def fake_stats(path, framing):
    return {
        "literals": 10,
        "matches": 10,
        "mean_match_len": 5.0,
        "literal_fraction": 0.2,
        "dist1_fraction": 0.1,
        "dist2_7_fraction": 0.2,
        "overlap_fraction": 0.3,
        "blocks": {"stored": 0, "fixed": 1, "dynamic": 2},
        "ratio": 0.4,
        "match_len_hist": dict.fromkeys(infgen.LEN_BINS, 1),
        "match_dist_hist": dict.fromkeys(infgen.DIST_BINS, 2),
    }


@pytest.fixture
def env_(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    (tmp_path / "data" / "manifests").mkdir(parents=True)
    entries, wls = [], []
    for fr in CFG["perf"]["framings"]:
        for lv in CFG["perf"]["levels"]:
            for corpus in ("silesia", "tiny"):
                p = tmp_path / f"{corpus}-{lv}.{fr}"
                p.write_bytes(b"x")
                wls.append(Workload(f"{corpus}/x", corpus, "x", lv, fr, p, p, 100, 40))
                entries.append({"id": f"{corpus}/x", "level": lv, "framing": fr, "len": 40})
    (tmp_path / "data" / "manifests" / "workloads.json").write_text(
        json.dumps({"entries": entries})
    )
    monkeypatch.setattr(workloads, "list_workloads", lambda cfg: wls)
    return tmp_path


def run(monkeypatch):
    payload = features.analyse(CFG, stats_fn=fake_stats)
    monkeypatch.setattr(features.infgen, "stats", fake_stats)
    rawio.write_raw("content", payload, machine="any", profile="full", script="s", environment=None)
    return features.derive(CFG), payload


def test_one_row_per_workload_level_framing(env_, monkeypatch):
    rows, payload = run(monkeypatch)
    n_levels, framings = len(CFG["perf"]["levels"]), CFG["perf"]["framings"]
    assert len(rows) == n_levels * len(framings)  # one corpus workload, tiny excluded
    keys = {(r["workload"], r["level"], r["framing"]) for r in rows}
    assert len(keys) == len(rows)
    assert {r["framing_analysed"] for r in rows} == {"raw"}
    assert {r["corpus"] for r in rows} == {"silesia"}
    assert len(payload["workload_manifest_sha256"]) == 64
    assert provenance.read_table("content_features")[1]["pending"] is None


def test_histogram_columns_present(env_, monkeypatch):
    rows, _ = run(monkeypatch)
    cols = list(provenance.read_table("content_features")[0][0])
    assert cols == features.COLUMNS
    assert len(features.LEN_COLS) == len(infgen.LEN_BINS)
    assert len(features.DIST_COLS) == len(infgen.DIST_BINS)
    assert rows[0]["len_frac_3"] == pytest.approx(0.1)
    assert rows[0]["dist_frac_65_512"] == pytest.approx(0.2)
    assert rows[0]["mean_match_len"] == 5.0


def test_no_data_is_pending(env_):
    assert features.derive(CFG) == []
    assert provenance.read_table("content_features")[1]["pending"] == features.PENDING
