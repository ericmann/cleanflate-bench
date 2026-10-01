"""Runtime dependencies (cargo tree) and security advisories (cargo audit) per Rust subject."""

import json
import re
import subprocess
import sys
from pathlib import Path

from cfbench import config, env, paths, provenance, rawio, sources, tools

SUBJECT_PACKAGES = {
    "cf": ["cleanflate"],
    "zrs": ["libz-rs-sys", "zlib-rs"],
    "mox": ["miniz_oxide"],
}
COLUMNS = [
    "subject",
    "package",
    "direct_count",
    "transitive_count",
    "direct",
    "transitive",
    "advisories",
    "note",
]
PENDING = "no deps scan; run make size"
_LINE = re.compile(r"^(\d+)(\S+) v(\S+)")


def parse_tree(text: str) -> dict:
    """Parse `cargo tree --prefix depth`: direct (depth 1) and transitive (depth >= 1) sets."""
    direct: set[str] = set()
    transitive: set[str] = set()
    for line in text.splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        depth, name, version = int(m.group(1)), m.group(2), m.group(3)
        if depth == 0:
            continue
        pkg = f"{name}@{version}"
        transitive.add(pkg)
        if depth == 1:
            direct.add(pkg)
    return {"direct": sorted(direct), "transitive": sorted(transitive)}


def parse_audit(doc: dict) -> list[dict]:
    """Every advisory in `cargo audit --json` output: vulnerabilities and warnings."""
    found = []
    for v in doc.get("vulnerabilities", {}).get("list", []):
        found.append(
            {
                "id": v["advisory"]["id"],
                "package": v["package"]["name"],
                "version": v["package"]["version"],
                "kind": "vulnerability",
                "title": v["advisory"].get("title", ""),
            }
        )
    for kind, items in doc.get("warnings", {}).items():
        for w in items:
            adv = w.get("advisory") or {}
            found.append(
                {
                    "id": adv.get("id", ""),
                    "package": w["package"]["name"],
                    "version": w["package"]["version"],
                    "kind": kind,
                    "title": adv.get("title", ""),
                }
            )
    return sorted(found, key=lambda a: (a["package"], a["id"]))


def filter_advisories(advisories: list[dict], dependency_set: set[str]) -> list[dict]:
    """Keep advisories whose package@version is in a subject's dependency set."""
    return [a for a in advisories if f"{a['package']}@{a['version']}" in dependency_set]


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=paths.ROOT)
    return out.returncode, out.stdout, out.stderr


def run_audit(runner=_run) -> tuple[list[dict] | None, dict, list]:
    """(advisories or None on failure, database info, tool gaps)."""
    version = config.load_toml("tools.toml")["cargo-audit"]["version"]
    cmd = [str(tools.binary_path("cargo-audit")), "audit", "--json"]
    try:
        rc, out, err = runner(cmd)
        # cargo-audit exits 1 when it finds vulnerabilities but still prints the JSON report
        doc = json.loads(out)
        return parse_audit(doc), doc.get("database", {}), []
    except Exception as e:  # noqa: BLE001 - tool-gap protocol
        detail = locals().get("err") or str(e)
        gap = {
            "tool": "cargo-audit",
            "version": version,
            "command": " ".join(cmd),
            "error": str(detail).strip()[-300:],
        }
        return None, {}, [gap]


def collect(metadata: dict | None = None, runner=_run, audit_runner=_run) -> dict:
    metadata = metadata or sources.cargo_metadata()
    versions = {p["name"]: p["version"] for p in metadata["packages"]}
    advisories, database, gaps = run_audit(audit_runner)
    rows = []
    for subject, pkgs in SUBJECT_PACKAGES.items():
        for name in pkgs:
            rc, out, err = runner(
                ["cargo", "tree", "-p", f"{name}@{versions[name]}", "-e", "normal",
                 "--prefix", "depth", "--locked"]
            )  # fmt: skip
            if rc != 0:
                raise RuntimeError(f"cargo tree failed for {name}: {err.strip()[-200:]}")
            tree = parse_tree(out)
            dep_set = set(tree["transitive"]) | {f"{name}@{versions[name]}"}
            note = ""
            hits: list[dict] = []
            if advisories is None:
                note = "advisories unavailable: cargo-audit tool gap"
            else:
                hits = filter_advisories(advisories, dep_set)
            rows.append(
                {
                    "subject": subject,
                    "package": f"{name}@{versions[name]}",
                    "direct_count": len(tree["direct"]),
                    "transitive_count": len(tree["transitive"]),
                    "direct": ";".join(tree["direct"]),
                    "transitive": ";".join(tree["transitive"]),
                    "advisories": None if advisories is None else ";".join(a["id"] for a in hits),
                    "note": note,
                    "advisory_details": hits,
                }
            )
    return {"kind": "deps", "rows": rows, "audit_database": database, "tool_gaps": gaps}


def _latest() -> tuple[Path, dict] | None:
    files = rawio.list_raw("size", machine="any", kind="deps")
    if not files:
        return None
    return files[-1], rawio.load_raw(files[-1])


def derive_table() -> None:
    latest = _latest()
    script = "cfbench.deps"
    if latest is None:
        provenance.write_table("deps", COLUMNS, [], script=script, raw_files=[], pending=PENDING)
        return
    p, doc = latest
    provenance.write_table("deps", COLUMNS, doc["payload"]["rows"], script=script, raw_files=[p])


def main() -> int:
    payload = collect()
    path = rawio.write_raw(
        "size",
        payload,
        machine="any",
        profile="full",
        script="cfbench.deps",
        environment=env.capture_environment(),
    )
    derive_table()
    print(path)
    for g in payload["tool_gaps"]:
        print(f"tool gap: {g['tool']}: {g['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
