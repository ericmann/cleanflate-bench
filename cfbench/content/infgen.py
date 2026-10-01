"""infgen (pinned) build and parser: per-stream token statistics (SPEC 3.4).

infgen reads a zlib, gzip or raw deflate stream and writes a defgen-style text description. The
forms parsed here (from the documentation at the top of infgen.c at the pinned commit; run as
`infgen -q [-r] <file>`, where `-q` drops the dynamic code lengths and `-r` forces a raw stream):

    ! ...                  comment, ignored (infgen writes "! infgen 3.6 output", empty "!" lines)
    last                   marks the following block as the last one; ignored
    stored | fixed | dynamic | block3
                           starts a block of that type (counted)
    literal 13 10 'abc     literal bytes: decimal numbers, then optionally a string that starts
                           with a single quote and runs to the end of the line (a tab starts a
                           comment). Each number and each string character is one output byte.
    data 'xyz              the same byte syntax, inside a stored block (counted as output, not as
                           literals, because the bytes are copied, not coded)
    match L D              a match of length L (3..258) at distance D (1..32768)
    end                    ends a block
    zlib | gzip | adler | crc | length ...    wrapper directives, ignored

Statistics are computed over the output the stream produces. The `ratio` is
compressed_bytes / output_bytes (lower is better compression).
"""

import os
import subprocess
from bisect import bisect_left
from collections.abc import Iterable
from pathlib import Path

from cfbench import config, download, paths, tools

LEN_EDGES = [3, 4, 8, 16, 32, 64, 128, 258]
LEN_BINS = ["3", "4", "5-8", "9-16", "17-32", "33-64", "65-128", "129-258"]
DIST_EDGES = [1, 7, 64, 512, 4096, 32768]
DIST_BINS = ["1", "2-7", "8-64", "65-512", "513-4096", "4097-32768"]
BLOCK_KINDS = ("stored", "fixed", "dynamic")


def spec() -> dict:
    return config.load_toml("tools.toml")["infgen"]


def binary_path() -> Path:
    return tools.tools_root() / "bin" / "infgen"


def ensure() -> Path:
    """Download (pinned URL and SHA-256) and build infgen into third_party/tools/bin."""
    out = binary_path()
    if out.exists():
        return out
    s = spec()
    tarball = download.fetch(s["url"], s["sha256"])
    src = download.extract(tarball, paths.THIRD_PARTY / "src" / f"infgen-{s['commit'][:12]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    zlib_dir = paths.BUILD / "c" / "zlib"
    if (zlib_dir / "lib" / "libz.a").exists():
        cmd = [
            cc,
            "-O2",
            f"-I{zlib_dir / 'include'}",
            "-o",
            str(out),
            str(src / "infgen.c"),
            str(zlib_dir / "lib" / "libz.a"),
        ]
    else:
        cmd = [cc, "-O2", "-o", str(out), str(src / "infgen.c"), "-lz"]
    subprocess.run(cmd, check=True)
    return out


def count_bytes(rest: str) -> int:
    """Bytes described by the parameters of a literal/data/copy directive."""
    tab = rest.find("\t")
    if tab >= 0:
        rest = rest[:tab]
    q = rest.find("'")
    numbers = rest if q < 0 else rest[:q]
    n = len(numbers.split())
    if q >= 0:
        n += len(rest) - q - 1  # every character after the opening quote is one byte
    return n


def _bin(edges: list[int], value: int) -> int:
    return bisect_left(edges, value)


def parse_lines(lines: Iterable[str]) -> dict:
    """Raw token counts from infgen text (see the module docstring for the forms)."""
    literals = data = matches = 0
    match_bytes = 0
    len_hist = [0] * len(LEN_BINS)
    dist_hist = [0] * len(DIST_BINS)
    dist_hist_bytes = [0] * len(DIST_BINS)
    overlap = overlap_bytes = 0
    blocks = {k: 0 for k in BLOCK_KINDS}
    for line in lines:
        line = line.rstrip("\r\n")
        if not line or line[0] == "!":
            continue
        word, _, rest = line.partition(" ")
        if word == "literal":
            literals += count_bytes(rest)
        elif word == "match":
            ln, _, dist = rest.partition(" ")
            length, d = int(ln), int(dist)
            matches += 1
            match_bytes += length
            len_hist[_bin(LEN_EDGES, length)] += 1
            b = _bin(DIST_EDGES, d)
            dist_hist[b] += 1
            dist_hist_bytes[b] += length
            if d < length:
                overlap += 1
                overlap_bytes += length
        elif word == "data":
            data += count_bytes(rest)
        elif word in blocks:
            blocks[word] += 1
    return {
        "literals": literals,
        "stored_bytes": data,
        "matches": matches,
        "match_bytes": match_bytes,
        "len_hist": len_hist,
        "dist_hist": dist_hist,
        "dist_hist_bytes": dist_hist_bytes,
        "overlap": overlap,
        "overlap_bytes": overlap_bytes,
        "blocks": blocks,
    }


def summarize(raw: dict, compressed_bytes: int) -> dict:
    """Derived features from raw counts."""
    out_bytes = raw["literals"] + raw["stored_bytes"] + raw["match_bytes"]
    m = raw["matches"]

    def frac(n: int, d: int) -> float | None:
        return n / d if d else None

    return {
        "literals": raw["literals"],
        "matches": m,
        "literal_fraction": frac(raw["literals"], out_bytes),
        "match_len_hist": dict(zip(LEN_BINS, raw["len_hist"], strict=True)),
        "match_dist_hist": dict(zip(DIST_BINS, raw["dist_hist"], strict=True)),
        "dist1_fraction": frac(raw["dist_hist"][0], m),
        "dist1_byte_fraction": frac(raw["dist_hist_bytes"][0], out_bytes),
        "dist2_7_fraction": frac(raw["dist_hist"][1], m),
        "dist2_7_byte_fraction": frac(raw["dist_hist_bytes"][1], out_bytes),
        "overlap_fraction": frac(raw["overlap"], m),
        "overlap_byte_fraction": frac(raw["overlap_bytes"], out_bytes),
        "blocks": dict(raw["blocks"]),
        "compressed_bytes": compressed_bytes,
        "output_bytes": out_bytes,
        "ratio": frac(compressed_bytes, out_bytes),
    }


def stats(stream_path: Path, framing: str, infgen: Path | None = None) -> dict:
    """Run infgen over a stream file and return its token statistics."""
    exe = infgen or ensure()
    argv = [str(exe), "-q", *(["-r"] if framing == "raw" else []), str(stream_path)]
    with subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="latin-1"
    ) as p:
        raw = parse_lines(p.stdout)
        err = p.stderr.read()
    if p.returncode != 0:
        raise RuntimeError(f"infgen failed on {stream_path}: {err.strip()[:200]}")
    return summarize(raw, Path(stream_path).stat().st_size)
