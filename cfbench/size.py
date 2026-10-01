"""Binary size, safety and dependency measurements (SPEC 3.7)."""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from cfbench import config, env, machine, paths, provenance, rawio, sources, tools

RUST_PROGRAMS = ["cf", "zrs", "mox"]
C_PROGRAMS = ["zlib", "zng"]
BINARY_COLUMNS = ["machine", "subject", "opt", "bytes", "note"]
BLOAT_COLUMNS = ["machine", "subject", "opt", "crate", "bytes", "share"]
ZSYS_NOTE = "dynamically linked system library; excluded from the static size comparison"
PENDING = "no size run; run make size"


# ---- command construction (pure, unit-tested) ----------------------------------------------


def _opt_config(opt: str) -> str:
    return (
        f"profile.release.opt-level={opt}"
        if opt.isdigit()
        else f'profile.release.opt-level="{opt}"'
    )


def target_dir(opt: str, stripped: bool) -> Path:
    return paths.ROOT / "target" / (f"size-{opt}" if stripped else f"size-{opt}-unstripped")


def rust_build_cmd(subject: str, opt: str, stripped: bool = True) -> list[str]:
    """Release build of `min-<subject>` with the given opt-level; `--config` keeps the member
    crates free of profile tables."""
    return [
        "cargo",
        "build",
        "--release",
        "-p",
        f"min-{subject}",
        "--target-dir",
        str(target_dir(opt, stripped)),
        "--config",
        _opt_config(opt),
        "--config",
        "profile.release.strip=true" if stripped else 'profile.release.strip="none"',
    ]


def bloat_cmd(subject: str, opt: str, top: int) -> tuple[list[str], dict]:
    """`cargo bloat` does not take `--config`, so the same profile goes in via environment."""
    cmd = [
        "cargo",
        "bloat",
        "--release",
        "-p",
        f"min-{subject}",
        "--crates",
        "-n",
        str(top),
        "--message-format",
        "json",
        "--target-dir",
        str(target_dir(opt, False)),
    ]
    envv = {"CARGO_PROFILE_RELEASE_OPT_LEVEL": opt, "CARGO_PROFILE_RELEASE_STRIP": "none"}
    return cmd, envv


def c_link_flags(system: str, opt: str) -> list[str]:
    gc = "-Wl,-dead_strip" if system == "Darwin" else "-Wl,--gc-sections"
    return [f"-O{opt}", "-flto", "-ffunction-sections", "-fdata-sections", gc]


def zlib_sources(makefile_in: str) -> list[str]:
    """The `.c` files of the `OBJZ` variable in zlib's Makefile.in."""
    m = re.search(r"^OBJZ\s*=\s*((?:.*\\\n)*.*)$", makefile_in, re.MULTILINE)
    if not m:
        raise ValueError("OBJZ not found in Makefile.in")
    objs = m.group(1).replace("\\\n", " ").split()
    return [o[:-2] + ".c" for o in objs if o.endswith(".o")]


def parse_bloat(doc: dict) -> list[dict]:
    """Crate rows (name, bytes, share of .text) from `cargo bloat --crates` JSON."""
    text = doc["text-section-size"]
    return [
        {"crate": c["name"], "bytes": c["size"], "share": c["size"] / text if text else None}
        for c in sorted(doc["crates"], key=lambda c: (-c["size"], c["name"]))
    ]


def rows_from_payload(payload: dict, machine_id: str) -> tuple[list[dict], list[dict]]:
    """(binary_size rows, cargo_bloat rows) from a raw `binary-size` payload."""
    size_rows = []
    for p in payload["programs"]:
        size_rows.append(
            {
                "machine": machine_id,
                "subject": p["subject"],
                "opt": p["opt"],
                "bytes": p.get("bytes"),
                "note": p.get("note", ""),
            }
        )
    bloat_rows = []
    for b in payload["bloat"]:
        for r in parse_bloat(b["doc"]):
            bloat_rows.append(
                {"machine": machine_id, "subject": b["subject"], "opt": b["opt"], **r}
            )
    return size_rows, bloat_rows


# ---- measurement ------------------------------------------------------------------------------


def _run(argv, **kw):
    return subprocess.run(argv, check=True, capture_output=True, text=True, **kw)


def _version(argv: list[str]) -> str:
    out = subprocess.run(argv, capture_output=True, text=True, check=False)
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else ""


def smoke_test(exe: Path) -> None:
    fx = paths.ROOT / "crates" / "harness" / "tests" / "fixtures"
    out = subprocess.run(
        [str(exe)], input=(fx / "hello.zlib").read_bytes(), capture_output=True, check=False
    )
    if out.returncode != 0 or out.stdout != (fx / "hello.txt").read_bytes():
        raise RuntimeError(f"smoke test failed for {exe}: rc={out.returncode}")


def build_rust(subject: str, opt: str) -> dict:
    cmd = rust_build_cmd(subject, opt, True)
    _run(cmd)
    exe = target_dir(opt, True) / "release" / f"min-{subject}"
    smoke_test(exe)
    return {
        "subject": subject,
        "opt": opt,
        "bytes": exe.stat().st_size,
        "stripped": True,
        "build_cmd": " ".join(cmd),
        "compiler": _version(["rustc", "--version"]),
    }


def run_bloat(subject: str, opt: str, top: int, gaps: list) -> dict | None:
    _run(rust_build_cmd(subject, opt, False))
    cmd, extra = bloat_cmd(subject, opt, top)
    envv = dict(os.environ, **extra)
    envv["PATH"] = f"{tools.tools_root() / 'bin'}{os.pathsep}{envv['PATH']}"
    res = subprocess.run(cmd, capture_output=True, text=True, check=False, env=envv, cwd=paths.ROOT)
    if res.returncode != 0:
        gaps.append(
            {
                "tool": "cargo-bloat",
                "version": config.load_toml("tools.toml")["cargo-bloat"]["version"],
                "command": " ".join(cmd),
                "error": res.stderr.strip()[-300:],
            }
        )
        return None
    return {"subject": subject, "opt": opt, "doc": json.loads(res.stdout)}


def _cc() -> str:
    return os.environ.get("CC", "cc")


def _strip(exe: Path) -> None:
    _run(["strip", str(exe)])


def build_c_zlib(opt: str) -> dict:
    src = sources.source_root("zlib")
    names = zlib_sources((src / "Makefile.in").read_text())
    out_dir = paths.BUILD / "c-size"
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = out_dir / f"min_zlib-{opt}"
    cmd = [
        _cc(),
        *c_link_flags(platform.system(), opt),
        f"-I{src}",
        str(paths.ROOT / "minimal" / "c" / "min_zlib.c"),
        *[str(src / n) for n in names],
        "-o",
        str(exe),
    ]
    _run(cmd)
    _strip(exe)
    smoke_test(exe)
    return {
        "subject": "zlib",
        "opt": opt,
        "bytes": exe.stat().st_size,
        "stripped": True,
        "build_cmd": " ".join(cmd),
        "sources": names,
        "compiler": _version([_cc(), "--version"]),
    }


def build_c_zng(opt: str) -> dict:
    src = sources.source_root("zng")
    build_dir = paths.BUILD / "c-size" / f"zng-{opt}"
    flags = f"-O{opt}"
    cmake = [
        "cmake",
        "-S",
        str(src),
        "-B",
        str(build_dir / "cmake"),
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_C_FLAGS={flags}",
        f"-DCMAKE_C_FLAGS_RELEASE={flags} -DNDEBUG",
        "-DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON",
        "-DZLIB_COMPAT=OFF",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DZLIB_ENABLE_TESTS=OFF",
        "-DZLIBNG_ENABLE_TESTS=OFF",
        "-DWITH_GTEST=OFF",
        f"-DCMAKE_INSTALL_PREFIX={build_dir / 'install'}",
    ]
    jobs = str(os.cpu_count() or 1)
    _run(cmake, env=dict(os.environ, CC=_cc()))
    _run(["cmake", "--build", str(build_dir / "cmake"), "-j", jobs])
    _run(["cmake", "--install", str(build_dir / "cmake")])
    exe = paths.BUILD / "c-size" / f"min_zng-{opt}"
    cmd = [
        _cc(),
        *c_link_flags(platform.system(), opt),
        f"-I{build_dir / 'install' / 'include'}",
        str(paths.ROOT / "minimal" / "c" / "min_zng.c"),
        str(build_dir / "install" / "lib" / "libz-ng.a"),
        "-o",
        str(exe),
    ]
    _run(cmd)
    _strip(exe)
    smoke_test(exe)
    return {
        "subject": "zng",
        "opt": opt,
        "bytes": exe.stat().st_size,
        "stripped": True,
        "build_cmd": " ".join(cmd),
        "cmake": " ".join(cmake),
        "compiler": _version([_cc(), "--version"]),
    }


def measure_binary(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load_config("full")
    gaps: list = []
    programs, bloat = [], []
    for opt in cfg["size"]["opt_levels"]:
        for s in RUST_PROGRAMS:
            programs.append(build_rust(s, opt))
            b = run_bloat(s, opt, cfg["size"]["bloat_top"], gaps)
            if b:
                bloat.append(b)
        programs.append(build_c_zlib(opt))
        programs.append(build_c_zng(opt))
        programs.append({"subject": "zsys", "opt": opt, "bytes": None, "note": ZSYS_NOTE})
    return {"kind": "binary-size", "programs": programs, "bloat": bloat, "tool_gaps": gaps}


def derive_binary() -> None:
    """Derive binary_size and cargo_bloat from the newest raw size run of each machine."""
    script = "cfbench.size"
    docs = {}
    for p in rawio.list_raw("size", kind="binary-size"):
        d = rawio.load_raw(p)
        cur = docs.get(d["machine"])
        if cur is None or d["timestamp"] > cur[1]["timestamp"]:
            docs[d["machine"]] = (p, d)
    if not docs:
        for name, cols in (("binary_size", BINARY_COLUMNS), ("cargo_bloat", BLOAT_COLUMNS)):
            provenance.write_table(name, cols, [], script=script, raw_files=[], pending=PENDING)
        return
    size_rows, bloat_rows, raw = [], [], []
    for m, (p, d) in sorted(docs.items()):
        raw.append(p)
        s, b = rows_from_payload(d["payload"], m)
        size_rows += s
        bloat_rows += b
    provenance.write_table("binary_size", BINARY_COLUMNS, size_rows, script=script, raw_files=raw)
    provenance.write_table("cargo_bloat", BLOAT_COLUMNS, bloat_rows, script=script, raw_files=raw)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["binary", "derive"])
    a = ap.parse_args(argv)
    cfg = config.load_config()
    if a.cmd == "binary":
        profile = os.environ.get("CFB_PROFILE") or "full"
        environment = env.capture_environment()
        payload = measure_binary(cfg)
        path = rawio.write_raw(
            "size",
            payload,
            machine=machine.detect_machine(),
            profile=profile,
            script="cfbench.size",
            environment=environment,
        )
        print(path)
        if profile == "full":
            derive_binary()
    else:
        derive_binary()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
