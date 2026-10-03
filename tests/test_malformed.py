import json

import pytest

from cfbench import malformed, paths, provenance

SUBJECTS = ["cf", "zrs", "mox"]


def res(ok, kind=None, trailing=0, produced=2):
    return {"ok": ok, "error_kind": kind, "error": kind or "", "produced": produced,
            "trailing_bytes": trailing}  # fmt: skip


def test_framing_from_directory():
    assert malformed.framing_of("rfc1950/adler_mismatch.bin") == "zlib"
    assert malformed.framing_of("rfc1951/btype3.bin") == "raw"
    assert malformed.framing_of("rfc1952/bad_magic.bin") == "gzip"
    with pytest.raises(KeyError):
        malformed.framing_of("other/x.bin")


def test_list_files_and_expected(tmp_path):
    for d, n in (("rfc1950", "a"), ("rfc1951", "b"), ("rfc1952", "c")):
        (tmp_path / d).mkdir()
        (tmp_path / d / f"{n}.bin").write_bytes(b"x")
    (tmp_path / "EXPECTED.tsv").write_text("# c\n# path\texpected\trule\nrfc1951/b.bin\tOK\tr1\n")
    assert malformed.list_files(tmp_path) == ["rfc1950/a.bin", "rfc1951/b.bin", "rfc1952/c.bin"]
    assert malformed.load_expected(tmp_path) == {"rfc1951/b.bin": {"expected": "OK", "rule": "r1"}}


def test_trailing_accept_is_distinguished():
    assert malformed.outcome(res(True)) == "accept"
    assert malformed.outcome(res(True, trailing=3)) == "accept+trailing"
    assert malformed.outcome(res(False, "TrailingData")) == "error:TrailingData"
    assert malformed.outcome(None) == "error:crash"
    assert malformed.is_accept("accept+trailing") and not malformed.is_accept("error:X")
    assert malformed.expected_matches("OK", "accept+trailing")
    assert malformed.expected_matches("BadHeader", "error:BadHeader")
    assert not malformed.expected_matches("BadHeader", "error:Truncated")


def test_disagreement_requires_differing_accept_reject():
    assert not malformed.is_disagreement({"cf": "error:A", "zrs": "error:B"})  # different kinds
    assert not malformed.is_disagreement({"cf": "accept", "zrs": "accept+trailing"})
    assert malformed.is_disagreement({"cf": "error:TrailingData", "zrs": "accept"})
    assert not malformed.is_disagreement({"cf": "error:A", "mox": "unsupported"})  # one supported
    assert malformed.is_disagreement({"cf": "accept", "zrs": "error:A", "mox": "unsupported"})


def test_run_all_with_fake_runner_and_derive(tmp_path, monkeypatch):
    from cfbench import config, rawio

    root = tmp_path / "m"
    for d in malformed.FRAMING_DIRS:
        (root / d).mkdir(parents=True)
    (root / "rfc1950" / "t.bin").write_bytes(b"x")
    (root / "rfc1951" / "u.bin").write_bytes(b"x")
    (root / "EXPECTED.tsv").write_text(
        "rfc1950/t.bin\tTrailingData\trule t\nrfc1951/u.bin\tBadHeader\trule u\n"
    )
    cfg = config.load_config("full")
    monkeypatch.setattr(malformed.subjects, "command", lambda s: ["fake", s])
    monkeypatch.setattr(
        malformed.subprocess,
        "run",
        lambda *a, **k: type(
            "R", (), {"stdout": json.dumps({"framings": ["raw", "zlib", "gzip"]})}
        )(),
    )

    def runner(argv):
        s = argv[1]
        if "t.bin" in argv[-1]:
            return res(False, "TrailingData") if s == "cf" else res(True)
        return res(False, "Truncated")

    payload = malformed.run_all(cfg, root, runner)
    cf_t = payload["files"][0]
    assert cf_t["results"]["zlib"]["outcome"] == "accept" and cf_t["rule"] == "rule t"
    assert [d["file"] for d in malformed.disagreements(payload)] == ["rfc1950/t.bin"]
    assert [f["file"] for f in malformed.cf_mismatches(payload)] == ["rfc1951/u.bin"]
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    (tmp_path / "results").mkdir()
    monkeypatch.setattr(paths, "RAW", tmp_path / "raw")
    rawio.write_raw(
        "correctness", payload, machine="M-T", profile="full", script="s", environment=None
    )
    malformed.derive()
    assert len(provenance.read_table("malformed_matrix")[0]) == 2 * len(
        cfg["conformance"]["subjects"]
    )
    assert "rfc1950/t.bin" in (tmp_path / "results" / "MALFORMED_HIGHLIGHTS.md").read_text()
    findings = (tmp_path / "results" / "findings.md").read_text()
    assert "rfc1951/u.bin" in findings
    malformed.derive()  # idempotent
    assert (tmp_path / "results" / "findings.md").read_text() == findings


def test_run_all_trailing_bytes_yield_accept_trailing(tmp_path, monkeypatch):
    from cfbench import config

    root = tmp_path / "m"
    for d in malformed.FRAMING_DIRS:
        (root / d).mkdir(parents=True)
    (root / "rfc1950" / "t.bin").write_bytes(b"x")
    (root / "EXPECTED.tsv").write_text("rfc1950/t.bin\tOK\trule t\n")
    cfg = config.load_config("full")
    monkeypatch.setattr(malformed.subjects, "command", lambda s: ["fake", s])
    monkeypatch.setattr(
        malformed.subprocess,
        "run",
        lambda *a, **k: type(
            "R", (), {"stdout": json.dumps({"framings": ["raw", "zlib", "gzip"]})}
        )(),
    )
    payload = malformed.run_all(cfg, root, lambda argv: res(True, trailing=1))
    assert payload["files"][0]["results"]["zlib"]["outcome"] == "accept+trailing"


def _payload(outcomes_by_file):
    subjects = ["cf", "zlib", "mox"]
    files = []
    for name, (expected, outs) in outcomes_by_file.items():
        files.append({"file": name, "framing": "zlib", "rule": "r", "cf_expected": expected,
                      "results": {s: {"outcome": o} for s, o in zip(subjects, outs, strict=True)}})  # fmt: skip
    return {"subjects": subjects, "files": files}


def test_summary_row_counts_matches_and_cf_stricter_disagreements():
    p = _payload({
        "rfc1950/a.bin": ("TrailingData", ("error:TrailingData", "accept+trailing", "unsupported")),
        "rfc1950/b.bin": ("OK", ("accept", "error:X", "accept")),
        "rfc1950/c.bin": ("BadHeader", ("error:Other", "error:Y", "error:Z")),
    })  # fmt: skip
    row = malformed.summary_row(p, "M-T")
    assert row == {"machine": "M-T", "files": 3, "subjects": 3, "cf_expected_files": 3, "cf_matches_expected": 2,
                   "cf_mismatches": 1, "disagreements": 2, "disagreements_cf_stricter": 1}  # fmt: skip
    assert malformed.cf_stricter({"cf": "error:A", "zlib": "accept", "mox": "unsupported"})
    assert not malformed.cf_stricter({"cf": "error:A", "zlib": "accept", "mox": "error:B"})


def test_highlights_and_findings_cover_every_machine(tmp_path):
    a = _payload({"rfc1950/a.bin": ("TrailingData", ("error:TrailingData", "accept", "accept"))})
    b = _payload({"rfc1950/a.bin": ("TrailingData", ("accept", "accept", "accept"))})
    text = malformed.highlights([("M-A", a), ("M-B", b)])
    assert (
        "M-A: 1 files, 3 subjects. 1 disagree" in text
        and "M-B: 1 files, 3 subjects. 0 disagree" in text
    )
    assert "- Outcomes on M-A: cf=error:TrailingData" in text
    assert "- M-A: cf's outcome matches EXPECTED.tsv for every file." in text
    assert "- M-B: rfc1950/a.bin: expected TrailingData, got accept" in text
    findings = tmp_path / "findings.md"
    assert malformed.update_findings([("M-A", a), ("M-B", b)], findings)
    assert "`rfc1950/a.bin` on M-B: expected TrailingData" in findings.read_text()
