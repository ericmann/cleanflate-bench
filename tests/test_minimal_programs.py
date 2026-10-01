import subprocess

import pytest

from cfbench import paths
from tests.cli_util import FIX, PLAIN, build_debug

RUST = ["cf", "zrs", "mox"]


@pytest.fixture(scope="session", autouse=True)
def _built():
    build_debug()


def run_min(program, data):
    exe = paths.ROOT / "target" / "debug" / f"min-{program}"
    return subprocess.run([str(exe)], input=data, capture_output=True, check=False)


@pytest.mark.parametrize("program", RUST)
def test_rust_minimal_roundtrip(program):
    r = run_min(program, (FIX / "hello.zlib").read_bytes())
    assert r.returncode == 0, r.stderr
    assert r.stdout == PLAIN
    assert r.stderr == b""


@pytest.mark.parametrize("program", RUST)
def test_rust_minimal_rejects_corrupt_input(program):
    good = (FIX / "hello.zlib").read_bytes()
    bad_trailer = good[:-1] + bytes([good[-1] ^ 0xFF])
    for data in (bad_trailer, good[:-3], b"", b"\x00\x01garbage"):
        r = run_min(program, data)
        assert r.returncode == 1, (program, data)
        assert r.stderr.decode().startswith("error: ")
        assert r.stderr.count(b"\n") == 1


@pytest.mark.parametrize("program", RUST)
def test_rust_minimal_streams_large_input(program):
    import os
    import zlib

    payload = (b"The quick brown fox jumps over the lazy dog. " * 4000) + os.urandom(200_000)
    r = run_min(program, zlib.compress(payload, 6))
    assert r.returncode == 0 and r.stdout == payload
