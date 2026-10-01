"""Effort tables, documented gaps and the trajectory-plus-effort join (SPEC 3.9, 3.5)."""

import sys
from collections import Counter, defaultdict
from pathlib import Path

from cfbench import provenance, rawio

TABLES = {
    "effort_stage_round": [
        "round",
        "stage",
        "wall_clock_s",
        "models",
        "input_tokens",
        "output_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
        "cost_usd",
    ],
    "effort_totals": [
        "round",
        "wall_clock_s",
        "idle_s",
        "models",
        "input_tokens",
        "output_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
        "cost_usd",
    ],
    "effort_milestones": ["round", "milestone", "wall_clock_s", "review_rounds"],
    "effort_review_rounds": ["round", "review_round", "verdict", "fix_tasks"],
    "effort_defects": ["round", "source", "count"],
    "effort_interventions": ["round", "when", "stage_task", "nature"],
    "effort_denied": ["round", "category", "count"],
    "trajectory_with_effort": [
        "machine",
        "round",
        "tag",
        "corpus",
        "framing",
        "mode",
        "level",
        "agg_mib_s",
        "ratio_vs_zlib",
        "wall_clock_s",
        "output_tokens",
        "cost_usd",
    ],
}
PENDING_RAW = "Pending: run `make effort` (needs the effort history and usage raw files)"
PENDING_TRAJECTORY = "Pending: run `make trajectory` on M-A and M-B"
TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens")


def _sum_cost(costs: list) -> float | None:
    """Sum of costs, or None when any component is unknown (null cost propagates)."""
    return None if (not costs or any(c is None for c in costs)) else sum(costs)


def _tokens(cells: list[dict]) -> dict:
    return {
        "input_tokens": sum(c["input_tokens"] for c in cells),
        "output_tokens": sum(c["output_tokens"] for c in cells),
        "cache_write_tokens": sum(c["cache_creation_5m"] + c["cache_creation_1h"] for c in cells),
        "cache_read_tokens": sum(c["cache_read_tokens"] for c in cells),
        "cost_usd": _sum_cost([c["cost_usd"] for c in cells]),
        "models": ";".join(sorted({c["model"] for c in cells if c["model"]})),
    }


def build_tables(
    history: dict, usage: dict, trajectory: list[dict] | None
) -> dict[str, list[dict]]:
    """All effort tables as row lists, keyed by table name."""
    cells_by_round_stage: dict[tuple, list[dict]] = defaultdict(list)
    cells_by_round: dict[int, list[dict]] = defaultdict(list)
    for c in usage["summary"]:
        cells_by_round_stage[(c["round"], c["stage"])].append(c)
        cells_by_round[c["round"]].append(c)
    stage_rows, totals, milestones, reviews, defects, interventions, denied = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for r in history["rounds"]:
        n = r["round"]
        wc = r["wall_clock"]
        stages = sorted(set(wc["by_stage"]) | {s for (rn, s) in cells_by_round_stage if rn == n})
        for s in stages:
            cells = cells_by_round_stage.get((n, s), [])
            row = {"round": n, "stage": s, "wall_clock_s": wc["by_stage"].get(s)}
            if cells:
                row.update(_tokens(cells))
            stage_rows.append(row)
        tok = _tokens(cells_by_round.get(n, [])) if cells_by_round.get(n) else {}
        totals.append(
            {
                "round": n,
                "wall_clock_s": wc["attributed_seconds"],
                "idle_s": wc["idle_seconds"],
                **tok,
            }
        )
        for m, secs in wc["by_milestone"].items():
            milestones.append(
                {
                    "round": n,
                    "milestone": m,
                    "wall_clock_s": secs,
                    "review_rounds": r["foundry"]["review_rounds"],
                }
            )
        for rv in r["foundry"]["reviews"]:
            reviews.append(
                {
                    "round": n,
                    "review_round": rv["round"],
                    "verdict": rv["verdict"],
                    "fix_tasks": rv["fix_tasks"],
                }
            )
        for src, cnt in r["defects"]["by_source"].items():
            defects.append({"round": n, "source": src, "count": cnt})
        defects.append({"round": n, "source": "none reported", "count": r["defects"]["none"]})
        for it in r["interventions"]["items"]:
            interventions.append(
                {
                    "round": n,
                    "when": it["when"],
                    "stage_task": it["stage_task"],
                    "nature": it["what"],
                }
            )
        for cat, cnt in r["tool_log"]["denied"]["categories"].items():
            denied.append({"round": n, "category": cat, "count": cnt})
    all_cells = [c for c in usage["summary"]]
    totals.append(
        {
            "round": "total",
            "wall_clock_s": sum(t["wall_clock_s"] for t in totals),
            "idle_s": sum(t["idle_s"] for t in totals),
            **(_tokens(all_cells) if all_cells else {}),
        }
    )
    by_round = {t["round"]: t for t in totals if t["round"] != "total"}
    joined = []
    for t in trajectory or []:
        rn = int(t["round"])
        e = by_round.get(rn, {})
        joined.append(
            {
                "machine": t["machine"],
                "round": rn,
                "tag": t["tag"],
                "corpus": t["corpus"],
                "framing": t["framing"],
                "mode": t["mode"],
                "level": t["level"],
                "agg_mib_s": t["agg_mib_s"],
                "ratio_vs_zlib": t["ratio_vs_zlib"],
                "wall_clock_s": e.get("wall_clock_s"),
                "output_tokens": e.get("output_tokens"),
                "cost_usd": e.get("cost_usd"),
            }
        )
    return {
        "effort_stage_round": stage_rows,
        "effort_totals": totals,
        "effort_milestones": milestones,
        "effort_review_rounds": reviews,
        "effort_defects": defects,
        "effort_interventions": interventions,
        "effort_denied": denied,
        "trajectory_with_effort": joined,
    }


def gaps_markdown(history: dict, usage: dict) -> str:
    """The generated documented-gaps file: every gap entry plus the estimation methods."""
    out = [
        "<!-- generated by cfbench.effort.derive; do not edit -->",
        "",
        "# Effort data gaps and methods",
        "",
    ]
    out.append("## Cost and pricing")
    out.append("")
    priced = [g for g in usage["gaps"] if g.startswith("no price")]
    if priced:
        out.append(
            "Cost is null wherever a model has no price in `config/pricing.toml` (all prices are unset, "
            "source UNSET). The benchmark never guesses a price. Missing:"
        )
        out += [f"- {g}" for g in priced]
    else:
        out.append("Every model seen has all five prices set; cost is computed for all records.")
    out.append("")
    out.append("## Human intervention durations")
    out.append("")
    out += [f"- {g}" for g in history["gaps"]]
    out.append("")
    out.append("## Stage attribution")
    out.append("")
    methods = Counter(r["stage_method"] for r in usage.get("records", []))
    stages = Counter(r["stage"] for r in usage.get("records", []))
    out.append(
        "Token usage is attributed to a stage by subagent type (an implementer after the first review "
        "of its round counts as `fix`), the main session is `controller`, and the nearest preceding "
        "tool-log entry is the fallback. Records by method: "
        + ", ".join(f"{k}: {v}" for k, v in sorted(methods.items()))
        + "."
    )
    unresolved = {s: n for s, n in stages.items() if s in ("unknown", "untagged")}
    out.append("")
    out.append(
        "Stages that could not be attributed: "
        + (
            ", ".join(f"{s} ({n} records)" for s, n in sorted(unresolved.items()))
            if unresolved
            else "none."
        )
    )
    untagged = [
        (r["round"], r["wall_clock"]["by_stage"].get("untagged", 0)) for r in history["rounds"]
    ]
    out.append("")
    out.append(
        "Wall-clock for commits without a `[stage:...]` tag is reported as `untagged`: "
        + ", ".join(f"round {n}: {s} s" for n, s in untagged)
        + "."
    )
    out.append("")
    out.append("## Other limits")
    out.append("")
    out += [
        "- Wall-clock per stage is an estimate from commit gaps (`docs/methods/effort.md`); gaps above the idle threshold are excluded and reported as `idle_s`.",
        "- Review rounds are recorded per Foundry flight, not per milestone, so `effort_milestones.review_rounds` repeats the round's count on every milestone row.",
        "- Models in `effort_stage_round` come from the token usage export; the tool log counts calls per model, not tokens.",
    ]
    out += [f"- {g}" for g in usage["gaps"] if not g.startswith("no price")]
    out.append("")
    return "\n".join(out)


def _latest(kind: str) -> tuple[Path, dict] | None:
    files = rawio.list_raw("effort", machine="any", kind=kind)
    return (files[-1], rawio.load_raw(files[-1])["payload"]) if files else None


def derive() -> None:
    script = "cfbench.effort.derive"
    hist, usage = _latest("history"), _latest("usage")
    from cfbench import paths

    gaps_path = paths.RESULTS / "EFFORT_GAPS.md"
    gaps_path.parent.mkdir(parents=True, exist_ok=True)
    if hist is None or usage is None:
        for name, cols in TABLES.items():
            provenance.write_table(name, cols, [], script=script, raw_files=[], pending=PENDING_RAW)
        gaps_path.write_text(
            f"<!-- generated by cfbench.effort.derive; do not edit -->\n\n# Effort data gaps and methods\n\n{PENDING_RAW}\n",
            encoding="utf-8",
        )
        return
    trajectory = None
    pending = None
    try:
        rows, side = provenance.read_table("trajectory")
        trajectory = rows if rows else None
        pending = None if rows else (side.get("pending") or PENDING_TRAJECTORY)
    except FileNotFoundError:
        pending = PENDING_TRAJECTORY
    typed = [
        {
            **r,
            "round": r["round"],
            "agg_mib_s": provenance.to_float(r["agg_mib_s"]),
            "ratio_vs_zlib": provenance.to_float(r["ratio_vs_zlib"]),
        }
        for r in (trajectory or [])
    ]
    tables = build_tables(hist[1], usage[1], typed)
    raw = [hist[0], usage[0]]
    for name, cols in TABLES.items():
        provenance.write_table(
            name,
            cols,
            tables[name],
            script=script,
            raw_files=raw,
            pending=pending if name == "trajectory_with_effort" and not tables[name] else None,
        )
    gaps_path.write_text(gaps_markdown(hist[1], usage[1]), encoding="utf-8")


def main() -> int:
    derive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
