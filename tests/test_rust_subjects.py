import hashlib
import zlib

import pytest

from tests.cli_util import FILES, FIX, MODES, PLAIN, build_debug, decode, run

SUBJECTS = ["cf", "zrs", "mox"]


@pytest.fixture(scope="session", autouse=True)
def _built():
    build_debug()


@pytest.mark.parametrize("subject", SUBJECTS)
def test_info_reports_caps(subject):
    info = run(subject, "info")
    assert info["id"] == subject
    assert info["impl_version"]
    assert "raw" in info["framings"] and "zlib" in info["framings"]
    assert info["modes"] == ["oneshot", "stream"]
    assert info["output_limit"] == {"cf": "native", "zrs": "caller", "mox": "caller"}[subject]
    assert info["dictionary"] is (subject != "mox")


@pytest.mark.parametrize("subject", SUBJECTS)
def test_decode_fixture_all_supported_framings(subject):
    want = hashlib.sha256(PLAIN).hexdigest()
    for framing in run(subject, "info")["framings"]:
        for mode, extra in MODES:
            r = decode(subject, framing, FIX / FILES[framing], mode, extra)
            assert r["ok"], (subject, framing, mode, r)
            assert r["sha256"] == want
            assert r["produced"] == len(PLAIN)


@pytest.mark.parametrize("subject", SUBJECTS)
def test_corrupted_trailer_is_rejected(subject, tmp_path):
    for framing in run(subject, "info")["framings"]:
        if framing == "raw":
            continue
        data = bytearray((FIX / FILES[framing]).read_bytes())
        # zlib: last 4 bytes are Adler-32; gzip: CRC-32 sits 8 bytes from the end
        data[-1 if framing == "zlib" else -8] ^= 0xFF
        bad = tmp_path / f"bad.{framing}"
        bad.write_bytes(bytes(data))
        for mode, extra in MODES:
            r = decode(subject, framing, bad, mode, extra)
            assert r["ok"] is False, (subject, framing, mode)
            assert r["error_kind"]


def test_mox_gzip_is_unsupported():
    info = run("mox", "info")
    assert "gzip" not in info["framings"]
    r = decode("mox", "gzip", FIX / "hello.gz", "oneshot", [])
    assert r["ok"] is False
    assert r["error_kind"] == "unsupported"


def _xorshift(seed, n):
    mask = (1 << 64) - 1
    s = seed | 1
    out = bytearray()
    while len(out) < n:
        s ^= (s << 13) & mask
        s ^= s >> 7
        s ^= (s << 17) & mask
        out += s.to_bytes(8, "little")
    return bytes(out[:n])


@pytest.mark.parametrize("subject", ["cf", "zrs"])
def test_checksums_match_python_zlib(subject):
    size, seed = 4096, 7
    data = _xorshift(seed, size)
    flags = ["--warmup-ms", 1, "--min-samples", 3, "--min-sample-ms", 1]
    a = run(subject, "checksum", "--algo", "adler32", "--size", size, "--seed", seed, *flags)
    c = run(subject, "checksum", "--algo", "crc32", "--size", size, "--seed", seed, *flags)
    assert a["value"] == zlib.adler32(data)
    assert c["value"] == zlib.crc32(data)


def test_mox_checksums_adler_only():
    flags = ["--warmup-ms", 1, "--min-samples", 3, "--min-sample-ms", 1, "--seed", 7]
    a = run("mox", "checksum", "--algo", "adler32", "--size", 1024, *flags)
    assert a["value"] == zlib.adler32(_xorshift(7, 1024))
    c = run("mox", "checksum", "--algo", "crc32", "--size", 1024, *flags)
    assert c["ok"] is False and c["error"] == "unsupported"
