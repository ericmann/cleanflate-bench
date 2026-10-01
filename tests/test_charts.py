import pytest

from cfbench import charts, config, parity, perf_charts, provenance

NOTE = parity.PARITY_NOTE


def simple_figure():
    fig = charts.new_figure("default")
    ax = fig.subplots()
    ax.bar([0, 1, 2], [1.0, 0.5, 0.25])
    ax.set_title("t")
    return fig


def test_save_figure_writes_svg_and_2x_png(tmp_path):
    fig = simple_figure()
    svg, png = charts.save_figure(fig, "demo", parity_note=NOTE, out_dir=tmp_path)
    assert svg.name == "demo.svg" and png.name == "demo.png"
    assert svg.read_text().lstrip().startswith("<?xml")
    dpi = config.load_config("full")["charts"]["base_dpi"]
    w_in, h_in = charts.size_inches("default")
    width, height = (
        int.from_bytes(png.read_bytes()[16:20], "big"),
        int.from_bytes(png.read_bytes()[20:24], "big"),
    )
    assert (width, height) == (round(w_in * 2 * dpi), round(h_in * 2 * dpi))
    # the parity note is drawn: its first words appear as figure text
    assert any(t.get_text().startswith("Parity note") for t in fig.texts)


def test_svg_is_byte_identical_on_rerender(tmp_path):
    a = charts.save_figure(simple_figure(), "a", parity_note=NOTE, out_dir=tmp_path / "1")
    b = charts.save_figure(simple_figure(), "a", parity_note=NOTE, out_dir=tmp_path / "2")
    assert a[0].read_bytes() == b[0].read_bytes()
    assert a[1].read_bytes() == b[1].read_bytes()
    assert (
        b"Date" not in b[0].read_bytes().split(b"<defs>")[0] or b"dc:date" not in b[0].read_bytes()
    )


def test_parity_note_is_required(tmp_path):
    with pytest.raises(TypeError):
        charts.save_figure(simple_figure(), "x", out_dir=tmp_path)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        charts.save_figure(simple_figure(), "x", parity_note="  ", out_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_sizes_come_from_config_and_unknown_is_rejected():
    c = config.load_config("full")["charts"]
    assert charts.size_inches("paper") == (c["paper_width_in"], c["paper_height_in"])
    assert charts.size_inches("slide") == (c["slide_width_in"], c["slide_height_in"])
    with pytest.raises(ValueError):
        charts.size_inches("poster")


def test_parity_note_text_and_context():
    assert "no SIMD" in parity.PARITY_NOTE and "no unsafe" in parity.PARITY_NOTE
    assert "no C ABI" in parity.PARITY_NOTE and "decompression only" in parity.PARITY_NOTE
    ctx = parity.with_context("M-B", "native")
    assert ctx.startswith(parity.PARITY_NOTE) and "M-B" in ctx and "native" in ctx


def agg_row(subject, framing, corpus, ratio, machine="M-T", variant="generic"):
    return {
        "machine": machine, "variant": variant, "subject": subject, "corpus": corpus, "level": "6",
        "framing": framing, "mode": "oneshot", "ratio_vs_zlib": "" if ratio is None else str(ratio),
    }  # fmt: skip


def test_unsupported_cells_render_as_na_not_zero(tmp_path):
    subjects = ["cf", "zlib", "mox"]
    rows = []
    for framing in ("raw", "zlib", "gzip"):
        for corpus in perf_charts.CORPORA:
            rows.append(agg_row("zlib", framing, corpus, 1.0))
            rows.append(agg_row("cf", framing, corpus, 0.8))
            if framing != "gzip":
                rows.append(agg_row("mox", framing, corpus, 0.6))
    data = perf_charts.throughput_data(rows, "M-T", "generic", subjects, ["raw", "zlib", "gzip"])
    assert data["gzip"]["silesia"]["mox"] is None and data["raw"]["silesia"]["mox"] == 0.6
    fig = perf_charts.draw_throughput(data, subjects, "M-T", "generic")
    gzip_ax = fig.axes[2]
    assert sorted(t.get_text() for t in gzip_ax.texts) == ["n/a", "n/a"]  # one per corpus
    assert len(gzip_ax.patches) == 4  # cf and zlib, two corpora; mox has no bar
    assert all(p.get_height() > 0 for ax in fig.axes[:3] for p in ax.patches)
    assert not fig.axes[0].texts
    charts.save_figure(
        fig, "throughput", parity_note=parity.with_context("M-T", "generic"), out_dir=tmp_path
    )
    assert (tmp_path / "throughput.png").stat().st_size > 1000


def test_throughput_figure_pending_without_data(tmp_path, monkeypatch, capsys):
    from cfbench import paths

    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    provenance.write_table(
        "perf_aggregates", ["machine"], [], script="s", raw_files=[], pending="p"
    )
    assert perf_charts.throughput_figure("M-B", out_dir=tmp_path) is None
    assert "pending" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.png"))
