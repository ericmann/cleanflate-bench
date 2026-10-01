import json
from pathlib import Path

import pytest

from cfbench import cleanflate_src, config, paths, provenance, rawio
from cfbench import conformance as cf

CLONE = Path("/clone")
MANIFEST = {
    "entries": [
        {"id": "a__raw", "path": "canterbury/a/raw.bin", "framing": "raw", "dictionary": None,
         "input_sha256": "aa", "input_len": 10},
        {"id": "a__zlib_dict", "path": "canterbury/a/zlib-dict.bin", "framing": "zlib",
         "dictionary": {"input": "testdata/corpora/canterbury/lcet10.txt", "len": 5, "sha256": "dd"},
         "input_sha256": "bb", "input_len": 20},
        {"id": "a__gzip", "path": "canterbury/a/gz.bin", "framing": "gzip", "dictionary": None,
         "input_sha256": "cc", "input_len": 30},
    ]
}  # fmt: skip


def test_manifest_entries_become_jobs_with_dictionary():
    jobs = cf.manifest_jobs(MANIFEST, CLONE)
    assert [j.id for j in jobs] == ["a__raw", "a__zlib_dict", "a__gzip"]
    assert jobs[0].path == CLONE / "testdata" / "generated" / "canterbury/a/raw.bin"
    assert (
        jobs[0].dictionary is None
        and jobs[0].expected_sha256 == "aa"
        and jobs[0].expected_len == 10
    )
    assert jobs[1].dictionary == CLONE / "testdata/corpora/canterbury/lcet10.txt"
    argv = cf.decode_argv(["bin"], jobs[1], 1048576, 1048576)
    assert argv[:2] == ["bin", "decode"] and argv[argv.index("--mode") + 1] == "stream"
    assert argv[argv.index("--dictionary") + 1].endswith("lcet10.txt")
    assert "--dictionary" not in cf.decode_argv(["bin"], jobs[0], 1, 1)
    assert argv[argv.index("--in-chunk") + 1] == "1048576"


def test_workload_jobs_use_original_digest(tmp_path, monkeypatch):
    from cfbench import workloads

    orig = tmp_path / "orig"
    orig.write_bytes(b"hello")
    wl = workloads.Workload(
        "silesia/x", "silesia", "x", 6, "gzip", orig, tmp_path / "l6.gzip", 5, 20
    )
    monkeypatch.setattr(workloads, "list_workloads", lambda cfg: [wl])
    (job,) = cf.workload_jobs(config.load_config("full"))
    import hashlib

    assert job.id == "silesia/x/l6.gzip" and job.source == "workload"
    assert job.expected_sha256 == hashlib.sha256(b"hello").hexdigest() and job.expected_len == 5


def job(framing="zlib", dictionary=None):
    return cf.Job("j", "generated", Path("p"), framing, dictionary, "aa", 10)


def test_unsupported_is_not_counted_as_failure():
    caps = {"framings": ["raw", "zlib"], "dictionary": False}
    assert cf.judge(job("gzip"), caps, None) == ("unsupported", "")
    assert cf.judge(job("zlib", Path("d")), caps, None) == ("unsupported", "")
    ok = {"ok": True, "sha256": "aa", "produced": 10}
    assert cf.judge(job(), caps, ok) == ("pass", "")
    assert cf.judge(job(), caps, {**ok, "sha256": "zz"})[0] == "fail"
    assert "output mismatch" in cf.judge(job(), caps, {**ok, "produced": 9})[1]
    bad = {"ok": False, "error_kind": "BadHeader", "error": "boom"}
    assert cf.judge(job(), caps, bad) == ("fail", "BadHeader: boom")
    payload = {
        "subjects": ["a", "b"],
        "jobs": [
            {
                "id": "1",
                "framing": "gzip",
                "outcomes": {"a": "pass", "b": "unsupported"},
                "errors": {},
            },
            {
                "id": "2",
                "framing": "raw",
                "outcomes": {"a": "pass", "b": "fail"},
                "errors": {"b": "x"},
            },
        ],
    }
    rows = {r["subject"]: r for r in cf.summary_rows(payload, "M-T")}
    assert (rows["b"]["passed"], rows["b"]["failed"], rows["b"]["unsupported"]) == (0, 1, 1)
    assert (
        rows["b"]["pass_rate"] == 0.0
        and rows["a"]["pass_rate"] == 1.0
        and rows["a"]["streams"] == 2
    )
    only_unsupported = cf.summary_rows(
        {"subjects": ["m"], "jobs": [{"outcomes": {"m": "unsupported"}}]}, "M-T"
    )[0]
    assert only_unsupported["pass_rate"] is None and only_unsupported["failed"] == 0


def test_disagreement_detection():
    payload = {
        "subjects": ["a", "b", "c"],
        "jobs": [
            {"id": "all-pass", "framing": "raw", "outcomes": {"a": "pass", "b": "pass", "c": "pass"}, "errors": {}},
            {"id": "one-fails", "framing": "raw", "outcomes": {"a": "pass", "b": "pass", "c": "fail"},
             "errors": {"c": "BadHeader: x"}},
            {"id": "majority-fails", "framing": "zlib", "outcomes": {"a": "pass", "b": "fail", "c": "fail"},
             "errors": {"b": "e1", "c": "e2"}},
            {"id": "mox-n/a", "framing": "gzip", "outcomes": {"a": "pass", "b": "pass", "c": "unsupported"}, "errors": {}},
            {"id": "all-unsupported", "framing": "gzip", "outcomes": {"a": "unsupported"}, "errors": {}},
        ],
    }  # fmt: skip
    rows = cf.disagreement_rows(payload, "M-T")
    got = {(r["entry"], r["subject"]): r["outcome"] for r in rows}
    assert got == {("one-fails", "c"): "fail", ("majority-fails", "a"): "pass",
                   ("majority-fails", "b"): "fail", ("majority-fails", "c"): "fail"}  # fmt: skip
    assert next(r for r in rows if r["entry"] == "one-fails")["error"] == "BadHeader: x"
    assert all(r["machine"] == "M-T" for r in rows)


def test_pristine_check_failure_aborts(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cleanflate_src, "pristine_check", lambda path=None: ["working tree not clean: x"]
    )
    with pytest.raises(cf.ConformanceError, match="not pristine"):
        cf.generate_corpus(CLONE, runner=lambda cmd, cwd: calls.append((cmd, cwd)) or 0)
    assert (
        calls[0][0][:5] == ["cargo", "run", "--release", "--locked", "-q"] and calls[0][1] == CLONE
    )
    assert calls[0][0][-4:] == ["--", "generate", "--tier", "full"]
    # a failing generate (with --locked) is a blocker and never reaches the pristine check
    monkeypatch.setattr(
        cleanflate_src, "pristine_check", lambda path=None: pytest.fail("not reached")
    )
    with pytest.raises(cf.ConformanceError, match="blocker"):
        cf.generate_corpus(CLONE, runner=lambda cmd, cwd: 101)
    monkeypatch.setattr(cleanflate_src, "pristine_check", lambda path=None: [])
    cf.generate_corpus(CLONE, runner=lambda cmd, cwd: 0)


def test_derive_tables_from_raw_and_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    cf.derive()
    assert provenance.read_table("conformance")[1]["pending"] == cf.PENDING
    payload = {"kind": "conformance", "subjects": ["a", "b"], "capabilities": {},
               "jobs": [{"id": "j1", "source": "generated", "framing": "raw", "dictionary": False, "expected_len": 1,
                         "outcomes": {"a": "pass", "b": "fail"}, "errors": {"b": "boom"}}]}  # fmt: skip
    rawio.write_raw(
        "correctness", payload, machine="M-T", profile="full", script="t", environment=None
    )
    cf.derive()
    rows, side = provenance.read_table("conformance")
    assert side["pending"] is None and {r["subject"] for r in rows} == {"a", "b"}
    dis, _ = provenance.read_table("conformance_disagreements")
    assert [(r["entry"], r["subject"], r["error"]) for r in dis] == [("j1", "b", "boom")]
    assert json.dumps(rows)
