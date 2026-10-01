"""Framing-cost decomposition and the hardware-CRC hypothesis (SPEC 3.3)."""

import argparse
import copy
import json
import sys
from pathlib import Path

from cfbench import charts, config, parity, paths, perf, perf_report, provenance
from cfbench.charts import new_figure

CATEGORY = "framing"
KIND = "framing-perf"
VARIANT = "framing"
OVERHEAD_COLUMNS = [
    "machine",
    "subject",
    "corpus",
    "level",
    "mode",
    "overhead_zlib",
    "overhead_gzip",
]
HYPOTHESIS_COLUMNS = [
    "machine",
    "corpus",
    "level",
    "cf_overhead_gzip",
    "zlib_nohw_overhead_gzip",
    "zlib_overhead_gzip",
    "rel_diff",
    "verdict",
]
PENDING = "no framing run; run make framing on M-A and M-B"
IDENTICAL_NOTE = "control identical to default on x86_64"
FIGURE = "framing_decomposition"


def overhead(t_raw: float, t_framed: float) -> float:
    """(1/T_framed - 1/T_raw) / (1/T_raw), with T the aggregate throughput."""
    return (1.0 / t_framed - 1.0 / t_raw) / (1.0 / t_raw)


def framing_cfg(cfg: dict) -> dict:
    out = copy.deepcopy(cfg)
    f = cfg["framing"]
    out["perf"].update(subjects=list(f["subjects"]), modes=list(f["modes"]))
    return out


def run(cfg: dict | None = None, **kw) -> list[Path]:
    cfg = framing_cfg(cfg or config.load_config())
    return perf.run(
        cfg, cfg["perf"]["subjects"], variant=VARIANT, category=CATEGORY, kind=KIND, **kw
    )


def overhead_rows(aggs: list[dict]) -> list[dict]:
    """Per (machine, subject, corpus, level, mode): zlib and gzip overhead vs raw framing.

    An overhead is None (n/a) when the framed or the raw aggregate is missing or incomplete.
    """
    by = {}
    for a in aggs:
        if a["complete"]:
            by[(a["machine"], a["subject"], a["corpus"], a["level"], a["mode"], a["framing"])] = a[
                "agg_mib_s"
            ]
    keys = {(m, s, c, lv, mo) for (m, s, c, lv, mo, _f) in by}
    rows = []
    for m, s, c, lv, mo in sorted(keys):
        raw = by.get((m, s, c, lv, mo, "raw"))
        row = {
            "machine": m,
            "subject": s,
            "corpus": c,
            "level": lv,
            "mode": mo,
            "overhead_zlib": None,
            "overhead_gzip": None,
        }
        for f, col in (("zlib", "overhead_zlib"), ("gzip", "overhead_gzip")):
            t = by.get((m, s, c, lv, mo, f))
            if raw and t:
                row[col] = overhead(raw, t)
        rows.append(row)
    return rows


def control_identical(lock: dict | None, machine: str) -> bool | None:
    """True when zlib-nohw and the default zlib build have the same hardware-CRC status here."""
    try:
        builds = lock["machines"][machine]["builds"]
        a, b = builds["zlib"]["hw_crc"]["compiled_in"], builds["zlib-nohw"]["hw_crc"]["compiled_in"]
    except (KeyError, TypeError):
        return None
    return a == b


def hypothesis_rows(overheads: list[dict], cfg: dict, lock: dict | None) -> list[dict]:
    """Per machine, corpus and level, cf's gzip overhead against zlib-nohw's, plus an ALL row."""
    tol = cfg["framing"]["hypothesis_tolerance"]
    f = cfg["framing"]
    idx = {(r["machine"], r["subject"], r["corpus"], r["level"], r["mode"]): r for r in overheads}
    rows = []
    keys = sorted({(r["machine"], r["corpus"], r["level"], r["mode"]) for r in overheads})
    for m, c, lv, mo in keys:
        cf = idx.get((m, "cf", c, lv, mo), {}).get("overhead_gzip")
        nohw = idx.get((m, "zlib-nohw", c, lv, mo), {}).get("overhead_gzip")
        zl = idx.get((m, "zlib", c, lv, mo), {}).get("overhead_gzip")
        row = {
            "machine": m,
            "corpus": c,
            "level": lv,
            "cf_overhead_gzip": cf,
            "zlib_nohw_overhead_gzip": nohw,
            "zlib_overhead_gzip": zl,
            "rel_diff": None,
        }
        if cf is None or nohw is None or nohw == 0:
            row["verdict"] = "no data"
        else:
            row["rel_diff"] = (cf - nohw) / nohw
            row["verdict"] = "within band" if abs(row["rel_diff"]) <= tol else "outside band"
        if control_identical(lock, m):
            row["verdict"] += f" ({IDENTICAL_NOTE})"
        rows.append(row)
    headline = [
        r for r in rows if r["corpus"] == f["figure_corpus"] and r["level"] == f["figure_level"]
    ]
    machines = cfg["paper"]["machines"]
    per = {r["machine"]: r["verdict"] for r in headline}
    verdicts = [per.get(m) for m in machines]
    if all(v and v.startswith("within band") for v in verdicts):
        overall = "confirmed"
    elif all(v and v.startswith("outside band") for v in verdicts):
        overall = "refuted"
    else:
        overall = "inconclusive"
    rows.append(
        {
            "machine": "ALL",
            "corpus": f["figure_corpus"],
            "level": f["figure_level"],
            "verdict": overall,
        }
    )
    return rows


def _lock() -> dict | None:
    p = paths.ROOT / "subjects.lock.json"
    return json.loads(p.read_text()) if p.exists() else None


def figure_data(overheads: list[dict], cfg: dict) -> dict:
    f = cfg["framing"]
    out: dict = {}
    for r in overheads:
        if r["corpus"] == f["figure_corpus"] and r["level"] == f["figure_level"]:
            out.setdefault(r["machine"], {})[r["subject"]] = (
                r["overhead_zlib"],
                r["overhead_gzip"],
            )
    return out


def draw(data: dict, cfg: dict):
    subjects = cfg["framing"]["subjects"]
    machines = sorted(data)
    fig = new_figure("default")
    axes = fig.subplots(1, len(machines), sharey=True, squeeze=False)[0]
    width = 0.38
    for ax, m in zip(axes, machines, strict=True):
        for i, s in enumerate(subjects):
            zl, gz = data[m].get(s, (None, None))
            for j, (v, color, label) in enumerate(
                ((zl, "#4C72B0", "zlib framing"), (gz, "#DD8452", "gzip framing"))
            ):
                x = i + (j - 0.5) * width
                if v is None:
                    ax.text(
                        x,
                        0.01,
                        "n/a",
                        rotation=90,
                        ha="center",
                        va="bottom",
                        fontsize=5,
                        color="#666666",
                    )
                else:
                    ax.bar(x, v * 100, width * 0.95, color=color, label=label if i == 0 else None)
        ax.set_xticks(range(len(subjects)), subjects, rotation=45, ha="right", fontsize=6)
        ax.set_title(m, fontsize=8)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.tick_params(axis="y", labelsize=7)
    axes[0].set_ylabel("framing overhead vs raw (% extra time)", fontsize=7)
    from matplotlib.patches import Patch

    axes[0].legend(
        handles=[
            Patch(color="#4C72B0", label="zlib framing"),
            Patch(color="#DD8452", label="gzip framing"),
        ],
        loc="upper left",
        fontsize=6,
        frameon=False,
    )
    fig.suptitle(
        f"Framing cost per subject, {cfg['framing']['figure_corpus'].title()} L{cfg['framing']['figure_level']}",
        fontsize=8,
    )
    return fig


def derive(cfg: dict | None = None, out_dir=None, lock: dict | None = None) -> dict:
    cfg = cfg or config.load_config("full")
    script = "cfbench.framing"
    rows, raw = perf_report.compute_rows(cfg, CATEGORY, KIND)
    if not rows:
        provenance.write_table(
            "framing_overhead", OVERHEAD_COLUMNS, [], script=script, raw_files=[], pending=PENDING
        )
        provenance.write_table(
            "framing_hypothesis",
            HYPOTHESIS_COLUMNS,
            [],
            script=script,
            raw_files=[],
            pending=PENDING,
        )
        print("framing: pending (no full framing run)")
        return {"overhead": [], "hypothesis": []}
    over = overhead_rows(perf_report.aggregates(rows))
    hyp = hypothesis_rows(over, cfg, lock if lock is not None else _lock())
    provenance.write_table("framing_overhead", OVERHEAD_COLUMNS, over, script=script, raw_files=raw)
    provenance.write_table(
        "framing_hypothesis", HYPOTHESIS_COLUMNS, hyp, script=script, raw_files=raw
    )
    data = figure_data(over, cfg)
    if data:
        charts.save_figure(
            draw(data, cfg), FIGURE, parity_note=parity.PARITY_NOTE, size="default", out_dir=out_dir
        )
    return {"overhead": over, "hypothesis": hyp}


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
