"""Helpers to drive the debug subject binaries from tests."""

import json
import subprocess

from cfbench import paths

FIX = paths.ROOT / "crates" / "harness" / "tests" / "fixtures"
PLAIN = (FIX / "hello.txt").read_bytes()
FILES = {"raw": "hello.raw", "zlib": "hello.zlib", "gzip": "hello.gz"}
MODES = [("oneshot", []), ("stream", ["--in-chunk", "5", "--out-chunk", "7"])]


def build_debug():
    subprocess.run(
        ["cargo", "build", "--workspace", "--bins"], cwd=paths.ROOT, check=True, capture_output=True
    )


def run(subject, *args):
    exe = paths.ROOT / "target" / "debug" / f"cfb-{subject}"
    out = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def decode(subject, framing, path, mode, extra):
    return run(subject, "decode", "--framing", framing, "--mode", mode, "--input", path, *extra)
