"""Build provenance: hardware-CRC determination, unsafe status, subjects.lock.json (SPEC 2.3)."""

import json
import os
import platform
import re
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

from cfbench import (
    cleanflate_src,
    config,
    env,
    machine,
    paths,
    rawio,
    sources,
    subjects,
    unsafe_scan,
)

LOCK_SCHEMA = "cfbench.subjects-lock/1"
LOCK_PATH = paths.ROOT / "subjects.lock.json"
NATIVE_RUSTFLAGS = "-C target-cpu=native"
SUBJECT_IDS = ["cf", "zlib", "zlib-nohw", "zng", "zrs", "mox", "zsys"]

_ARM_CRC = re.compile(r"^crc32[bhwx]$")
_ARM_CRC_C = re.compile(r"^crc32c[bhwx]$")
_PCLMUL = re.compile(r"^v?pclmul(qdq|lqlqdq|hqhqdq|lqhqdq|hqlqdq)$")
_X86_CRC_C = re.compile(r"^crc32[bwlq]$")
_RAW_BYTES = re.compile(r"(?:[0-9a-f]{2}(?: |$))+|[0-9a-f]{8}")
_DISPATCH_SYM = re.compile(r"crc32_(armv8|pclmulqdq|vpclmulqdq)")


def mnemonics(disasm: str) -> Counter:
    """Count instruction mnemonics from `objdump -d --no-show-raw-insn` (GNU or LLVM) text."""
    counts: Counter = Counter()
    for line in disasm.splitlines():
        if ":" not in line or "\t" not in line:
            continue
        head, _, rest = line.partition(":")
        if not re.fullmatch(r"\s*[0-9a-f]+", head):
            continue
        segs = [x for x in rest.split("\t") if x.strip()]
        if len(segs) > 1 and _RAW_BYTES.fullmatch(segs[0].strip()):
            segs = segs[1:]
        if segs:
            counts[segs[0].split()[0].lower()] += 1
    return counts


def hw_crc(arch: str, disasm: str | None, symbols: list[str], hints: dict) -> dict:
    """Determine whether a build contains hardware CRC-32 code (SPEC 2.3).

    `hints` may carry `arm_feature_crc32` (compiler probe), `cmake_options` (zng build-info),
    `runtime_dispatch_source` (bool from inspecting source) and `note`.
    """
    method: list[str] = []
    evidence: dict = {}
    notes = [hints["note"]] if hints.get("note") else []
    aarch64 = arch in ("aarch64", "arm64")

    compiled_in = None
    if disasm is not None:
        method.append("disassembly")
        m = mnemonics(disasm)
        if aarch64:
            hw = sum(c for k, c in m.items() if _ARM_CRC.match(k))
            c32c = sum(c for k, c in m.items() if _ARM_CRC_C.match(k))
            evidence.update({"crc32_instructions": hw, "crc32c_instructions": c32c})
        else:
            hw = sum(c for k, c in m.items() if _PCLMUL.match(k))
            c32c = sum(c for k, c in m.items() if _X86_CRC_C.match(k))
            evidence.update({"pclmul_instructions": hw, "sse42_crc32c_instructions": c32c})
        compiled_in = hw > 0
        if c32c:
            notes.append("CRC32C (Castagnoli) instructions present; not the gzip polynomial")
    else:
        notes.append("no disassembly available; compiled_in is unknown")

    if "arm_feature_crc32" in hints and hints["arm_feature_crc32"] is not None:
        method.append("compiler-probe")
        evidence["__ARM_FEATURE_CRC32"] = bool(hints["arm_feature_crc32"])
    if hints.get("cmake_options"):
        method.append("cmake-options")
        evidence["cmake_options"] = {
            k: v
            for k, v in sorted(hints["cmake_options"].items())
            if k.startswith("WITH_") and "-" not in k
        }

    dispatch_syms = sorted({s for s in symbols if _DISPATCH_SYM.search(s)})
    runtime_dispatch = None
    if symbols:
        method.append("symbols")
        evidence["dispatch_symbols"] = dispatch_syms
        runtime_dispatch = bool(dispatch_syms)
    if hints.get("runtime_dispatch_source") is not None:
        method.append("source")
        evidence["runtime_dispatch_source"] = bool(hints["runtime_dispatch_source"])
        runtime_dispatch = bool(runtime_dispatch) or bool(hints["runtime_dispatch_source"])
    if runtime_dispatch is None and hints.get("no_dispatch"):
        runtime_dispatch = False
    return {
        "compiled_in": compiled_in,
        "runtime_dispatch": runtime_dispatch,
        "evidence": evidence,
        "method": method,
        "note": "; ".join(notes),
    }


def merge_lock(existing: dict | None, static: dict, machine_id: str, entry: dict) -> dict:
    """Refresh the static sections and this machine's entry; keep other machines as they are."""
    lock = dict(existing or {})
    machines = dict(lock.get("machines", {}))
    machines[machine_id] = entry
    lock.update(static)
    lock["schema"] = LOCK_SCHEMA
    lock["machines"] = dict(sorted(machines.items()))
    return lock


def rust_profile(cargo_toml: Path | None = None) -> dict:
    with open(cargo_toml or paths.ROOT / "Cargo.toml", "rb") as f:
        rel = tomllib.load(f)["profile"]["release"]
    return {
        "opt-level": rel["opt-level"],
        "lto": rel["lto"],
        "codegen-units": rel["codegen-units"],
        "panic": rel.get("panic", "default"),
    }


def lock_checksums(cargo_lock: Path | None = None) -> dict[str, str]:
    with open(cargo_lock or paths.ROOT / "Cargo.lock", "rb") as f:
        pkgs = tomllib.load(f)["package"]
    return {p["name"]: p.get("checksum", "") for p in pkgs if "checksum" in p}


def static_section() -> dict:
    subj = config.load_toml("subjects.toml")
    rounds = cleanflate_src.rounds()
    primary = next(r for r in rounds["rounds"] if r["round"] == rounds["primary_round"])
    sums = lock_checksums()
    with open(paths.ROOT / "rust-toolchain.toml", "rb") as f:
        channel = tomllib.load(f)["toolchain"]["channel"]
    return {
        "rust_toolchain": channel,
        "rust_profile": rust_profile(),
        "subjects": {
            "cf": {"tag": primary["tag"], "git_sha": primary["sha"]},
            "zlib": {k: subj["zlib"][k] for k in ("version", "url", "sha256")},
            "zng": {k: subj["zng"][k] for k in ("version", "url", "sha256")},
            "zrs": {
                "crate": subj["zrs"]["crate"],
                "version": subj["zrs"]["version"],
                "checksum": sums.get(subj["zrs"]["crate"], ""),
                "core_crate": subj["zrs"]["core_crate"],
                "core_checksum": sums.get(subj["zrs"]["core_crate"], ""),
            },
            "mox": {
                "crate": subj["mox"]["crate"],
                "version": subj["mox"]["version"],
                "checksum": sums.get(subj["mox"]["crate"], ""),
            },
            "zsys": {"note": "platform zlib, dynamically linked as installed (SPEC 2.2)"},
        },
    }


# ---- tool plumbing -------------------------------------------------------------------------


def _run(argv: list[str], **kw) -> str | None:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, check=False, **kw)
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def disassemble(path: Path, gaps: list) -> str | None:
    out = _run(["objdump", "-d", "--no-show-raw-insn", str(path)])
    if out is None:
        gaps.append(
            {"tool": "objdump", "version": None, "command": f"objdump -d {path}", "error": "failed"}
        )
    return out


def symbols_of(path: Path, gaps: list) -> list[str]:
    out = _run(["nm", str(path)])
    if out is None:
        gaps.append({"tool": "nm", "version": None, "command": f"nm {path}", "error": "failed"})
        return []
    syms = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and not line.rstrip().endswith(":"):
            syms.append(parts[-1])
    return syms


def arm_crc_probe(cc: str, cflags: str) -> bool | None:
    out = _run([cc, *cflags.split(), "-dM", "-E", "-"], input="")
    if out is None:
        return None
    return "__ARM_FEATURE_CRC32" in out


def _build_info(bid: str) -> dict:
    return json.loads((paths.BUILD / "c" / bid / "build-info.json").read_text())


def _c_lib(bid: str) -> Path:
    name = {"zlib": "libcfbz_default.a", "zlib-nohw": "libcfbz_nohw.a", "zng": "libz-ng.a"}[bid]
    return paths.BUILD / "c" / bid / "lib" / name


def release_bin(bid: str) -> Path:
    return paths.ROOT / "target" / "release" / f"cfb-{bid}"


def _zrs_source_dispatch(root: Path) -> bool | None:
    d = root / "src" / "crc32"
    if not d.is_dir():
        return None
    text = "\n".join(p.read_text(errors="replace") for p in d.rglob("*.rs"))
    return bool(
        re.search(r"is_x86_feature_detected|is_aarch64_feature_detected|cpu_features", text)
    )


def _unsafe_status(subject: str, metadata: dict) -> dict:
    roots = [sources.source_root(subject, metadata), *sources.extra_roots(subject, metadata)]
    scans = [unsafe_scan.scan_crate(r) for r in roots]
    totals = {k: sum(s["totals"][k] for s in scans) for k in unsafe_scan.COUNT_KEYS}
    return {
        **totals,
        "forbid_unsafe_code": all(s["forbid_unsafe_code"] for s in scans),
        "deny_unsafe_code": all(s["deny_unsafe_code"] for s in scans),
        "roots": [r.name for r in roots],
    }


def _zsys_info(gaps: list) -> tuple[Path | None, dict]:
    info: dict = {"library": None, "package": None, "version": None}
    if platform.system() == "Darwin":
        info["note"] = "Apple libz lives in the dyld shared cache; no file to disassemble"
        return None, info
    out = _run(["ldconfig", "-p"]) or ""
    for line in out.splitlines():
        if "libz.so.1 " in line and "=>" in line:
            info["library"] = line.split("=>")[-1].strip()
            break
    pkg = _run(["dpkg-query", "-W", "zlib1g"])
    if pkg:
        info["package"] = pkg.strip().splitlines()[0].replace("\t", " ")
    else:
        rpm = _run(["rpm", "-q", "zlib"])
        info["package"] = rpm.strip() if rpm else None
    if info["library"]:
        return Path(info["library"]).resolve(), info
    gaps.append({"tool": "ldconfig", "version": None, "command": "ldconfig -p", "error": "no libz"})
    return None, info


def collect(metadata: dict | None = None) -> tuple[dict, list]:
    """Gather this machine's build entries. Returns (entry, tool_gaps)."""
    metadata = metadata or sources.cargo_metadata()
    arch = platform.machine()
    gaps: list = []
    builds: dict = {}
    cc_info = {}
    for bid in ("zlib", "zlib-nohw", "zng"):
        bi = _build_info(bid)
        cc_info[bid] = bi
        lib = _c_lib(bid)
        disasm = disassemble(lib, gaps)
        syms = symbols_of(lib, gaps)
        hints: dict = {}
        if bid == "zng":
            hints["cmake_options"] = bi.get("cmake_options", {})
        else:
            probe = None
            if arch in ("aarch64", "arm64"):
                probe = arm_crc_probe(bi["compiler"], bi["cflags"])
            hints["arm_feature_crc32"] = probe
            hints["no_dispatch"] = True
            if bid == "zlib-nohw" and bi.get("control_identical_to_default"):
                hints["note"] = bi.get("control_note", "")
        builds[bid] = {
            "compiler": bi["compiler"],
            "compiler_version": bi["compiler_version"],
            "flags": bi["cflags"],
            "hw_crc": hw_crc(arch, disasm, syms, hints),
            "target_cpu": "generic",
        }
    for bid in ("cf", "zrs", "mox"):
        exe = release_bin(bid)
        disasm = disassemble(exe, gaps) if exe.exists() else None
        syms = symbols_of(exe, gaps) if exe.exists() else []
        hints = {"no_dispatch": bid != "zrs"}
        if bid == "zrs":
            hints["runtime_dispatch_source"] = _zrs_source_dispatch(
                sources.source_root("zrs", metadata)
            )
        rc = _run(["rustc", "--version"]) or ""
        builds[bid] = {
            "compiler": "rustc",
            "compiler_version": rc.strip(),
            "flags": "release profile from root Cargo.toml (opt-level 3, lto fat, codegen-units 1)",
            "hw_crc": hw_crc(arch, disasm, [s for s in syms if "crc32" in s], hints),
            "unsafe_status": _unsafe_status(bid, metadata),
            "target_cpu": "generic",
        }
    for bid in ("cf", "zrs", "mox"):
        exe = subjects.binary_path(bid, "native")
        if not exe.exists():
            continue
        disasm = disassemble(exe, gaps)
        syms = symbols_of(exe, gaps)
        hints = {"no_dispatch": bid != "zrs"}
        if bid == "zrs":
            hints["runtime_dispatch_source"] = _zrs_source_dispatch(
                sources.source_root("zrs", metadata)
            )
        entry = dict(builds[bid])
        entry.update(
            flags="RUSTFLAGS='-C target-cpu=native' plus the release profile from root Cargo.toml",
            hw_crc=hw_crc(arch, disasm, [x for x in syms if "crc32" in x], hints),
            target_cpu="native",
            rustflags=NATIVE_RUSTFLAGS,
        )
        builds[subjects.native_label(bid)] = entry
    zpath, zinfo = _zsys_info(gaps)
    zdis = disassemble(zpath, gaps) if zpath else None
    zsyms = symbols_of(zpath, gaps) if zpath else []
    ver = _run([str(release_bin("zsys")), "info"])
    zinfo["zlib_version"] = json.loads(ver)["impl_version"] if ver else None
    builds["zsys"] = {
        "compiler": None,
        "compiler_version": None,
        "flags": None,
        "hw_crc": hw_crc(arch, zdis, zsyms, {"note": zinfo.get("note", ""), "no_dispatch": True}),
        "system_library": zinfo,
        "target_cpu": "generic",
    }
    return {"builds": dict(sorted(builds.items()))}, gaps


def main() -> int:
    config.load_config()  # validates CFB_PROFILE
    profile = os.environ.get("CFB_PROFILE") or "full"
    m = machine.detect_machine()
    entry, gaps = collect()
    environment = env.capture_environment()
    path = rawio.write_raw(
        "pins",
        {"kind": "pins", "entry": entry, "tool_gaps": gaps},
        machine=m,
        profile=profile,
        script="cfbench.pins",
        environment=environment,
    )
    doc = rawio.load_raw(path)
    entry = {"recorded_at": doc["timestamp"], **entry}
    existing = json.loads(LOCK_PATH.read_text()) if LOCK_PATH.exists() else None
    lock = merge_lock(existing, static_section(), m, entry)
    if profile == "full":
        LOCK_PATH.write_text(json.dumps(lock, sort_keys=True, indent=1) + "\n")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
