import copy
import hashlib
import tarfile
from pathlib import Path

from cfbench import config, fuzzing, paths, rawio, workloads
from cfbench.workloads import Workload

FIX = Path(__file__).parent / "fixtures" / "fuzz"
CFG = config.load_config("full")


def test_libfuzzer_stats_parsed():
    fork = fuzzing.parse_libfuzzer((FIX / "fork_run.log").read_text())
    assert fork["executed"] == 129714 and fork["exec_per_s"] == 6663
    assert fork["cov"] == 681 and fork["ft"] == 1571 and fork["divergences"] == 0
    crash = fuzzing.parse_libfuzzer((FIX / "crash_excerpt.log").read_text())
    assert crash["executed"] == 4096  # stat:: line wins over the last progress line
    assert crash["divergences"] == 1
    assert crash["artifacts"] == ["/repo/fuzz/artifacts/diff_cf_zlib/crash-0a1b2c3d4e5f"]
    assert crash["cov"] == 455 and crash["exec_per_s"] == 4096
    empty = fuzzing.parse_libfuzzer("")
    assert empty["executed"] is None and empty["divergences"] == 0


def test_budget_split_across_jobs():
    assert fuzzing.seconds_per_job(CFG, "full") == 4 * 3600 // 4
    argv = fuzzing.run_argv("diff_cf_zrs", CFG, "full")
    assert argv[:6] == ["cargo", "+nightly", "fuzz", "run", "diff_cf_zrs", "--"]
    assert "-fork=4" in argv and "-max_total_time=3600" in argv and "-ignore_crashes=1" in argv
    assert f"-seed={CFG['fuzz']['seed']}" in argv
    two = copy.deepcopy(CFG)
    two["fuzz"].update(jobs=2, budget_cpu_hours=1)
    assert fuzzing.seconds_per_job(two, "full") == 1800
    quick = config.load_config("quick")
    assert quick["fuzz"]["jobs"] == 1
    assert fuzzing.seconds_per_job(quick, "quick") == quick["fuzz"]["smoke_seconds"]
    assert f"-max_total_time={quick['fuzz']['smoke_seconds']}" in fuzzing.run_argv(
        "diff_cf_zlib", quick, "quick"
    )
    assert "-fork=1" in fuzzing.run_argv("diff_cf_zlib", quick, "quick")


def test_seed_inputs_prefixed_with_framing_byte(tmp_path, monkeypatch):
    clone = tmp_path / "clone"
    mal = clone / "testdata" / "malformed"
    for d in ("rfc1950", "rfc1951", "rfc1952"):
        (mal / d).mkdir(parents=True)
    (mal / "rfc1951" / "b.bin").write_bytes(b"RAW")
    (mal / "rfc1952" / "g.bin").write_bytes(b"GZ")
    wl = []
    for fr in ("raw", "zlib", "gzip"):
        for lv in (1, 6):
            p = tmp_path / f"w_{fr}_{lv}"
            p.write_bytes(fr.encode())
            wl.append(Workload("silesia/x", "silesia", "x", lv, fr, p, p, 1, 1))
    monkeypatch.setattr(workloads, "list_workloads", lambda cfg: wl)
    corpus = tmp_path / "corpus"
    n = fuzzing.write_seeds(CFG, ["diff_cf_zlib", "diff_cf_mox"], corpus, clone)
    z = {p.name: p.read_bytes() for p in (corpus / "diff_cf_zlib").iterdir()}
    m = {p.name: p.read_bytes() for p in (corpus / "diff_cf_mox").iterdir()}
    assert z["wl_silesia_x_raw"] == b"\x00raw" and z["wl_silesia_x_zlib"] == b"\x01zlib"
    assert z["wl_silesia_x_gzip"] == b"\x02gzip" and z["mal_rfc1952_g.bin"] == b"\x02GZ"
    assert z["mal_rfc1951_b.bin"] == b"\x00RAW"
    assert len(z) == 5 and len(m) == 3 and "wl_silesia_x_gzip" not in m  # mox has no gzip
    assert n == 8 and not any(name.endswith("_1") for name in z)  # only level 6


def test_archive_recorded_with_sha256(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "SMOKE", tmp_path / "smoke")
    monkeypatch.setattr(fuzzing, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setenv("CFB_MACHINE", "M-T")
    (tmp_path / "fuzz" / "corpus" / "t").mkdir(parents=True)
    (tmp_path / "fuzz" / "corpus" / "t" / "a").write_bytes(b"1")
    (tmp_path / "fuzz" / "artifacts" / "t").mkdir(parents=True)
    (tmp_path / "fuzz" / "artifacts" / "t" / "crash-1").write_bytes(b"2")
    log = (FIX / "crash_excerpt.log").read_text()
    calls = []

    def runner(argv, **kw):
        calls.append(argv)
        return type("R", (), {"stdout": log, "stderr": "", "returncode": 0})()

    payload = fuzzing.run_target("t", CFG, "quick", runner)
    assert "cmin" in calls[1] and calls[0][4] == "t"
    arc = payload["archive"]
    path = tmp_path / arc["path"]
    assert (
        path.name.endswith("-fuzz-t.tar.gz")
        and path.parent == tmp_path / "smoke" / "correctness" / "M-T"
    )
    assert arc["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    with tarfile.open(path) as tar:
        assert sorted(tar.getnames()) == [
            "t/artifacts",
            "t/artifacts/crash-1",
            "t/corpus",
            "t/corpus/a",
        ]
    assert payload["stats"]["divergences"] == 1 and payload["corpus_files_after_cmin"] == 1
    out = rawio.write_raw(
        "correctness", payload, machine="M-T", profile="quick", script="s", environment=None
    )
    assert rawio.load_raw(out)["payload"]["kind"] == "fuzz"
