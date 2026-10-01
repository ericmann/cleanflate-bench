"""Build the pinned C subject libraries (SPEC 2.3): zlib, zlib-nohw and zng."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from cfbench import config, download, paths

ZLIB_DEFAULT_CFLAGS = "-O3"
NOHW_UNDEF = "-U__ARM_FEATURE_CRC32"
IDS = ["zlib", "zlib-nohw", "zng"]


def _sub_cfg(name: str) -> dict:
    return config.load_toml("subjects.toml")[name]


def source_dir(name: str) -> Path:
    cfg = _sub_cfg(name)
    return paths.THIRD_PARTY / "src" / f"{name}-{cfg['version']}"


def ensure_source(name: str) -> tuple[Path, str]:
    cfg = _sub_cfg(name)
    tarball = download.fetch(cfg["url"], cfg["sha256"])
    dest = source_dir(name)
    if not (dest / ".cfb-extracted").exists():
        download.extract(tarball, dest)
        (dest / ".cfb-extracted").write_text(cfg["sha256"])
    return dest, cfg["sha256"]


def nohw_plan(arch: str) -> dict:
    """The zlib hardware-CRC-disabled control (SPEC 2.3)."""
    if arch in ("aarch64", "arm64"):
        return {
            "cflags": f"{ZLIB_DEFAULT_CFLAGS} {NOHW_UNDEF}",
            "control_identical_to_default": False,
            "note": "ARMv8 CRC32 undefined via -U__ARM_FEATURE_CRC32",
        }
    return {
        "cflags": ZLIB_DEFAULT_CFLAGS,
        "control_identical_to_default": True,
        "note": "stock zlib has no x86_64 hardware-CRC path",
    }


def parse_cmake_cache(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        if line.startswith(("//", "#")) or "=" not in line or ":" not in line:
            continue
        key, value = line.split("=", 1)
        name = key.split(":", 1)[0]
        if "-" not in name and name.startswith(("WITH_", "CMAKE_C_FLAGS")):
            out[name] = value
    return dict(sorted(out.items()))


def is_up_to_date(info_path: Path, expected: dict) -> bool:
    if not info_path.exists():
        return False
    try:
        info = json.loads(info_path.read_text())
    except ValueError:
        return False
    return all(info.get(k) == v for k, v in expected.items())


def _compiler() -> tuple[str, str]:
    cc = os.environ.get("CC", "cc")
    out = subprocess.run([cc, "--version"], capture_output=True, text=True, check=False)
    first = (out.stdout or out.stderr).strip().splitlines()
    return cc, first[0] if first else ""


def _run(argv, cwd=None, env=None):
    subprocess.run(argv, cwd=cwd, env=env, check=True)


def _makefile_cflags(makefile: Path) -> str:
    for line in makefile.read_text().splitlines():
        if line.startswith("CFLAGS="):
            return line.split("=", 1)[1].strip()
    return ""


def _write_info(out: Path, info: dict) -> None:
    (out / "build-info.json").write_text(json.dumps(info, sort_keys=True, indent=1) + "\n")


def _build_zlib(bid: str, force: bool) -> Path:
    arch = platform.machine()
    out = paths.BUILD / "c" / bid
    src, sha = ensure_source("zlib")
    plan = nohw_plan(arch) if bid == "zlib-nohw" else {"cflags": None}
    expected = {
        "id": bid,
        "source_sha256": sha,
        "recipe": {"configure": ["--static"], "env_cflags": plan["cflags"]},
    }
    if not force and is_up_to_date(out / "build-info.json", expected):
        return out
    if out.exists():
        shutil.rmtree(out)
    work = out / "src"
    shutil.copytree(src, work)
    env = dict(os.environ)
    if plan["cflags"] is not None:
        env["CFLAGS"] = plan["cflags"]
    else:
        env.pop("CFLAGS", None)
    cc, cc_version = _compiler()
    env["CC"] = cc
    args = ["--static", f"--prefix={out}"]
    _run(["./configure", *args], cwd=work, env=env)
    cflags = _makefile_cflags(work / "Makefile")
    jobs = str(os.cpu_count() or 1)
    _run(["make", f"-j{jobs}", "libz.a", "install"], cwd=work, env=env)
    libname = "libcfbz_nohw.a" if bid == "zlib-nohw" else "libcfbz_default.a"
    shutil.copy(out / "lib" / "libz.a", out / "lib" / libname)
    info = {
        **expected,
        "version": _sub_cfg("zlib")["version"],
        "compiler": cc,
        "compiler_version": cc_version,
        "cflags": cflags,
        "configure_args": args,
        "arch": arch,
        "built_from": str(src.relative_to(paths.ROOT)),
    }
    if bid == "zlib-nohw":
        info["control_identical_to_default"] = plan["control_identical_to_default"]
        info["control_note"] = plan["note"]
    _write_info(out, info)
    return out


def _build_zng(force: bool) -> Path:
    arch = platform.machine()
    out = paths.BUILD / "c" / "zng"
    src, sha = ensure_source("zng")
    opts = [
        "-DCMAKE_BUILD_TYPE=Release",
        "-DZLIB_COMPAT=OFF",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DZLIB_ENABLE_TESTS=OFF",
        "-DZLIBNG_ENABLE_TESTS=OFF",
        "-DWITH_GTEST=OFF",
    ]
    expected = {"id": "zng", "source_sha256": sha, "recipe": {"cmake": opts}}
    if not force and is_up_to_date(out / "build-info.json", expected):
        return out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    cmake_dir = out / "cmake"
    cc, cc_version = _compiler()
    env = dict(os.environ, CC=cc)
    _run(
        ["cmake", "-S", str(src), "-B", str(cmake_dir), *opts, f"-DCMAKE_INSTALL_PREFIX={out}"],
        env=env,
    )
    jobs = str(os.cpu_count() or 1)
    _run(["cmake", "--build", str(cmake_dir), "-j", jobs], env=env)
    _run(["cmake", "--install", str(cmake_dir)], env=env)
    cache = parse_cmake_cache((cmake_dir / "CMakeCache.txt").read_text())
    info = {
        **expected,
        "version": _sub_cfg("zng")["version"],
        "compiler": cc,
        "compiler_version": cc_version,
        "cflags": cache.get("CMAKE_C_FLAGS_RELEASE", ""),
        "cmake_options": cache,
        "arch": arch,
        "built_from": str(src.relative_to(paths.ROOT)),
    }
    _write_info(out, info)
    return out


def build(bid: str, force: bool = False) -> Path:
    if bid in ("zlib", "zlib-nohw"):
        return _build_zlib(bid, force)
    if bid == "zng":
        return _build_zng(force)
    raise ValueError(f"unknown C subject {bid!r}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("ids", nargs="*", default=IDS)
    a = ap.parse_args(argv)
    for bid in a.ids:
        print(build(bid, force=a.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
