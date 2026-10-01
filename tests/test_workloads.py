import copy
import hashlib
import zlib

import pytest

from cfbench import cleanflate_src, config, paths, workloads

FILES = {
    "canterbury": {"alice29.txt": b"alice " * 400, "kennedy.xls": bytes(range(256)) * 8},
    "silesia": {"xml": b"<a>" * 1000, "dickens": b"it was the best " * 100},
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path / "data")

    def corpus_files(corpus):
        out = []
        for name, data in sorted(FILES[corpus].items()):
            p = tmp_path / "corpora" / corpus / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            out.append((name, p, hashlib.sha256(data).hexdigest(), len(data)))
        return out

    monkeypatch.setattr(cleanflate_src, "corpus_files", corpus_files)
    monkeypatch.setattr(workloads, "zlib_version", lambda: "9.9.9")
    calls = []

    def fake(orig, level, framing, out):
        calls.append((orig.name, level, framing))
        out.write_bytes(zlib.compress(orig.read_bytes(), level) + framing.encode())

    fake.calls = calls
    return fake


def cfg(**perf):
    c = copy.deepcopy(config.load_config("full"))
    c["perf"].update(perf)
    return c


def test_list_workloads_respects_files_filter_and_always_adds_tiny(env):
    c = cfg(files=["canterbury/alice29.txt"], levels=[6], framings=["raw", "zlib"])
    c["perf"]["tiny"]["prefix_bytes"] = [64]
    ws = workloads.list_workloads(c)
    ids = sorted({w.id for w in ws})
    assert ids == [
        "canterbury/alice29.txt",
        "tiny/canterbury-alice29.txt-64",
        "tiny/canterbury-kennedy.xls-64",
        "tiny/silesia-xml-64",
    ]
    assert len(ws) == len(ids) * 1 * 2
    assert [w.id for w in ws] == sorted(w.id for w in ws)
    full = workloads.list_workloads(cfg(levels=[6], framings=["raw"]))
    assert {w.corpus for w in full} == {"canterbury", "silesia", "tiny"}
    assert len([w for w in full if w.corpus != "tiny"]) == 4


def test_tiny_prefix_paths_and_lengths(env):
    c = cfg(levels=[1], framings=["gzip"])
    c["perf"]["tiny"]["prefix_bytes"] = [64, 100000]
    ws = {w.id: w for w in workloads.list_workloads(c) if w.corpus == "tiny"}
    short = ws["tiny/canterbury-alice29.txt-64"]
    assert short.orig_len == 64
    assert (
        short.orig_path == paths.DATA / "workloads" / "tiny" / "canterbury-alice29.txt-64" / "orig"
    )
    assert short.path.name == "l1.gzip"
    # a prefix longer than the source is clamped to the whole file
    assert ws["tiny/canterbury-alice29.txt-100000"].orig_len == len(
        FILES["canterbury"]["alice29.txt"]
    )
    workloads.generate(c, compressor=env)
    assert short.orig_path.read_bytes() == FILES["canterbury"]["alice29.txt"][:64]


def test_generate_then_verify_and_manifest_is_sorted(env):
    c = cfg(levels=[1, 6], framings=["raw", "zlib"])
    c["perf"]["tiny"]["prefix_bytes"] = [64]
    entries = workloads.generate(c, compressor=env, write_manifest=True)
    assert len(entries) == (4 + 3) * 4
    m = workloads.load_manifest()
    assert m["zlib_version"] == "9.9.9"
    keys = [(e["id"], e["level"], e["framing"]) for e in m["entries"]]
    assert keys == sorted(keys)
    assert workloads.verify(c) == []
    n = len(env.calls)
    workloads.generate(c, compressor=env)
    assert len(env.calls) == n  # nothing regenerated


def test_verify_detects_hash_mismatch(env):
    c = cfg(levels=[6], framings=["raw"])
    c["perf"]["tiny"]["prefix_bytes"] = [64]
    workloads.generate(c, compressor=env, write_manifest=True)
    victim = next(w for w in workloads.list_workloads(c) if w.corpus == "silesia")
    victim.path.write_bytes(b"corrupted")
    problems = workloads.verify(c)
    assert len(problems) == 1 and "differs from manifest" in problems[0]
    victim.path.unlink()
    assert "missing" in workloads.verify(c)[0]


def test_generate_refuses_to_overwrite_mismatched_file(env):
    c = cfg(levels=[6], framings=["raw"])
    c["perf"]["tiny"]["prefix_bytes"] = [64]
    workloads.generate(c, compressor=env, write_manifest=True)
    victim = next(w for w in workloads.list_workloads(c) if w.corpus == "canterbury")
    victim.path.write_bytes(b"tampered")
    with pytest.raises(workloads.WorkloadError, match="refusing to overwrite"):
        workloads.generate(c, compressor=env)
    assert victim.path.read_bytes() == b"tampered"


def test_regenerated_stream_that_differs_is_rejected(env):
    c = cfg(levels=[6], framings=["raw"])
    c["perf"]["tiny"]["prefix_bytes"] = [64]
    workloads.generate(c, compressor=env, write_manifest=True)
    victim = next(w for w in workloads.list_workloads(c) if w.corpus == "canterbury")
    victim.path.unlink()

    def nondeterministic(orig, level, framing, out):
        out.write_bytes(b"different")

    with pytest.raises(workloads.WorkloadError, match="differs from manifest"):
        workloads.generate(c, compressor=nondeterministic)
    assert not victim.path.exists()


def test_corrupt_corpus_input_is_rejected(env, monkeypatch):
    c = cfg(levels=[6], framings=["raw"])
    c["perf"]["tiny"]["prefix_bytes"] = [64]
    real = cleanflate_src.corpus_files

    def bad(corpus):
        return [(n, p, "0" * 64, b) for n, p, _s, b in real(corpus)]

    monkeypatch.setattr(cleanflate_src, "corpus_files", bad)
    with pytest.raises(workloads.WorkloadError, match="SHA-256"):
        workloads.generate(c, compressor=env)
