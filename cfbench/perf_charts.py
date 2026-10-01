"""Performance figures drawn from the derived tables."""

import sys
from collections import defaultdict

from matplotlib.patches import Patch

from cfbench import charts, config, parity, provenance

CORPORA = ("silesia", "canterbury")
LEVEL = 6
MODE = "oneshot"
COLORS = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860", "#DA8BC3", "#8C8C8C"]


def throughput_data(
    rows: list[dict], machine: str, variant: str, subjects: list[str], framings: list[str]
):
    """{framing: {corpus: {subject: ratio or None}}} from perf_aggregates rows (strings)."""
    got: dict = defaultdict(dict)
    for r in rows:
        if (r["machine"], r["variant"], r["mode"], r["level"]) != (
            machine,
            variant,
            MODE,
            str(LEVEL),
        ):
            continue
        got[(r["framing"], r["corpus"], r["subject"])] = provenance.to_float(r["ratio_vs_zlib"])
    return {f: {c: {s: got.get((f, c, s)) for s in subjects} for c in CORPORA} for f in framings}


def draw_throughput(data: dict, subjects: list[str], machine: str, variant: str):
    """Grouped bars of ratio vs zlib; missing values are labelled n/a, never drawn as zero."""
    fig = charts.new_figure("default")
    n = len(data)
    axes = fig.subplots(1, n, sharey=True, squeeze=False)[0]
    width = 0.8 / max(len(subjects), 1)
    for ax, (framing, per_corpus) in zip(axes, data.items(), strict=True):
        for ci, corpus in enumerate(CORPORA):
            for si, subject in enumerate(subjects):
                x = ci + (si - (len(subjects) - 1) / 2) * width
                v = per_corpus[corpus][subject]
                if v is None:
                    ax.text(
                        x,
                        0.02,
                        "n/a",
                        rotation=90,
                        ha="center",
                        va="bottom",
                        fontsize=6,
                        color="#666666",
                    )
                else:
                    ax.bar(x, v, width * 0.9, color=COLORS[si % len(COLORS)])
        ax.axhline(1.0, color="black", linewidth=0.6, linestyle="--")
        ax.set_xticks(range(len(CORPORA)), CORPORA, fontsize=7)
        ax.set_title(framing, fontsize=8)
        ax.set_ylim(bottom=0)
        ax.tick_params(axis="y", labelsize=7)
    axes[0].set_ylabel("throughput vs zlib (zlib = 1.00x)", fontsize=7)
    handles = [Patch(color=COLORS[i % len(COLORS)], label=s) for i, s in enumerate(subjects)]
    axes[len(axes) // 2].legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.12),
        ncol=3,
        fontsize=6,
        frameon=False,
    )
    fig.suptitle(
        f"Aggregate decompression throughput, level {LEVEL}, one-shot ({machine}, {variant})",
        fontsize=8,
    )
    return fig


def throughput_figure(machine: str, variant: str = "generic", out_dir=None):
    """Render `perf_throughput_<machine>` from perf_aggregates; None (pending) without data."""
    rows, _side = provenance.read_table("perf_aggregates")
    cfg = config.load_config("full")
    if variant == "native":
        subjects = [f"{s}@native" for s in cfg["perf"]["native_subjects"]] + ["zlib"]
    else:
        subjects = list(cfg["perf"]["subjects"])
    data = throughput_data(rows, machine, variant, subjects, cfg["perf"]["framings"])
    if not any(v is not None for per in data.values() for pc in per.values() for v in pc.values()):
        print(f"perf_throughput_{machine}: pending (no full perf data for {machine} {variant})")
        return None
    fig = draw_throughput(data, subjects, machine, variant)
    name = f"perf_throughput_{machine}" + ("" if variant == "generic" else f"_{variant}")
    return charts.save_figure(
        fig,
        name,
        parity_note=parity.with_context(machine, variant),
        size="default",
        out_dir=out_dir,
    )


def main() -> int:
    rows, _side = provenance.read_table("perf_aggregates")
    if not rows:
        print("perf figures: pending (no full perf data)")
        return 0
    for machine, variant in sorted({(r["machine"], r["variant"]) for r in rows}):
        throughput_figure(machine, variant)
    return 0


if __name__ == "__main__":
    sys.exit(main())
