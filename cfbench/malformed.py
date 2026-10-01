"""Behaviour of every subject on cleanflate's hand-built malformed inputs (SPEC 3.6).

Every `*.bin` under `testdata/malformed/rfc1950|rfc1951|rfc1952` runs through each subject's
`decode --mode oneshot`. The outcome is `accept`, `accept+trailing`, `error:<kind>` or
`unsupported`. A disagreement is a file where supported subjects differ on accept versus reject.
"""

import json
import subprocess
import sys
from pathlib import Path

from cfbench import cleanflate_src, config, env, machine, paths, provenance, rawio, subjects

KIND = "malformed"
SCRIPT = "cfbench.malformed"
FRAMING_DIRS = {"rfc1950": "zlib", "rfc1951": "raw", "rfc1952": "gzip"}
MATRIX_COLUMNS = ["machine", "file", "framing", "subject", "outcome", "produced", "trailing_bytes", "error"]  # fmt: skip
DISAGREEMENT_COLUMNS = ["file", "framing", "outcomes_by_subject", "cf_expected"]
PENDING = "no malformed run; run make malformed"
FINDINGS_BEGIN = "<!-- malformed-findings:begin -->"
FINDINGS_END = "<!-- malformed-findings:end -->"


def malformed_dir(clone: Path | None = None) -> Path:
    return (clone or cleanflate_src.clone_path()) / "testdata" / "malformed"


def framing_of(rel: str) -> str:
    """The framing implied by the directory of a path such as `rfc1951/btype3.bin`."""
    return FRAMING_DIRS[Path(rel).parts[0]]


def list_files(root: Path) -> list[str]:
    out = []
    for d in FRAMING_DIRS:
        out += [f"{d}/{p.name}" for p in sorted((root / d).glob("*.bin"))]
    return out


def load_expected(root: Path) -> dict[str, dict]:
    """EXPECTED.tsv: path -> {expected, rule}."""
    out = {}
    for line in (root / "EXPECTED.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts[0] == "path":
            continue
        out[parts[0]] = {"expected": parts[1], "rule": parts[2] if len(parts) > 2 else ""}
    return out


def outcome(result: dict | None) -> str:
    if result is None:
        return "error:crash"
    if result["ok"]:
        return "accept+trailing" if result.get("trailing_bytes", 0) > 0 else "accept"
    return f"error:{result.get('error_kind')}"


def is_accept(o: str) -> bool:
    return o.startswith("accept")


def is_disagreement(outcomes: dict[str, str]) -> bool:
    """True when the supported subjects do not all accept, or all reject."""
    kinds = {is_accept(o) for o in outcomes.values() if o != "unsupported"}
    return len(kinds) > 1


def expected_matches(expected: str, o: str) -> bool:
    """`OK` means accept (trailing bytes allowed); anything else is the cf error kind."""
    return is_accept(o) if expected == "OK" else o == f"error:{expected}"


def run_decode(argv: list[str]) -> dict | None:
    out = subprocess.run(argv, capture_output=True, text=True, check=False)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None


def run_all(cfg: dict, root: Path, runner=run_decode) -> dict:
    ids = cfg["conformance"]["subjects"]
    cmds = {s: subjects.command(s) for s in ids}
    caps = {
        s: json.loads(
            subprocess.run([*cmds[s], "info"], capture_output=True, text=True, check=True).stdout
        )["framings"]
        for s in ids
    }
    expected = load_expected(root)
    files = []
    for rel in list_files(root):
        framing = framing_of(rel)
        results = {}
        for s in ids:
            if framing not in caps[s]:
                results[s] = {"outcome": "unsupported"}
                continue
            argv = [*cmds[s], "decode", "--framing", framing, "--mode", "oneshot",
                    "--input", str(root / rel)]  # fmt: skip
            r = runner(argv)
            results[s] = {
                "outcome": outcome(r),
                "produced": r["produced"] if r else None,
                "trailing_bytes": r.get("trailing_bytes") if r else None,
                "consumed": r.get("consumed") if r else None,
                "error": (r.get("error") or "") if r else "no result",
            }
        e = expected.get(rel, {})
        files.append({"file": rel, "framing": framing, "results": results,
                      "cf_expected": e.get("expected"), "rule": e.get("rule", "")})  # fmt: skip
    return {"kind": KIND, "subjects": ids, "files": files}


def matrix_rows(payload: dict, machine_id: str) -> list[dict]:
    rows = []
    for f in payload["files"]:
        for s in payload["subjects"]:
            r = f["results"][s]
            rows.append({"machine": machine_id, "file": f["file"], "framing": f["framing"],
                         "subject": s, "outcome": r["outcome"], "produced": r.get("produced"),
                         "trailing_bytes": r.get("trailing_bytes"), "error": r.get("error", "")})  # fmt: skip
    return rows


def disagreements(payload: dict) -> list[dict]:
    out = []
    for f in payload["files"]:
        outcomes = {s: f["results"][s]["outcome"] for s in payload["subjects"]}
        if is_disagreement(outcomes):
            out.append({"file": f["file"], "framing": f["framing"], "rule": f["rule"],
                        "outcomes": outcomes, "cf_expected": f["cf_expected"]})  # fmt: skip
    return out


def cf_mismatches(payload: dict) -> list[dict]:
    return [
        f
        for f in payload["files"]
        if f["cf_expected"]
        and not expected_matches(f["cf_expected"], f["results"]["cf"]["outcome"])
    ]


def highlights(payload: dict, dis: list[dict]) -> str:
    summary = (f"{len(payload['files'])} files, {len(payload['subjects'])} subjects. "
               f"{len(dis)} disagree on accept versus reject (candidate T3 findings).")  # fmt: skip
    lines = ["# Malformed-input highlights", "",
             "Generated by `cfbench.malformed`; do not edit.", "",
             summary, ""]  # fmt: skip
    for d in dis:
        by = ", ".join(f"{s}={o}" for s, o in d["outcomes"].items())
        lines += [f"## {d['file']}", "", f"- Framing: {d['framing']}",
                  f"- Rule: {d['rule'] or 'n/a'}", f"- cf expected: {d['cf_expected']}",
                  f"- Outcomes: {by}", ""]  # fmt: skip
    mism = cf_mismatches(payload)
    lines += ["## cf against EXPECTED.tsv", ""]
    if mism:
        for f in mism:
            lines.append(
                f"- {f['file']}: expected {f['cf_expected']}, got {f['results']['cf']['outcome']}"
            )
    else:
        lines.append("- cf's outcome matches EXPECTED.tsv for every file.")
    lines.append("")
    return "\n".join(lines)


def set_findings_block(block: list[str], begin: str, end: str, path: Path | None = None) -> None:
    """Replace the marked block in findings.md; an empty `block` removes it."""
    path = path or paths.RESULTS / "findings.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Findings\n"
    if begin in text:
        head, rest = text.split(begin, 1)
        tail = rest.split(end, 1)[1] if end in rest else ""
        text = head.rstrip("\n") + "\n" + tail.lstrip("\n")
    if block:
        text = text.rstrip("\n") + "\n\n" + "\n".join([begin, "", *block, "", end, ""])
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def update_findings(payload: dict, path: Path | None = None) -> bool:
    """Keep a marked block in findings.md listing cf outcomes that differ from EXPECTED.tsv."""
    mism = cf_mismatches(payload)
    block = []
    if mism:
        block = ["## Malformed-input outcome differs from EXPECTED.tsv", ""]
        for f in mism:
            block.append(
                f"- `{f['file']}`: expected {f['cf_expected']}, cf gave {f['results']['cf']['outcome']}"
            )
    set_findings_block(block, FINDINGS_BEGIN, FINDINGS_END, path)
    return bool(mism)


def derive() -> None:
    files = rawio.list_raw("correctness", kind=KIND)
    if not files:
        provenance.write_table("malformed_matrix", MATRIX_COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING)  # fmt: skip
        provenance.write_table("malformed_disagreements", DISAGREEMENT_COLUMNS, [], script=SCRIPT, raw_files=[], pending=PENDING)  # fmt: skip
        (paths.RESULTS / "MALFORMED_HIGHLIGHTS.md").write_text(
            f"# Malformed-input highlights\n\nPending: {PENDING}.\n", encoding="utf-8"
        )
        return
    newest = {}
    for p in files:
        d = rawio.load_raw(p)
        if d["machine"] not in newest or d["timestamp"] > newest[d["machine"]][1]["timestamp"]:
            newest[d["machine"]] = (p, d)
    rows, dis_rows, raw = [], [], []
    last = None
    for m, (p, d) in sorted(newest.items()):
        raw.append(p)
        rows += matrix_rows(d["payload"], m)
        last = d["payload"]
        for x in disagreements(last):
            by = ";".join(f"{s}={o}" for s, o in x["outcomes"].items())
            dis_rows.append({"file": x["file"], "framing": x["framing"],
                             "outcomes_by_subject": by, "cf_expected": x["cf_expected"]})  # fmt: skip
    provenance.write_table("malformed_matrix", MATRIX_COLUMNS, rows, script=SCRIPT, raw_files=raw)
    provenance.write_table("malformed_disagreements", DISAGREEMENT_COLUMNS, dis_rows, script=SCRIPT, raw_files=raw)  # fmt: skip
    (paths.RESULTS / "MALFORMED_HIGHLIGHTS.md").write_text(
        highlights(last, disagreements(last)), encoding="utf-8"
    )
    update_findings(last)


def run() -> Path:
    cfg = config.load_config("full")
    root = malformed_dir()
    payload = run_all(cfg, root)
    return rawio.write_raw("correctness", payload, machine=machine.detect_machine(),
                           profile="full", script=SCRIPT, environment=env.capture_environment())  # fmt: skip


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "run"
    if cmd == "run":
        print(run())
    if cmd in ("run", "derive"):
        derive()
        return 0
    print("usage: cfbench.malformed [run|derive]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
