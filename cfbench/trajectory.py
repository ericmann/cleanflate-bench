"""Improvement trajectory: cleanflate rounds 1-3 against zlib in one session (SPEC 3.5)."""

import argparse
import copy
import re
import sys
from pathlib import Path

from cfbench import charts, cleanflate_src, config, parity, perf, perf_report, provenance
from cfbench.charts import new_figure

CATEGORY = "trajectory"
KIND = "trajectory"
VARIANT = "rounds"
COLUMNS = [
    "machine",
    "round",
    "tag",
    "sha",
    "corpus",
    "framing",
    "mode",
    "level",
    "agg_mib_s",
    "ratio_vs_zlib",
    "complete",
]
PENDING = "no trajectory run; run make trajectory on M-A and M-B"
_ROUND = re.compile(r"^cf-r(\d+)$")
FIGURE_LEVEL = 6
FIGURE_MODE = "oneshot"


def trajectory_cfg(cfg: dict) -> dict:
    """The perf config with the trajectory subject, mode, level and run overrides applied."""
    out = copy.deepcopy(cfg)
    t = cfg["trajectory"]
    out["perf"].update(
        subjects=list(t["subjects"]),
        modes=list(t["modes"]),
        levels=list(t["levels"]),
        runs=t["runs"],
    )
    return out


def run(cfg: dict | None = None, **kw) -> list[Path]:
    """One randomised session of every trajectory subject (rounds and the zlib baseline)."""
    cfg = trajectory_cfg(cfg or config.load_config())
    return perf.run(
        cfg, cfg["perf"]["subjects"], variant=VARIANT, category=CATEGORY, kind=KIND, **kw
    )


def round_info() -> dict[int, dict]:
    return {r["round"]: r for r in cleanflate_src.rounds()["rounds"]}


def table_rows(aggs: list[dict], info: dict[int, dict]) -> list[dict]:
    """One row per round, corpus, framing, mode and level; the zlib baseline has no row."""
    out = []
    for a in aggs:
        m = _ROUND.match(a["subject"])
        if not m:
            continue
        n = int(m.group(1))
        out.append(
            {
                "machine": a["machine"],
                "round": n,
                "tag": info[n]["tag"],
                "sha": info[n]["sha"],
                "corpus": a["corpus"],
                "framing": a["framing"],
                "mode": a["mode"],
                "level": a["level"],
                "agg_mib_s": a["agg_mib_s"],
                "ratio_vs_zlib": a["ratio_vs_zlib"],
                "complete": a["complete"],
            }
        )
    return out


def derive(cfg: dict | None = None, out_dir=None) -> list[dict]:
    """Write the `trajectory` table and one figure per machine; pending without data."""
    cfg = cfg or config.load_config("full")
    rows, raw = perf_report.compute_rows(cfg, CATEGORY, KIND)
    script = "cfbench.trajectory"
    if not rows:
        provenance.write_table(
            "trajectory", COLUMNS, [], script=script, raw_files=[], pending=PENDING
        )
        print("trajectory: pending (no full trajectory run)")
        return []
    table = table_rows(perf_report.aggregates(rows), round_info())
    provenance.write_table("trajectory", COLUMNS, table, script=script, raw_files=raw)
    for machine in sorted({r["machine"] for r in table}):
        figure(table, machine, out_dir=out_dir)
    return table


def figure_series(table: list[dict], machine: str) -> dict[str, list[tuple[int, float]]]:
    """{'corpus framing': [(round, ratio)]} at the figure's level and mode, sorted by round."""
    series: dict[str, list[tuple[int, float]]] = {}
    for r in table:
        if (
            r["machine"] == machine
            and r["level"] == FIGURE_LEVEL
            and r["mode"] == FIGURE_MODE
            and r["ratio_vs_zlib"] is not None
        ):
            series.setdefault(f"{r['corpus']} {r['framing']}", []).append(
                (r["round"], r["ratio_vs_zlib"])
            )
    return {k: sorted(v) for k, v in sorted(series.items())}


def draw(
    series: dict[str, list[tuple[int, float]]],
    tags: dict[int, str],
    machine: str,
    size: str = "default",
):
    fig = new_figure(size)
    ax = fig.subplots()
    for label, pts in series.items():
        ax.plot(
            [p[0] for p in pts],
            [p[1] for p in pts],
            marker="o",
            markersize=3,
            linewidth=1,
            label=label,
        )
    ax.axhline(1.0, color="black", linewidth=0.6, linestyle="--")
    rounds = sorted(tags)
    ax.set_xticks(rounds, [f"{n}\n{tags[n]}" for n in rounds], fontsize=6)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("throughput vs zlib (zlib = 1.00x)", fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.legend(fontsize=6, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    fig.suptitle(
        f"cleanflate improvement by round, level {FIGURE_LEVEL}, one-shot ({machine})", fontsize=8
    )
    return fig


def figure(table: list[dict], machine: str, out_dir=None):
    series = figure_series(table, machine)
    if not series:
        print(f"trajectory_{machine}: pending (no ratio data for {machine})")
        return None
    tags = {n: r["tag"] for n, r in round_info().items()}
    return charts.save_figure(
        draw(series, tags, machine),
        f"trajectory_{machine}",
        parity_note=parity.with_context(machine, VARIANT),
        size="default",
        out_dir=out_dir,
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "derive"])
    a = ap.parse_args(argv)
    if a.cmd == "run":
        try:
            for p in run():
                print(p)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    else:
        derive()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
