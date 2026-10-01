"""Token usage per round, stage and model from Claude Code transcripts (SPEC 3.9).

The export is content-free: only the fields in `EXPORT_FIELDS` are copied from a transcript record,
never message text. Attribution (`stage`, `stage_method`, `round`) is added by this module:

- stage from the subagent's `attributionAgent` type (planner, implementer, reviewer, summarizer);
  an implementer after the first review of its flight counts as `fix`; the main session is
  `controller`;
- where the agent type is missing, the stage of the nearest preceding tool-log entry;
- round from the committer-time windows of `cfbench.effort.history`.

Records are de-duplicated on `(message_id, request_id)`, keeping the record with the most output
tokens (streaming writes several records per message).
"""

import argparse
import bisect
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from cfbench import config, env, rawio

EXPORT_FIELDS = [
    "ts",
    "session_id",
    "transcript",
    "agent_type",
    "model",
    "input_tokens",
    "output_tokens",
    "cache_creation_5m",
    "cache_creation_1h",
    "cache_read_tokens",
    "message_id",
    "request_id",
]
DERIVED_FIELDS = ["stage", "stage_method", "round"]
PRICE_KEYS = [
    "input_per_mtok",
    "output_per_mtok",
    "cache_write_5m_per_mtok",
    "cache_write_1h_per_mtok",
    "cache_read_per_mtok",
]
AGENT_STAGE = [
    ("implementer", "implement"),
    ("reviewer", "review"),
    ("planner", "plan"),
    ("summarizer", "summarize"),
]
MTOK = 1_000_000


def transcript_files(root: Path) -> list[Path]:
    return sorted(root.glob("*.jsonl")) + sorted(root.glob("*/subagents/*.jsonl"))


def export_record(d: dict, rel: str) -> dict | None:
    """A content-free export record from one transcript line, or None if it has no usage."""
    msg = d.get("message")
    if d.get("type") != "assistant" or not isinstance(msg, dict) or "usage" not in msg:
        return None
    u = msg["usage"]
    cc = u.get("cache_creation") or {}
    five = cc.get("ephemeral_5m_input_tokens")
    hour = cc.get("ephemeral_1h_input_tokens")
    if five is None and hour is None:
        five, hour = u.get("cache_creation_input_tokens", 0), 0
    return {
        "ts": d.get("timestamp"),
        "session_id": d.get("sessionId"),
        "transcript": rel,
        "agent_type": d.get("attributionAgent"),
        "model": msg.get("model"),
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_creation_5m": five or 0,
        "cache_creation_1h": hour or 0,
        "cache_read_tokens": u.get("cache_read_input_tokens", 0),
        "message_id": msg.get("id"),
        "request_id": d.get("requestId"),
    }


def read_records(root: Path) -> tuple[list[dict], int]:
    """De-duplicated export records and the number of duplicates dropped."""
    best: dict[tuple, dict] = {}
    seen = 0
    for f in transcript_files(root):
        rel = f.relative_to(root).as_posix()
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                rec = export_record(d, rel)
                if rec is None:
                    continue
                seen += 1
                key = (rec["message_id"], rec["request_id"])
                if key not in best or rec["output_tokens"] >= best[key]["output_tokens"]:
                    best[key] = rec
    return sorted(best.values(), key=lambda r: (r["ts"] or "", r["message_id"] or "")), seen - len(
        best
    )


def stage_from_agent(agent_type: str | None) -> str | None:
    low = (agent_type or "").lower()
    for needle, stage in AGENT_STAGE:
        if needle in low:
            return stage
    return None


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def attribute(
    records: list[dict],
    boundaries: list[int],
    first_review_at: dict[int, int | None],
    tool_log: list[tuple[int, str]],
) -> list[dict]:
    """Add stage, stage_method and round to each record.

    `boundaries` are the round end timestamps, `first_review_at` the first review time per round
    (epoch seconds) and `tool_log` sorted (epoch, stage) pairs for the fallback.
    """
    times = [t for t, _ in tool_log]
    out = []
    for r in records:
        ts = _epoch(r["ts"])
        rnd = next((i for i, end in enumerate(boundaries, 1) if ts <= end), len(boundaries))
        stage = stage_from_agent(r["agent_type"])
        method = "agent type"
        if stage == "implement":
            fr = first_review_at.get(rnd)
            if fr is not None and ts > fr:
                stage, method = "fix", "agent type, after the first review of its round"
        elif stage is None and r["agent_type"] is None and "/subagents/" not in r["transcript"]:
            stage, method = "controller", "main session"
        elif stage is None:
            i = bisect.bisect_right(times, ts) - 1
            stage = tool_log[i][1] if i >= 0 else "unknown"
            method = "nearest preceding tool-log entry"
        out.append({**r, "stage": stage, "stage_method": method, "round": rnd})
    return out


def load_prices(pricing: dict | None = None) -> dict[str, dict]:
    return (pricing or config.load_toml("pricing.toml"))["models"]


def cost_of(rec: dict, price: dict) -> float | None:
    """USD cost of one record, or None when any needed price is missing."""
    if any(k not in price for k in PRICE_KEYS):
        return None
    return (
        rec["input_tokens"] * price["input_per_mtok"]
        + rec["output_tokens"] * price["output_per_mtok"]
        + rec["cache_creation_5m"] * price["cache_write_5m_per_mtok"]
        + rec["cache_creation_1h"] * price["cache_write_1h_per_mtok"]
        + rec["cache_read_tokens"] * price["cache_read_per_mtok"]
    ) / MTOK


def summarize(records: list[dict], prices: dict[str, dict]) -> dict:
    """Token and cost totals per round, stage and model, plus gaps."""
    cells: dict[tuple, dict] = defaultdict(
        lambda: {"messages": 0, "input_tokens": 0, "output_tokens": 0, "cache_creation_5m": 0,
                 "cache_creation_1h": 0, "cache_read_tokens": 0, "cost_usd": 0.0, "priced": True}
    )  # fmt: skip
    gaps: set[str] = set()
    for r in records:
        c = cells[(r["round"], r["stage"], r["model"])]
        c["messages"] += 1
        for k in (
            "input_tokens",
            "output_tokens",
            "cache_creation_5m",
            "cache_creation_1h",
            "cache_read_tokens",
        ):
            c[k] += r[k]
        cost = cost_of(r, prices.get(r["model"], {}))
        if cost is None:
            c["priced"] = False
            missing = [k for k in PRICE_KEYS if k not in prices.get(r["model"], {})]
            gaps.add(
                f"no price for model {r['model']} ({', '.join(missing)} unset in config/pricing.toml)"
            )
        else:
            c["cost_usd"] += cost
    rows = []
    for (rnd, stage, model), c in sorted(
        cells.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")
    ):
        rows.append(
            {
                "round": rnd,
                "stage": stage,
                "model": model,
                **{k: v for k, v in c.items() if k not in ("priced", "cost_usd")},
                "cost_usd": c["cost_usd"] if c["priced"] else None,
            }
        )
    return {"cells": rows, "gaps": sorted(gaps)}


def collect(
    root: Path,
    boundaries: list[int],
    first_review_at: dict[int, int | None],
    tool_log: list[tuple[int, str]],
    pricing: dict | None = None,
) -> dict:
    records, dupes = read_records(root)
    attributed = attribute(records, boundaries, first_review_at, tool_log)
    summary = summarize(attributed, load_prices(pricing))
    gaps = list(summary["gaps"])
    gaps.append(
        "usage covers only the transcripts present in transcripts_dir on this machine; sessions run "
        "elsewhere are not included"
    )
    return {
        "kind": "usage",
        "fields": EXPORT_FIELDS,
        "derived_fields": DERIVED_FIELDS,
        "records": attributed,
        "duplicates_dropped": dupes,
        "summary": summary["cells"],
        "gaps": gaps,
        "method": {
            "dedup": "(message_id, request_id), keeping the record with the most output tokens",
            "stage": "attributionAgent type; implementer after the first review of its round is fix; "
            "main session is controller; otherwise the nearest preceding tool-log entry",
            "round": "committer-time windows of the effort history payload",
            "cost": "tokens times config/pricing.toml; null where any price is missing",
        },
    }


def _history_inputs() -> tuple[list[int], dict[int, int | None], list[tuple[int, str]]]:
    """Round boundaries, first review times and tool-log (epoch, stage) pairs from the clone."""
    from cfbench import cleanflate_src
    from cfbench.effort import history

    files = rawio.list_raw("effort", machine="any", kind="history")
    if not files:
        raise RuntimeError(
            "no effort history raw file: run `python -m cfbench.effort.history` first"
        )
    doc = rawio.load_raw(files[-1])["payload"]
    boundaries = [r["wall_clock"]["end_ts"] for r in doc["rounds"]]
    first_review: dict[int, int | None] = {}
    for r in doc["rounds"]:
        ats = [x["at"] for x in r["foundry"]["reviews"] if x.get("at")]
        first_review[r["round"]] = int(_epoch(min(ats))) if ats else None
    sha = cleanflate_src.rounds()["rounds"][-1]["sha"]
    entries = history.parse_tool_log(
        cleanflate_src.git(cleanflate_src.clone_path(), "show", f"{sha}:{history.SNAPSHOT}")
    )
    log = sorted(
        (int(_epoch(e["ts"])), e["foundry_stage"]) for e in entries if e.get("foundry_stage")
    )
    return boundaries, first_review, log


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-gaps", action="store_true")
    a = ap.parse_args(argv)
    cfg = config.load_config("full")
    root = Path(cfg["effort"]["transcripts_dir"]).expanduser()
    if not root.is_dir():
        if not a.allow_gaps:
            print(
                f"error: transcripts_dir {root} is missing; pass --allow-gaps to record an empty export",
                file=sys.stderr,
            )
            return 1
        payload = {"kind": "usage", "fields": EXPORT_FIELDS, "records": [], "summary": [],
                   "gaps": [f"transcripts_dir {root} is missing on this machine"], "duplicates_dropped": 0}  # fmt: skip
    else:
        payload = collect(root, *_history_inputs())
    path = rawio.write_raw(
        "effort",
        payload,
        machine="any",
        profile="full",
        script="cfbench.effort.usage",
        environment=env.capture_environment(),
    )
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
