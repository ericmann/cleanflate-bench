"""Effort per round from the pinned cleanflate clone: git history, tool log, Foundry state.

Methods (recorded in the payload):

- Round windows follow committer time: round 1 is the first commit through the r1 tag commit
  inclusive, round N is after the r(N-1) tag commit up to and including the rN tag commit.
- Stage wall-clock attributes each commit's gap since the previous commit (in committer-time order
  across the whole history) to that commit's `[stage:<s>]` tag. Gaps above `effort.idle_gap_hours`
  are idle (overnight pauses, waiting for review) and are reported separately.
- The milestone of a commit is the phase prefix of its `[task:<id>]` (`P0`..`P5`), `R<n>` for review
  fix tasks, `other` otherwise.
- The tool log is the complete snapshot at the last round; entries are assigned to rounds by their
  timestamp against the round windows.
- The forbidden-read audit (`effort.forbidden_reads`) lists every allowed call by a read-capable tool
  with a path-like token under a forbidden root, or naming a prior-art word outside the build
  checkout. Candidates are classified by hand in `config/forbidden_read_verdicts.toml`.
"""

import json
import re
import shlex
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cfbench import cleanflate_src, config, env, rawio

_TAG = re.compile(r"\[stage:([^\]]+)\]\s*\[task:([^\]]+)\]")
_PHASE = re.compile(r"^(P\d+)-")
_FIX = re.compile(r"^(R\d+)")
SNAPSHOT = "provenance/tool-log.snapshot.jsonl"
INTERVENTIONS = "provenance/human-interventions.md"
DURATION_GAP = (
    "human-interventions.md records when and what but not how long; durations are unavailable"
)
SOURCES = ("fuzzing", "conformance", "unit_tests", "review")


@dataclass(frozen=True)
class Commit:
    sha: str
    ts: int
    subject: str
    stage: str | None
    task: str | None
    defects: tuple[str, ...]


def parse_git_log(text: str) -> list[Commit]:
    """Commits from `git log --format=%H%x1f%ct%x1f%B%x1e`, oldest first by committer time."""
    out = []
    for rec in text.split("\x1e"):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        sha, ts, body = rec.split("\x1f", 2)
        m = _TAG.search(body)
        defects = tuple(
            line.split(":", 1)[1].strip()
            for line in body.splitlines()
            if line.startswith("Defects-caught:")
        )
        out.append(
            Commit(
                sha.strip(),
                int(ts),
                body.strip().splitlines()[0] if body.strip() else "",
                m.group(1) if m else None,
                m.group(2) if m else None,
                defects,
            )
        )
    return sorted(out, key=lambda c: (c.ts, c.sha))


def milestone(task: str | None) -> str:
    if task:
        for pat in (_PHASE, _FIX):
            m = pat.match(task)
            if m:
                return m.group(1)
    return "other"


def round_windows(commits: list[Commit], tag_shas: list[str]) -> list[list[Commit]]:
    """Commits per round: after the previous tag commit up to and including this round's tag."""
    index = {c.sha: i for i, c in enumerate(commits)}
    windows, start = [], 0
    for sha in tag_shas:
        end = index[sha] + 1
        windows.append(commits[start:end])
        start = end
    return windows


def stage_wall_clock(window: list[Commit], previous_ts: int | None, idle_gap_seconds: int) -> dict:
    """Seconds per stage and milestone, idle seconds and the span of a round window."""
    by_stage: Counter = Counter()
    by_milestone: Counter = Counter()
    by_stage_milestone: dict[str, Counter] = defaultdict(Counter)
    idle = 0
    prev = previous_ts
    for c in window:
        gap = 0 if prev is None else c.ts - prev
        prev = c.ts
        if gap > idle_gap_seconds:
            idle += gap
            continue
        stage = c.stage or "untagged"
        by_stage[stage] += gap
        by_milestone[milestone(c.task)] += gap
        by_stage_milestone[milestone(c.task)][stage] += gap
    return {
        "commits": len(window),
        "start_ts": window[0].ts if window else None,
        "end_ts": window[-1].ts if window else None,
        "attributed_seconds": sum(by_stage.values()),
        "idle_seconds": idle,
        "by_stage": dict(sorted(by_stage.items())),
        "by_milestone": dict(sorted(by_milestone.items())),
        "by_milestone_stage": {
            m: dict(sorted(v.items())) for m, v in sorted(by_stage_milestone.items())
        },
        "commits_by_stage": dict(sorted(Counter(c.stage or "untagged" for c in window).items())),
    }


def parse_tool_log(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _ts(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp())


def assign_round(ts: int, boundaries: list[int]) -> int:
    """Round (1-based) whose window contains `ts`; later than the last tag counts as the last."""
    for i, end in enumerate(boundaries, start=1):
        if ts <= end:
            return i
    return len(boundaries)


def categorize_denial(reason: str | None, prefix_map: list[dict]) -> str:
    for entry in prefix_map:
        if (reason or "").startswith(entry["prefix"]):
            return entry["category"]
    return "other"


_SEPARATORS = re.compile(r"[;|&<>()=]")


def path_tokens(tool: str, target: str) -> list[str]:
    """Path-like tokens of a call: the whole target for file tools, `/` or `~` words for Bash.

    Bash words are split on shell separators too, so a path inside a pipeline or an inline script
    is still seen; that over-reports (a regex naming a path is a candidate) and never under-reports.
    """
    if tool != "Bash":
        return [target] if target else []
    try:
        words = shlex.split(target, comments=False)
    except ValueError:
        words = target.split()
    out = []
    for w in words:
        for piece in _SEPARATORS.split(w):
            for p in piece.split():
                p = p.strip("'\"`")
                if p.startswith(("/", "~")):
                    out.append(p)
    return out


def _word_in(path: str, words: list[str]) -> str | None:
    for w in words:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(w)}(?![A-Za-z0-9])", path, re.IGNORECASE):
            return w
    return None


def forbidden_read_match(entry: dict, rules: dict) -> dict | None:
    """The first offending path of an allowed read-capable call, or None."""
    if entry["decision"] != "allowed" or entry["tool"] not in rules["read_tools"]:
        return None
    root = rules["repo_root"].rstrip("/")
    for p in path_tokens(entry["tool"], entry.get("target") or ""):
        hit = next((pat for pat in rules["root_patterns"] if re.search(pat, p)), None)
        if hit:
            return {"path": p, "rule": f"root {hit}"}
        inside = p == root or p.startswith(root + "/")
        word = None if inside else _word_in(p, rules["words"])
        if word:
            return {"path": p, "rule": f"word {word} outside the build checkout"}
    return None


def forbidden_reads(entries: list[dict], rules: dict) -> dict:
    """Read-capable allowed calls and the forbidden-read candidates among them."""
    calls = [e for e in entries if e["decision"] == "allowed" and e["tool"] in rules["read_tools"]]
    cands = []
    for e in calls:
        m = forbidden_read_match(e, rules)
        if m:
            cands.append({"ts": e["ts"], "tool": e["tool"], "stage": e.get("foundry_stage"),
                          "task": e.get("task_id"), **m})  # fmt: skip
    return {"read_calls": len(calls), "candidates": cands}


def tool_log_summary(
    entries: list[dict], prefix_map: list[dict], read_rules: dict | None = None
) -> dict:
    models: dict[str, Counter] = defaultdict(Counter)
    denied: Counter = Counter()
    items = []
    for e in entries:
        stage = e.get("foundry_stage") or "unknown"
        if e.get("model"):
            models[stage][e["model"]] += 1
        if e["decision"] == "denied":
            cat = categorize_denial(e.get("reason"), prefix_map)
            denied[cat] += 1
            items.append({"ts": e["ts"], "tool": e["tool"], "stage": e.get("foundry_stage"),
                          "task": e.get("task_id"), "reason": e.get("reason"), "category": cat})  # fmt: skip
    out = {
        "calls": len(entries),
        "models_by_stage": {s: dict(sorted(c.items())) for s, c in sorted(models.items())},
        "denied": {
            "count": sum(denied.values()),
            "categories": dict(sorted(denied.items())),
            "items": items,
        },
    }
    if read_rules is not None:
        out["forbidden_reads"] = forbidden_reads(entries, read_rules)
    return out


def defect_source(text: str, stage: str | None, keywords: dict[str, list[str]]) -> str:
    """Source of a defect from keywords, with the stage as tiebreak (review-fix counts as review)."""
    low = text.lower()
    hits = [s for s in SOURCES if any(k in low for k in keywords.get(s, []))]
    review_stage = stage in ("review", "fix")
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        return "review" if review_stage and "review" in hits else hits[0]
    return "review" if review_stage else "other"


def defects_summary(window: list[Commit], keywords: dict[str, list[str]]) -> dict:
    sources: Counter = Counter()
    none = 0
    for c in window:
        for d in c.defects:
            if d.lower().startswith("none"):
                none += 1
            else:
                sources[defect_source(d, c.stage, keywords)] += 1
    return {
        "by_source": dict(sorted(sources.items())),
        "found": sum(sources.values()),
        "none": none,
    }


def parse_interventions(md: str) -> list[dict]:
    """Rows of the human-interventions tables: when, who, stage/task, what, why."""
    rows = []
    for line in md.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) < 5 or not re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
            continue
        rows.append(
            {
                "when": cells[0],
                "who": cells[1],
                "stage_task": cells[2],
                "what": cells[3],
                "why": " | ".join(cells[4:]),
            }
        )
    return rows


def intervention_round(row: dict, boundaries: list[int]) -> int:
    """Round of an intervention: a `phase-N` mention wins, otherwise the timestamp (date-only is 00:00Z)."""
    m = re.search(r"phase-(\d+)", row["stage_task"])
    if m and int(m.group(1)) <= len(boundaries):
        return int(m.group(1))
    when = row["when"]
    when = when if "T" in when else f"{when}T00:00Z"
    return assign_round(_ts(when), boundaries)


def state_summary(state: dict) -> dict:
    return {
        "flight_round": state.get("round"),
        "verdict": state.get("verdict"),
        "review_rounds": len(state.get("rounds", [])),
        "reviews": [
            {
                "round": r["round"],
                "verdict": r["verdict"],
                "fix_tasks": r.get("fixTasks"),
                "at": r.get("at"),
            }
            for r in state.get("rounds", [])
        ],
    }


def collect(
    clone: Path | None = None, cfg: dict | None = None, git=None, rounds: list[dict] | None = None
) -> dict:
    """Effort payload. `git(clone, *args)` and `rounds` are injectable for tests."""
    cfg = cfg or config.load_config("full")
    clone = clone or cleanflate_src.clone_path()
    rounds = rounds or cleanflate_src.rounds()["rounds"]
    shas = [r["sha"] for r in rounds]
    git = git or cleanflate_src.git
    log = git(clone, "log", "--format=%H%x1f%ct%x1f%B%x1e", shas[-1])
    commits = parse_git_log(log)
    windows = round_windows(commits, shas)
    eff = cfg["effort"]
    idle = int(eff["idle_gap_hours"] * 3600)
    boundaries = [w[-1].ts for w in windows]
    entries = parse_tool_log(git(clone, "show", f"{shas[-1]}:{SNAPSHOT}"))
    interventions = parse_interventions(git(clone, "show", f"{shas[-1]}:{INTERVENTIONS}"))
    out = []
    prev_ts = None
    for i, (r, window) in enumerate(zip(rounds, windows, strict=True), start=1):
        in_round = [e for e in entries if assign_round(_ts(e["ts"]), boundaries) == i]
        state = json.loads(git(clone, "show", f"{r['sha']}:.foundry/state.json"))
        mine = [x for x in interventions if intervention_round(x, boundaries) == i]
        out.append(
            {
                "round": r["round"],
                "tag": r["tag"],
                "sha": r["sha"],
                "wall_clock": stage_wall_clock(window, prev_ts, idle),
                "tool_log": tool_log_summary(
                    in_round, eff["denial_categories"], eff["forbidden_reads"]
                ),
                "foundry": state_summary(state),
                "defects": defects_summary(window, eff["defect_keywords"]),
                "interventions": {"count": len(mine), "items": mine},
            }
        )
        prev_ts = window[-1].ts if window else prev_ts
    return {
        "kind": "history",
        "method": {
            "round_windows": "committer time; round 1 from the first commit, round N after the r(N-1) tag commit",
            "stage_wall_clock": "each commit's gap since the previous commit goes to its [stage:] tag",
            "idle_gap_hours": eff["idle_gap_hours"],
            "tool_log": f"{SNAPSHOT} at the last round, entries assigned to rounds by timestamp",
            "defects": "Defects-caught trailers mapped by effort.defect_keywords; stage breaks ties",
            "forbidden_reads": eff["forbidden_reads"],
        },
        "gaps": [DURATION_GAP],
        "rounds": out,
    }


def main() -> int:
    payload = collect()
    path = rawio.write_raw(
        "effort",
        payload,
        machine="any",
        profile="full",
        script="cfbench.effort.history",
        environment=env.capture_environment(),
    )
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
