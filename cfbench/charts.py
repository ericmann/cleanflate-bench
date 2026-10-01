"""Deterministic figure output: SVG plus 2x PNG, always with the parity footnote."""

import textwrap
from contextlib import contextmanager
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import rc_context
from matplotlib.figure import Figure

from cfbench import config, paths

SIZES = ("paper", "slide", "default")
_DEFAULT_AS = ["default"]


@contextmanager
def size_override(size: str):
    """Within the block, figures asked for the `default` size are made at `size` instead.

    This re-renders the ordinary figure functions at slide size without changing them.
    """
    if size not in SIZES:
        raise ValueError(f"unknown figure size {size!r}; expected one of {SIZES}")
    _DEFAULT_AS.append(size)
    try:
        yield
    finally:
        _DEFAULT_AS.pop()


def size_inches(size: str, cfg: dict | None = None) -> tuple[float, float]:
    c = (cfg or config.load_config("full"))["charts"]
    if size == "paper":
        return c["paper_width_in"], c["paper_height_in"]
    if size == "slide":
        return c["slide_width_in"], c["slide_height_in"]
    if size == "default":
        if _DEFAULT_AS[-1] != "default":
            return size_inches(_DEFAULT_AS[-1], cfg)
        return c["default_width_in"], c["default_height_in"]
    raise ValueError(f"unknown figure size {size!r}; expected one of {SIZES}")


def new_figure(size: str = "default") -> Figure:
    return Figure(figsize=size_inches(size))


def _footnote(fig: Figure, note: str, cfg: dict) -> None:
    c = cfg["charts"]
    width_in, height_in = fig.get_size_inches()
    pt = c["footnote_pt"]
    chars = max(20, int(width_in * 72 / (pt * 0.55)))
    wrapped = "\n".join(textwrap.wrap(note, chars))
    lines = wrapped.count("\n") + 1
    frac = (lines * pt * 1.35 / 72) / height_in + 0.02
    fig.tight_layout(rect=(0, frac, 1, 1))
    fig.text(0.01, 0.01, wrapped, fontsize=pt, va="bottom", ha="left", color="#444444")


def save_figure(
    fig: Figure,
    name: str,
    *,
    parity_note: str,
    size: str = "default",
    out_dir: Path | None = None,
) -> list[Path]:
    """Write `<name>.svg` and `<name>.png` (2x base dpi). The parity note is mandatory.

    `size` is checked against the configured sizes; the figure should already have been created
    with `new_figure(size)` so its dimensions match.
    """
    if not parity_note or not parity_note.strip():
        raise ValueError("parity_note must not be empty")
    size_inches(size)  # validates the size name
    cfg = config.load_config("full")
    out_dir = Path(out_dir) if out_dir else paths.FIGURES
    out_dir.mkdir(parents=True, exist_ok=True)
    svg, png = out_dir / f"{name}.svg", out_dir / f"{name}.png"
    rc = {
        "svg.hashsalt": "cfbench",
        "font.family": cfg["charts"]["font_family"],
        "svg.fonttype": "path",
    }
    with rc_context(rc):
        _footnote(fig, parity_note, cfg)
        fig.savefig(svg, format="svg", metadata={"Date": None})
        fig.savefig(
            png, format="png", dpi=2 * cfg["charts"]["base_dpi"], metadata={"Software": None}
        )
    return [svg, png]
