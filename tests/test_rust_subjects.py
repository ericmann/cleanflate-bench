import hashlib
import json
import subprocess
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


ROUND_SHAS = {1: "e94efcf", 2: "d3e911b", 3: "85f2100"}


@pytest.fixture(scope="session")
def round_binaries():
    """Debug builds of each round, built on demand (cached after the first run)."""
    from cfbench import paths

    out = {}
    for n in ROUND_SHAS:
        target = paths.ROOT / "target" / f"round{n}"
        subprocess.run(
            ["cargo", "build", "-p", "subj-cf", "--no-default-features", "--features", f"round{n}",
             "--target-dir", str(target)],
            cwd=paths.ROOT, check=True, capture_output=True,
        )  # fmt: skip
        out[n] = target / "debug" / "cfb-cf"
    return out


@pytest.mark.parametrize("n", [1, 2, 3])
def test_round_binaries_decode_fixture(n, round_binaries):
    want = hashlib.sha256(PLAIN).hexdigest()
    exe = str(round_binaries[n])
    info = json.loads(
        subprocess.run([exe, "info"], capture_output=True, text=True, check=True).stdout
    )
    assert f"round {n}" in info["impl_version"] and ROUND_SHAS[n] in info["impl_version"]
    for framing in ("raw", "zlib", "gzip"):
        out = subprocess.run(
            [exe, "decode", "--framing", framing, "--mode", "stream", "--input",
             str(FIX / FILES[framing]), "--in-chunk", "5", "--out-chunk", "7"],
            capture_output=True, text=True, check=True,
        )  # fmt: skip
        r = json.loads(out.stdout)
        assert r["ok"] and r["sha256"] == want, (n, framing, r)


@pytest.mark.parametrize("subject", SUBJECTS)
def test_trailing_byte_reported(subject, tmp_path):
    data = (FIX / FILES["zlib"]).read_bytes() + b"\x00"
    p = tmp_path / "trail.zlib"
    p.write_bytes(data)
    for mode, extra in MODES:
        r = decode(subject, "zlib", p, mode, extra)
        if subject == "cf":
            assert r["ok"] is False, (mode, r)
            assert r["error_kind"] == "TrailingData", (mode, r)
        else:
            assert r["ok"], (subject, mode, r)
            assert r["consumed"] == len(data) - 1, (subject, mode, r)
            assert r["trailing_bytes"] == 1, (subject, mode, r)


ZEROS = bytes(1 << 20)


@pytest.mark.parametrize("subject", SUBJECTS)
def test_oneshot_grows_past_initial_buffer(subject, tmp_path):
    p = tmp_path / "zeros.zlib"
    p.write_bytes(zlib.compress(ZEROS))
    r = decode(subject, "zlib", p, "oneshot", [])
    assert r["ok"], (subject, r)
    assert r["produced"] == len(ZEROS)
    assert r["sha256"] == hashlib.sha256(ZEROS).hexdigest()


@pytest.mark.parametrize("subject", SUBJECTS)
def test_oneshot_max_output_sets_limit_hit(subject, tmp_path):
    p = tmp_path / "zeros.zlib"
    p.write_bytes(zlib.compress(ZEROS))
    r = decode(subject, "zlib", p, "oneshot", ["--max-output", 1000])
    assert r["ok"] is False, (subject, r)
    assert r["limit_hit"] is True, (subject, r)
    assert r["error_kind"] == "output_full", (subject, r)
