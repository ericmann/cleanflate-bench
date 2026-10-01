import copy
import hashlib
import json
import sys
import zlib

import pytest

from cfbench import bombs, config, paths, provenance, rawio

CFG = copy.deepcopy(config.load_config("full"))


def small_cfg():
    cfg = copy.deepcopy(CFG)
    cfg["bomb"].update(output_sizes=[1024, 65536], nested_layers=2, output_limit_bytes=4096)
    return cfg


def test_ratio_computation_and_nested_overall_ratio(tmp_path):
    assert bombs.ratio(1000, 10) == 100.0 and bombs.ratio(5, 0) is None
    cases = bombs.generate(small_cfg(), tmp_path)
    zeros = [c for c in cases if c["layer"] is None]
    nested = [c for c in cases if c["layer"] is not None]
    assert [c["output_bytes"] for c in zeros] == [1024, 65536]
    assert zlib.decompress(zeros[1]["path"].read_bytes()) == bytes(65536)
    outer = nested[-1]
    overall = 65536 / outer["compressed_bytes"]
    assert all(c["overall_ratio"] == pytest.approx(overall) for c in nested)
    # layer 1 inflates to the zeros, layer 2 inflates to the stored layer 1
    assert zlib.decompress(nested[0]["path"].read_bytes(), 31) == bytes(65536)
    inner = zlib.decompress(outer["path"].read_bytes(), 31)
    assert inner == nested[0]["path"].read_bytes()
    assert outer["inner_sha256"] == hashlib.sha256(inner).hexdigest()
    assert outer["output_bytes"] == len(inner)
    # deterministic: a second call reuses the files and reports the same sizes
    again = bombs.generate(small_cfg(), tmp_path)
    assert [c["compressed_bytes"] for c in again] == [c["compressed_bytes"] for c in cases]


def test_overall_ratio_beyond_one_layer_limit():
    # one DEFLATE layer cannot exceed ~1032:1; the second gzip layer multiplies that
    one = len(zlib.compress(bytes(1 << 22), 9))
    two = len(zlib.compress(zlib.compress(bytes(1 << 22), 9), 9))
    assert (1 << 22) / one < 1100 and (1 << 22) / two > (1 << 22) / one


def test_ru_maxrss_normalized_per_platform():
    assert bombs.rss_bytes(2048, "linux") == 2048 * 1024
    assert bombs.rss_bytes(2048, "darwin") == 2048
    child = bombs.run_child([sys.executable, "-c", "import json;print(json.dumps({'ok':True}))"])
    assert child["result"] == {"ok": True} and child["seconds"] > 0
    assert child["peak_rss_bytes"] > 1_000_000  # a Python interpreter is at least a few MiB


def test_limit_enforcement_taken_from_info_caps(tmp_path, monkeypatch):
    cfg = small_cfg()
    cfg["bomb"]["subjects"] = ["cf", "zlib", "mox"]
    cases = bombs.generate(cfg, tmp_path)
    infos = {
        "cf": {"output_limit": "native", "framings": ["raw", "zlib", "gzip"]},
        "zlib": {"output_limit": "caller", "framings": ["raw", "zlib", "gzip"]},
        "mox": {"output_limit": "caller", "framings": ["raw", "zlib"]},
    }
    monkeypatch.setattr(bombs.subjects, "command", lambda s: [s])
    monkeypatch.setattr(
        bombs.subprocess, "run",
        lambda argv, **k: type("R", (), {"stdout": json.dumps(infos[argv[0]])})(),
    )  # fmt: skip
    seen = []

    def runner(argv):
        seen.append(argv)
        assert "--max-output" in argv and argv[argv.index("--max-output") + 1] == "4096"
        src = argv[argv.index("--input") + 1]
        limit = "zeros-65536" in src or "nested-1-" in src
        return {"result": {"ok": True, "limit_hit": limit, "produced": 4096 if limit else 1024,
                           "sha256": "x"}, "seconds": 0.5, "peak_rss_bytes": 123}  # fmt: skip

    rows = bombs.run_all(cfg, cases, "M-T", runner)
    by = {(r["subject"], r["case"]): r for r in rows}
    assert {r["limit_enforcement"] for r in rows if r["subject"] == "cf"} == {"native"}
    assert {r["limit_enforcement"] for r in rows if r["subject"] in ("zlib", "mox")} == {"caller"}
    assert by[("mox", "nested-2x-65536:layer1")]["outcome"] == "unsupported"  # no gzip
    assert (
        by[("cf", "zeros-65536")]["outcome"] == "limit"
        and by[("cf", "zeros-1024")]["outcome"] == "ok"
    )
    assert (
        by[("cf", "nested-2x-65536:layer2")]["outcome"] == "output-mismatch"
    )  # runner's sha is fake
    assert (
        by[("cf", "nested-2x-65536:layer1")]["overall_ratio"]
        == by[("cf", "nested-2x-65536:layer2")]["overall_ratio"]
    )
    assert len(seen) == 3 * 4 - 2


def test_derive_pending_then_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    bombs.derive()
    assert provenance.read_table("bombs")[1]["pending"] == bombs.PENDING
    row = dict.fromkeys(bombs.COLUMNS, "")
    row.update(machine="M-T", subject="cf", case="c", outcome="ok")
    rawio.write_raw(
        "correctness",
        {"kind": "bombs", "rows": [row]},
        machine="M-T",
        profile="full",
        script="s",
        environment=None,
    )
    bombs.derive()
    rows, side = provenance.read_table("bombs")
    assert side["pending"] is None and rows[0]["subject"] == "cf"


def test_layer_rows_carry_layer_and_overall_ratio(tmp_path, monkeypatch):
    cfg = small_cfg()
    cfg["bomb"]["subjects"] = ["cf"]
    cases = bombs.generate(cfg, tmp_path)
    monkeypatch.setattr(bombs.subjects, "command", lambda s: [s])
    monkeypatch.setattr(
        bombs.subprocess,
        "run",
        lambda argv, **k: type(
            "R",
            (),
            {"stdout": json.dumps({"output_limit": "native", "framings": ["raw", "zlib", "gzip"]})},
        )(),
    )

    def runner(argv):
        return {"result": {"ok": True, "limit_hit": False, "produced": 1, "sha256": "x"},
                "seconds": 0.1, "peak_rss_bytes": 1}  # fmt: skip

    rows = bombs.run_all(cfg, cases, "M-T", runner)
    by = {r["case"]: r for r in rows}
    layer2 = by["nested-2x-65536:layer2"]
    c2 = next(c for c in cases if c["layer"] == 2)
    assert layer2["ratio"] == pytest.approx(c2["output_bytes"] / c2["compressed_bytes"])
    assert layer2["ratio"] != pytest.approx(layer2["overall_ratio"])
    assert layer2["overall_ratio"] == pytest.approx(65536 / c2["compressed_bytes"])
    assert by["zeros-1024"]["overall_ratio"] is None
    assert by["zeros-65536"]["overall_ratio"] is None
