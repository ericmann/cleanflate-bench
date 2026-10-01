"""Per-function complexity distributions of each subject's decompression path (SPEC 3.7).

Rust (`python -m cfbench.complexity rust`): rust-code-analysis-cli gives cyclomatic and cognitive
complexity per function space. Closures (`<anonymous>`) are not counted on their own: the enclosing
function's `sum` already includes them. If the tool cannot run (tool-gap protocol), `lizard` is
used for cyclomatic complexity only and the raw file marks cognitive as unavailable.

C (`... c`): lizard's Python API over the zlib and zng decompression-path files (cyclomatic only;
lizard has no cognitive metric). `derive` writes the combined `complexity` table.
"""

import csv
import io
import json
import math
import subprocess
import sys
from pathlib import Path

import lizard

from cfbench import decomp_paths, env, paths, provenance, rawio, tools

RUST_SUBJECTS = ["cf", "zrs", "mox"]
C_SUBJECTS = ["zlib", "zng"]
KIND_RUST = "complexity-rust"
KIND_C = "complexity-c"
COLUMNS = ["subject", "tool", "tool_version", "metric", "n_functions", "median", "p90", "max"]
PENDING = "no complexity run; run make size"
UNAVAILABLE = " (cognitive unavailable)"
SCRIPT = "cfbench.complexity"
ANONYMOUS = "<anonymous>"


def distribution(values) -> dict:
    """n, median, p90 and max of a list of numbers.

    The median is the usual one (mean of the two middle values for even n). p90 is the nearest-rank
    percentile: the value at 1-based rank ceil(0.9 * n) in the sorted list.
    """
    xs = sorted(values)
    n = len(xs)
    if n == 0:
        return {"n": 0, "median": None, "p90": None, "max": None}
    mid = n // 2
    median = xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2
    return {"n": n, "median": median, "p90": xs[math.ceil(0.9 * n) - 1], "max": xs[-1]}


def rca_functions(doc: dict, file: str) -> list[dict]:
    """Function spaces (closures excluded) of one rust-code-analysis JSON document."""
    out = []

    def walk(space: dict) -> None:
        if space.get("kind") == "function" and space.get("name") != ANONYMOUS:
            m = space["metrics"]
            out.append(
                {
                    "file": file,
                    "name": space["name"],
                    "start_line": space["start_line"],
                    "cyclomatic": m["cyclomatic"]["sum"],
                    "cognitive": m["cognitive"]["sum"],
                }
            )
        for child in space.get("spaces", []):
            walk(child)

    walk(doc)
    return out


def lizard_functions(csv_text: str, file: str) -> list[dict]:
    """Functions from `lizard --csv` output: cyclomatic number (CCN) only."""
    rows = csv.reader(io.StringIO(csv_text))
    out = []
    for r in rows:
        if len(r) < 11 or r[0] == "NLOC":
            continue
        out.append(
            {
                "file": file,
                "name": r[7],
                "start_line": int(r[9]),
                "cyclomatic": float(r[1]),
                "cognitive": None,
            }
        )
    return out


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(paths.ROOT).as_posix()
    except ValueError:
        return Path(p).as_posix()


def run_rca(binary: str | Path, file: Path) -> dict:
    res = subprocess.run(
        [str(binary), "-m", "-O", "json", "-p", str(file)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(res.stdout)


def run_lizard(file: Path) -> str:
    res = subprocess.run(
        [sys.executable, "-m", "lizard", "--csv", str(file)],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout


def summarize(functions: list[dict], cognitive: bool) -> dict:
    return {
        "cyclomatic": distribution([f["cyclomatic"] for f in functions]),
        "cognitive": distribution([f["cognitive"] for f in functions]) if cognitive else None,
    }


def collect_rust(status, rca=run_rca, lizard=run_lizard, file_lists: dict | None = None) -> dict:
    """Per-function metrics for cf, zrs and mox; falls back to lizard when rca is unavailable."""
    use_rca = status.ok
    gap = (
        None
        if status.ok
        else {
            "tool": "rust-code-analysis-cli",
            "error": status.error,
            "fallback": "lizard (cyclomatic only)",
        }
    )
    subjects = {}
    for s in RUST_SUBJECTS:
        files = (file_lists or {}).get(s) or [f for f in decomp_paths.files(s) if f.suffix == ".rs"]
        funcs: list[dict] = []
        for f in files:
            if use_rca:
                funcs += rca_functions(rca(status.path, f), rel(f))
            else:
                funcs += lizard_functions(lizard(f), rel(f))
        subjects[s] = {
            "files": [rel(f) for f in files],
            "functions": funcs,
            "distributions": summarize(funcs, cognitive=use_rca),
        }
    return {
        "kind": KIND_RUST,
        "tool": {
            "name": "rust-code-analysis-cli" if use_rca else "lizard",
            "version": status.version if use_rca else None,
        },
        "cognitive": "available" if use_rca else "unavailable",
        "tool_gap": gap,
        "subjects": subjects,
    }


def run_rust() -> Path:
    status = tools.ensure("rust-code-analysis-cli")
    if not status.ok:
        print(f"tool gap: rust-code-analysis-cli: {status.error}", file=sys.stderr)
    payload = collect_rust(status)
    return rawio.write_raw(
        "size",
        payload,
        machine="any",
        profile="full",
        script=SCRIPT,
        environment=env.capture_environment(),
    )


def c_functions(info, file: str) -> list[dict]:
    """Functions of one `lizard` FileInformation (cyclomatic number only)."""
    return [{"file": file, "name": f.name, "start_line": f.start_line,
             "cyclomatic": float(f.cyclomatic_complexity), "cognitive": None}
            for f in info.function_list]  # fmt: skip


def collect_c(analyze=lizard.analyze_file, file_lists: dict | None = None) -> dict:
    """Per-function cyclomatic complexity for zlib and zng with lizard; cognitive is unavailable."""
    subjects = {}
    for s in C_SUBJECTS:
        files = (file_lists or {}).get(s) or [
            f for f in decomp_paths.files(s) if f.suffix in (".c", ".h")
        ]
        funcs: list[dict] = []
        for f in files:
            funcs += c_functions(analyze(str(f)), rel(f))
        subjects[s] = {"files": [rel(f) for f in files], "functions": funcs,
                       "distributions": summarize(funcs, cognitive=False)}  # fmt: skip
    return {"kind": KIND_C, "tool": {"name": "lizard", "version": lizard.version},
            "cognitive": "unavailable", "subjects": subjects}  # fmt: skip


def table_rows(rust: dict | None, c: dict | None) -> list[dict]:
    rows = []
    for payload in (rust, c):
        if payload is None:
            continue
        tool, version = payload["tool"]["name"], payload["tool"]["version"]
        cognitive = payload["cognitive"] == "available"
        for s, d in payload["subjects"].items():
            for metric in ("cyclomatic", "cognitive"):
                dist = d["distributions"][metric]
                n = d["distributions"]["cyclomatic"]["n"]
                row = {"subject": s, "tool": tool, "tool_version": version, "metric": metric,
                       "n_functions": n, "median": None, "p90": None, "max": None}  # fmt: skip
                if metric == "cognitive" and not cognitive:
                    row["tool"] = tool + UNAVAILABLE
                elif dist:
                    row.update(
                        n_functions=dist["n"],
                        median=dist["median"],
                        p90=dist["p90"],
                        max=dist["max"],
                    )
                rows.append(row)
    return rows


def derive() -> None:
    rust = rawio.list_raw("size", machine="any", kind=KIND_RUST)
    c = rawio.list_raw("size", machine="any", kind=KIND_C)
    if not rust and not c:
        provenance.write_table(
            "complexity", COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING
        )
        return
    docs = [rawio.load_raw(files[-1])["payload"] if files else None for files in (rust, c)]
    raw = [files[-1] for files in (rust, c) if files]
    provenance.write_table("complexity", COLUMNS, table_rows(*docs), script=SCRIPT, raw_files=raw)


def run_c() -> Path:
    return rawio.write_raw("size", collect_c(), machine="any", profile="full", script=SCRIPT,
                           environment=env.capture_environment())  # fmt: skip


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "rust":
        print(run_rust())
    elif cmd == "c":
        print(run_c())
    elif cmd == "derive":
        derive()
    else:
        print("usage: cfbench.complexity rust|c|derive", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
