"""Count `unsafe` constructs in a Rust crate, ignoring comments and string literals."""

import json
import re
import subprocess
import sys
from pathlib import Path

from cfbench import config, env, paths, provenance, rawio, sources, tools

EXCLUDED_DIRS = {"tests", "benches", "examples"}
COUNT_KEYS = ["unsafe_blocks", "unsafe_fns", "unsafe_impls", "unsafe_traits", "target_feature"]

_BLOCK = re.compile(r"\bunsafe\s*\{")
_FN = re.compile(r"\bunsafe\s+(?:const\s+)?(?:extern\s*(?:\"\"\s*)?)?fn\b")
_IMPL = re.compile(r"\bunsafe\s+impl\b")
_TRAIT = re.compile(r"\bunsafe\s+trait\b")
_TARGET_FEATURE = re.compile(r"#\s*\[\s*target_feature\b")
_FORBID = re.compile(r"#!\[\s*forbid\s*\([^\]]*\bunsafe_code\b")
_DENY = re.compile(r"#!\[\s*deny\s*\([^\]]*\bunsafe_code\b")


def strip_comments_and_strings(src: str) -> str:
    """Blank out comments; keep string literals as empty `""`. Newlines are preserved."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        two = src[i : i + 2]
        if two == "//":
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif two == "/*":
            depth, i = 1, i + 2
            while i < n and depth:
                if src.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif src.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    if src[i] == "\n":
                        out.append("\n")
                    i += 1
        elif c == "r" and re.match(r'r#*"', src[i:]) and (i == 0 or not src[i - 1].isalnum()):
            m = re.match(r'r(#*)"', src[i:])
            hashes = m.group(1)
            end = src.find('"' + hashes, i + m.end())
            end = n if end < 0 else end + 1 + len(hashes)
            out.append('""')
            out.append("\n" * src.count("\n", i, end))
            i = end
        elif c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            out.append('""')
            out.append("\n" * src.count("\n", i, min(j, n)))
            i = j + 1
        elif c == "'":
            # a char literal ('x', '\n', '\u{..}') versus a lifetime ('a)
            m = re.match(r"'(?:\\.[^']*|[^\\'])'", src[i:])
            if m:
                out.append("''")
                i += m.end()
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def count_text(src: str) -> dict:
    s = strip_comments_and_strings(src)
    return {
        "unsafe_blocks": len(_BLOCK.findall(s)),
        "unsafe_fns": len(_FN.findall(s)),
        "unsafe_impls": len(_IMPL.findall(s)),
        "unsafe_traits": len(_TRAIT.findall(s)),
        "target_feature": len(_TARGET_FEATURE.findall(s)),
    }


def scan_crate(root: Path) -> dict:
    root = Path(root)
    files = {}
    for p in sorted(root.rglob("*.rs")):
        rel = p.relative_to(root)
        if rel.parts[0] in EXCLUDED_DIRS:
            continue
        files[rel.as_posix()] = count_text(p.read_text(encoding="utf-8", errors="replace"))
    totals = {k: sum(f[k] for f in files.values()) for k in COUNT_KEYS}
    lib = root / "src" / "lib.rs"
    lib_src = strip_comments_and_strings(lib.read_text(encoding="utf-8")) if lib.exists() else ""
    return {
        "files": files,
        "totals": totals,
        "forbid_unsafe_code": bool(_FORBID.search(lib_src)),
        "deny_unsafe_code": bool(_DENY.search(lib_src)),
    }


# ---- full unsafe surface: subject crates plus runtime dependencies ---------------------------

C_NOTE = "C: entire codebase memory-unsafe by language"
GEIGER_NOTE = (
    "geiger counts unsafe expressions in code reachable (used) or not (unused) from the program"
)
UNSAFE_COLUMNS = [
    "subject",
    "crate",
    "version",
    "role",
    "forbid_unsafe_code",
    "unsafe_blocks",
    "unsafe_fns",
    "unsafe_impls",
    "unsafe_traits",
    "target_feature_attrs",
    "geiger_used",
    "geiger_unused",
    "note",
]
RUST_SUBJECT_CRATES = {
    "cf": ["cleanflate"],
    "zrs": ["zlib-rs", "libz-rs-sys"],
    "mox": ["miniz_oxide"],
}
C_SUBJECTS = ["zlib", "zng", "zsys"]
MIN_PROGRAM = {"cf": "min-cf", "zrs": "min-zrs", "mox": "min-mox"}
PENDING = "no unsafe scan; run make size"


def _runtime_deps(metadata: dict, roots: list[str]) -> list[dict]:
    """Packages reachable from `roots` through normal (non-dev, non-build) dependencies."""
    by_name = {p["name"]: p for p in metadata["packages"]}
    by_id = {p["id"]: p for p in metadata["packages"]}
    nodes = {n["id"]: n for n in metadata["resolve"]["nodes"]}
    seen: set[str] = set()
    stack = [by_name[r]["id"] for r in roots if r in by_name]
    while stack:
        pid = stack.pop()
        for dep in nodes.get(pid, {}).get("deps", []):
            normal = any(k.get("kind") is None for k in dep.get("dep_kinds", [{"kind": None}]))
            if normal and dep["pkg"] not in seen:
                seen.add(dep["pkg"])
                stack.append(dep["pkg"])
    return sorted(
        (by_id[i] for i in seen if by_id[i]["name"] not in roots), key=lambda p: p["name"]
    )


def _row(subject: str, name: str, version: str, role: str, scan: dict) -> dict:
    t = scan["totals"]
    return {
        "subject": subject,
        "crate": name,
        "version": version,
        "role": role,
        "forbid_unsafe_code": scan["forbid_unsafe_code"],
        "deny_unsafe_code": scan["deny_unsafe_code"],
        "unsafe_blocks": t["unsafe_blocks"],
        "unsafe_fns": t["unsafe_fns"],
        "unsafe_impls": t["unsafe_impls"],
        "unsafe_traits": t["unsafe_traits"],
        "target_feature_attrs": t["target_feature"],
        "geiger_used": None,
        "geiger_unused": None,
        "note": "",
    }


def scan_subject(subject: str, metadata: dict | None = None) -> list[dict]:
    """One row per subject crate and per normal runtime dependency (grep-based counts)."""
    if subject in C_SUBJECTS:
        return [
            {
                "subject": subject,
                "crate": subject,
                "version": "",
                "role": "subject",
                "note": C_NOTE,
            }
        ]
    metadata = metadata or sources.cargo_metadata()
    names = RUST_SUBJECT_CRATES[subject]
    pkgs = {p["name"]: p for p in metadata["packages"]}
    roots = {names[0]: sources.source_root(subject, metadata)}
    for extra, name in zip(sources.extra_roots(subject, metadata), names[1:], strict=False):
        roots[name] = extra
    rows = [
        _row(subject, n, pkgs[n]["version"], "subject", scan_crate(r)) for n, r in roots.items()
    ]
    for dep in _runtime_deps(metadata, names):
        rows.append(
            _row(
                subject,
                dep["name"],
                dep["version"],
                "dependency",
                scan_crate(Path(dep["manifest_path"]).parent),
            )
        )
    return rows


def geiger_counts(subject: str, runner=None) -> tuple[dict, list]:
    """{crate name: (used unsafe exprs, unused unsafe exprs)} and tool gaps from cargo-geiger."""
    runner = runner or _run_geiger
    version = config.load_toml("tools.toml")["cargo-geiger"]["version"]
    manifest = paths.ROOT / "crates" / MIN_PROGRAM[subject] / "Cargo.toml"
    cmd = [
        str(tools.binary_path("cargo-geiger")),
        "geiger",
        "--output-format",
        "Json",
        "--manifest-path",
        str(manifest),
    ]
    try:
        rc, out, err = runner(cmd)
        if rc != 0:
            raise RuntimeError(err.strip()[-300:] or f"exit {rc}")
        first = next(line for line in out.splitlines() if line.startswith('{"packages"'))
        doc = json.loads(first)
        counts = {
            p["package"]["id"]["name"]: (
                p["unsafety"]["used"]["exprs"]["unsafe_"],
                p["unsafety"]["unused"]["exprs"]["unsafe_"],
            )
            for p in doc["packages"]
        }
        return counts, []
    except Exception as e:  # noqa: BLE001 - tool-gap protocol: record and continue
        gap = {
            "tool": "cargo-geiger",
            "version": version,
            "command": " ".join(cmd),
            "error": str(e),
        }
        return {}, [gap]


def _run_geiger(cmd: list[str]) -> tuple[int, str, str]:
    out = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=paths.ROOT)
    return out.returncode, out.stdout, out.stderr


def collect(metadata: dict | None = None, geiger_runner=None) -> dict:
    metadata = metadata or sources.cargo_metadata()
    rows: list[dict] = []
    gaps: list = []
    for subject in [*RUST_SUBJECT_CRATES, *C_SUBJECTS]:
        subject_rows = scan_subject(subject, metadata)
        if subject in RUST_SUBJECT_CRATES:
            counts, g = geiger_counts(subject, geiger_runner)
            gaps += g
            for r in subject_rows:
                if r["crate"] in counts:
                    r["geiger_used"], r["geiger_unused"] = counts[r["crate"]]
        rows += subject_rows
    return {"kind": "unsafe", "rows": rows, "tool_gaps": gaps}


def _latest_unsafe_doc() -> tuple[Path, dict] | None:
    files = rawio.list_raw("size", machine="any", kind="unsafe")
    if not files:
        return None
    p = files[-1]
    return p, rawio.load_raw(p)


def status_from_latest_raw(subject: str) -> dict | None:
    """The `unsafe_status` for subjects.lock.json, summed over the subject's own crates."""
    latest = _latest_unsafe_doc()
    if latest is None:
        return None
    rows = [
        r
        for r in latest[1]["payload"]["rows"]
        if r["subject"] == subject and r["role"] == "subject"
    ]
    if not rows:
        return None
    return {
        "unsafe_blocks": sum(r["unsafe_blocks"] for r in rows),
        "unsafe_fns": sum(r["unsafe_fns"] for r in rows),
        "unsafe_impls": sum(r["unsafe_impls"] for r in rows),
        "unsafe_traits": sum(r["unsafe_traits"] for r in rows),
        "target_feature": sum(r["target_feature_attrs"] for r in rows),
        "forbid_unsafe_code": all(r["forbid_unsafe_code"] for r in rows),
        "deny_unsafe_code": all(r["deny_unsafe_code"] for r in rows),
        "roots": [r["crate"] for r in rows],
    }


def derive_table() -> None:
    latest = _latest_unsafe_doc()
    if latest is None:
        provenance.write_table(
            "unsafe",
            UNSAFE_COLUMNS,
            [],
            script="cfbench.unsafe_scan",
            raw_files=[],
            pending=PENDING,
        )
        return
    p, doc = latest
    provenance.write_table(
        "unsafe",
        UNSAFE_COLUMNS,
        doc["payload"]["rows"],
        script="cfbench.unsafe_scan",
        raw_files=[p],
    )


def main() -> int:
    payload = collect()
    path = rawio.write_raw(
        "size",
        payload,
        machine="any",
        profile="full",
        script="cfbench.unsafe_scan",
        environment=env.capture_environment(),
    )
    derive_table()
    print(path)
    for g in payload["tool_gaps"]:
        print(f"tool gap: {g['tool']}: {g['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
