import hashlib
import json
import zlib

import pytest

from tests.cli_util import FILES, FIX, MODES, PLAIN, build_debug, decode, run

C_SUBJECTS = ["zlib", "zlib-nohw", "zsys"]
WBITS = {"raw": -15, "zlib": 15, "gzip": 31}


@pytest.fixture(scope="session", autouse=True)
def _built():
    build_debug()


@pytest.mark.parametrize("subject", C_SUBJECTS)
def test_info_versions(subject):
    info = run(subject, "info")
    assert info["id"] == subject
    assert info["framings"] == ["raw", "zlib", "gzip"]
    if subject == "zsys":
        assert info["impl_version"]
    else:
        assert info["impl_version"] == "1.3.2"


@pytest.mark.parametrize("subject", C_SUBJECTS)
def test_decode_fixture_all_framings(subject):
    want = hashlib.sha256(PLAIN).hexdigest()
    for framing in ("raw", "zlib", "gzip"):
        for mode, extra in MODES:
            r = decode(subject, framing, FIX / FILES[framing], mode, extra)
            assert r["ok"], (subject, framing, mode, r)
            assert r["sha256"] == want
            assert r["trailing_bytes"] == 0 or mode == "oneshot"


def test_compress_roundtrip_all_framings_levels_1_6_9(tmp_path):
    for framing in ("raw", "zlib", "gzip"):
        for level in (1, 6, 9):
            out = tmp_path / f"o.{framing}.{level}"
            r = run(
                "zlib", "compress", "--level", level, "--framing", framing,
                "--input", FIX / "hello.txt", "--output", out,
            )  # fmt: skip
            assert r["ok"], r
            data = out.read_bytes()
            d = zlib.decompressobj(WBITS[framing])
            assert d.decompress(data) + d.flush() == PLAIN
            back = decode("zlib", framing, out, "oneshot", [])
            assert back["ok"] and back["sha256"] == hashlib.sha256(PLAIN).hexdigest()


def test_only_stock_zlib_compresses(tmp_path):
    for subject in ("zlib-nohw", "zsys", "cf"):
        r = run(
            subject, "compress", "--level", 6, "--framing", "raw",
            "--input", FIX / "hello.txt", "--output", tmp_path / "x",
        )  # fmt: skip
        assert r["ok"] is False and r["error"] == "unsupported"


def test_gzip_header_is_os255_mtime0(tmp_path):
    out = tmp_path / "o.gz"
    run(
        "zlib", "compress", "--level", 6, "--framing", "gzip",
        "--input", FIX / "hello.txt", "--output", out,
    )  # fmt: skip
    data = out.read_bytes()
    assert data[:2] == b"\x1f\x8b"
    assert data[4:8] == b"\x00\x00\x00\x00"
    assert data[9] == 255


@pytest.mark.parametrize("subject", C_SUBJECTS)
def test_heap_is_counted_via_zalloc(subject, tmp_path):
    cell = {
        "framing": "zlib", "mode": "oneshot", "in_chunk": 1024, "out_chunk": 4096,
        "input": str(FIX / "hello.zlib"), "expected": str(FIX / "hello.txt"),
        "warmup_ms": 1, "min_samples": 3, "min_sample_ms": 1,
    }  # fmt: skip
    p = tmp_path / "cell.json"
    p.write_text(json.dumps(cell))
    r = run(subject, "bench", "--cell", p)
    assert r["ok"], r
    assert r["peak_heap_bytes"] > 0
    if subject != "zsys":
        # zalloc routes the inflate state (window etc.) through the counting allocator
        assert r["peak_heap_bytes"] > len(PLAIN) + 1024
