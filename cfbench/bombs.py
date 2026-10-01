"""Decompression-bomb robustness sweep (SPEC 3.6).

Zeros of each configured size are compressed (zlib framing, level 9, streamed chunk-wise so memory
stays bounded) and decoded by every subject with the configured output limit. A nested bomb,
`gzip^N(zeros)` over the largest size, reaches overall ratios beyond 1:1,000,000 because one DEFLATE
layer cannot exceed about 1032:1. Each nested layer is decoded separately: the output of layer `j`
is checked to equal the stored layer `j-1` stream.

Peak RSS is read from the child's own resource usage (`os.wait4`, the same figure
`getrusage(RUSAGE_CHILDREN)` reports for a single child), normalized to bytes. The kernel seeds a
child's peak with the launcher's resident size at fork, so every figure has the driver's own RSS as
a floor; the raw document records that floor (`rss_floor_bytes`, measured by launching `true`).
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zlib
from pathlib import Path

from cfbench import config, env, machine, paths, provenance, rawio, subjects

KIND = "bombs"
SCRIPT = "cfbench.bombs"
COLUMNS = ["machine", "subject", "case", "ratio", "output_bytes", "limit_bytes", "outcome",
           "peak_rss_bytes", "seconds", "limit_enforcement"]  # fmt: skip
PENDING = "no bomb sweep; run make bombs (a human step: 4 GiB cases)"
CHUNK = 1 << 20
GZIP_WBITS = 31
ZLIB_WBITS = 15


def bomb_dir() -> Path:
    return paths.DATA / "workloads" / "bombs"


def rss_bytes(ru_maxrss: int, platform: str | None = None) -> int:
    """`ru_maxrss` is KiB on Linux and bytes on macOS."""
    return ru_maxrss if (platform or sys.platform) == "darwin" else ru_maxrss * 1024


def ratio(output_bytes: int, compressed_bytes: int) -> float | None:
    return output_bytes / compressed_bytes if compressed_bytes else None


def compress_stream(src_chunks, dest: Path, wbits: int, level: int = 9) -> int:
    """Compress an iterable of byte chunks into `dest`; returns the compressed size."""
    comp = zlib.compressobj(level, zlib.DEFLATED, wbits)
    with open(dest, "wb") as f:
        f.writelines(comp.compress(chunk) for chunk in src_chunks)
        f.write(comp.flush())
    return dest.stat().st_size


def zero_chunks(total: int):
    full, rest = divmod(total, CHUNK)
    block = bytes(CHUNK)
    for _ in range(full):
        yield block
    if rest:
        yield bytes(rest)


def file_chunks(path: Path):
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            yield chunk


def generate(cfg: dict, out: Path | None = None) -> list[dict]:
    """Bomb files and their metadata; existing files are reused (generation is deterministic)."""
    out = out or bomb_dir()
    out.mkdir(parents=True, exist_ok=True)
    b = cfg["bomb"]
    cases = []
    for size in b["output_sizes"]:
        p = out / f"zeros-{size}.zlib"
        if not p.exists():
            compress_stream(zero_chunks(size), p, ZLIB_WBITS)
        cases.append({"case": f"zeros-{size}", "path": p, "framing": "zlib", "output_bytes": size,
                      "compressed_bytes": p.stat().st_size, "layer": None})  # fmt: skip
    base = max(b["output_sizes"])
    layers = [out / f"nested-0-{base}.zeros"]  # layer 0 is the zeros themselves (never stored)
    prev = None
    for k in range(1, b["nested_layers"] + 1):
        p = out / f"nested-{k}-{base}.gz"
        if not p.exists():
            compress_stream(zero_chunks(base) if prev is None else file_chunks(prev), p, GZIP_WBITS)
        layers.append(p)
        prev = p
    outer = layers[-1].stat().st_size
    for k in range(1, b["nested_layers"] + 1):
        inner = None if k == 1 else layers[k - 1]
        cases.append({
            "case": f"nested-{b['nested_layers']}x-{base}:layer{k}", "path": layers[k], "framing": "gzip",
            "output_bytes": base if k == 1 else layers[k - 1].stat().st_size,
            "compressed_bytes": layers[k].stat().st_size, "layer": k,
            "inner_sha256": hashlib.sha256(inner.read_bytes()).hexdigest() if inner else None,
            "overall_ratio": ratio(base, outer),
        })  # fmt: skip
    return cases


def run_child(argv: list[str]) -> dict:
    """Run one child; returns its JSON result, wall seconds and peak RSS in bytes."""
    t0 = time.perf_counter()
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert p.stdout is not None
    out = p.stdout.read()
    _pid, status, usage = os.wait4(p.pid, 0)
    seconds = time.perf_counter() - t0
    p.returncode = os.waitstatus_to_exitcode(status)
    try:
        result = json.loads(out)
    except ValueError:
        result = None
    return {"result": result, "seconds": seconds, "peak_rss_bytes": rss_bytes(usage.ru_maxrss)}


def decode_argv(cmd: list[str], case: dict, cfg: dict) -> list[str]:
    perf = cfg["perf"]
    return [*cmd, "decode", "--framing", case["framing"], "--mode", "stream", "--input",
            str(case["path"]), "--in-chunk", str(perf["large_in_chunk"]), "--out-chunk",
            str(perf["large_out_chunk"]), "--max-output", str(cfg["bomb"]["output_limit_bytes"])]  # fmt: skip


def outcome_of(result: dict | None, expected_sha: str | None = None) -> str:
    if result is None:
        return "error:crash"
    if not result["ok"]:
        return f"error:{result.get('error_kind')}"
    if result.get("limit_hit"):
        return "limit"
    if expected_sha is not None and result.get("sha256") != expected_sha:
        return "output-mismatch"
    return "ok"


def run_all(cfg: dict, cases: list[dict], machine_id: str, runner=run_child) -> list[dict]:
    limit = cfg["bomb"]["output_limit_bytes"]
    rows = []
    for s in cfg["bomb"]["subjects"]:
        cmd = subjects.command(s)
        info = json.loads(
            subprocess.run([*cmd, "info"], capture_output=True, text=True, check=True).stdout
        )
        enforcement = info["output_limit"]  # native or caller
        for c in cases:
            row = {"machine": machine_id, "subject": s, "case": c["case"],
                   "ratio": c.get("overall_ratio") or ratio(c["output_bytes"], c["compressed_bytes"]),
                   "output_bytes": None, "limit_bytes": limit, "outcome": "unsupported",
                   "peak_rss_bytes": None, "seconds": None, "limit_enforcement": enforcement}  # fmt: skip
            if c["framing"] in info["framings"]:
                m = runner(decode_argv(cmd, c, cfg))
                r = m["result"]
                row["output_bytes"] = r["produced"] if r else None
                row["outcome"] = outcome_of(r, c.get("inner_sha256"))
                row["peak_rss_bytes"], row["seconds"] = m["peak_rss_bytes"], m["seconds"]
            rows.append(row)
    return rows


def run(profile: str = "full") -> Path:
    cfg = config.load_config(profile)
    cases = generate(cfg)
    mach = machine.detect_machine()
    floor = run_child([shutil.which("true") or "true"])["peak_rss_bytes"]
    rows = run_all(cfg, cases, mach)
    nested = [c for c in cases if c["layer"] is not None]
    payload = {
        "kind": KIND,
        "limit_bytes": cfg["bomb"]["output_limit_bytes"],
        "rss_floor_bytes": floor,
        "cases": [{k: (str(v) if isinstance(v, Path) else v) for k, v in c.items() if k != "path"} for c in cases],
        "nested_overall_ratio": nested[-1]["overall_ratio"] if nested else None,
        "rows": rows,
    }  # fmt: skip
    return rawio.write_raw("correctness", payload, machine=mach, profile=profile, script=SCRIPT,
                           environment=env.capture_environment())  # fmt: skip


def derive() -> None:
    files = rawio.list_raw("correctness", kind=KIND)
    if not files:
        provenance.write_table("bombs", COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING)
        return
    newest = {}
    for p in files:
        d = rawio.load_raw(p)
        if d["machine"] not in newest or d["timestamp"] > newest[d["machine"]][1]["timestamp"]:
            newest[d["machine"]] = (p, d)
    rows = [r for _m, (_p, d) in sorted(newest.items()) for r in d["payload"]["rows"]]
    provenance.write_table(
        "bombs", COLUMNS, rows, script=SCRIPT, raw_files=[p for p, _d in newest.values()]
    )


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "run"
    profile = "full" if (os.environ.get("CFB_PROFILE") or "full") == "full" else "quick"
    if cmd == "run":
        print(run(profile))
        if profile == "full":
            derive()
    elif cmd == "derive":
        derive()
    else:
        print("usage: cfbench.bombs run|derive", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
