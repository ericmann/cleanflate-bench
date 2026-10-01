"""Lines of code of each subject's decompression path, counted with tokei (SPEC 3.7).

Only the files in the shared decompression-path manifest (`config/decomp_paths.toml`, method in
`docs/methods/decomp-paths.md`) are passed to tokei, so no other source file is counted.
"""

import json
import subprocess
import sys
from pathlib import Path

from cfbench import decomp_paths, env, paths, provenance, rawio, tools

COLUMNS = ["subject", "language", "files", "code", "comments", "blanks"]
PENDING = "no loc run; run make size"
TOTAL = "Total"
SCRIPT = "cfbench.loc"


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(paths.ROOT).as_posix()
    except ValueError:
        return Path(p).as_posix()


def tokei_argv(binary: str | Path, files: list[Path]) -> list[str]:
    return [str(binary), "--no-ignore", "--output", "json", *[str(f) for f in files]]


def parse_tokei(doc: dict) -> dict[str, dict]:
    """Per language: files, code, comments, blanks; plus a `Total` entry.

    tokei reports embedded languages (Rust doc comments counted as Markdown) as `children` of the
    host language; they become `<language> (embedded)` rows with no file count so the rows sum to
    the total.
    """
    out: dict[str, dict] = {}
    for lang, v in doc.items():
        if lang == TOTAL:
            continue
        out[lang] = {"files": len(v["reports"]), "code": v["code"], "comments": v["comments"],
                     "blanks": v["blanks"]}  # fmt: skip
        for child, reports in v.get("children", {}).items():
            e = out.setdefault(
                f"{child} (embedded)", {"files": 0, "code": 0, "comments": 0, "blanks": 0}
            )
            for r in reports:
                for k in ("code", "comments", "blanks"):
                    e[k] += r["stats"][k]
    total = doc.get(TOTAL, {})
    out[TOTAL] = {
        "files": sum(v["files"] for v in out.values()),
        "code": total.get("code", 0),
        "comments": total.get("comments", 0),
        "blanks": total.get("blanks", 0),
    }
    return out


def run_tokei(argv: list[str]) -> dict:
    res = subprocess.run(argv, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def collect(binary: str | Path, runner=run_tokei, file_lists: dict | None = None) -> dict:
    subjects = {}
    for s in decomp_paths.SUBJECTS:
        files = (file_lists or {}).get(s) or decomp_paths.files(s)
        subjects[s] = {"files": [rel(f) for f in files],
                       "languages": parse_tokei(runner(tokei_argv(binary, files)))}  # fmt: skip
    return {"kind": "loc", "subjects": subjects}


def table_rows(payload: dict) -> list[dict]:
    rows = []
    for s, d in payload["subjects"].items():
        for lang, c in sorted(d["languages"].items(), key=lambda kv: (kv[0] == TOTAL, kv[0])):
            rows.append({"subject": s, "language": lang, **c})
    return rows


def derive_table() -> None:
    files = rawio.list_raw("size", machine="any", kind="loc")
    if not files:
        provenance.write_table("loc", COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING)
        return
    doc = rawio.load_raw(files[-1])
    provenance.write_table("loc", COLUMNS, table_rows(doc["payload"]), script=SCRIPT,
                           raw_files=[files[-1]])  # fmt: skip


def main() -> int:
    status = tools.ensure("tokei")
    if not status.ok:
        print(f"tool gap: tokei: {status.error}", file=sys.stderr)
        derive_table()
        return 0
    payload = collect(status.path)
    payload["tool"] = {"tokei": status.version}
    path = rawio.write_raw("size", payload, machine="any", profile="full", script=SCRIPT,
                           environment=env.capture_environment())  # fmt: skip
    derive_table()
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
