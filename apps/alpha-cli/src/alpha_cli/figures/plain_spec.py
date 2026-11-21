"""Lay a ``FigureSpec`` out as a notebook figure, plain or annotated.

Both variants draw the same marks on the same axes. The annotated variant adds callouts,
labelled bands and a "How to read this chart" box from ``spec_facts``; it never changes a
plotted value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alpha_cli.figures import plain_marks as pm
from alpha_cli.figures import plain_style as ps
from alpha_cli.figures.spec_facts import (
    Plan,
    figure_bands,
    held_back_span,
    panel_plan,
    time_extent,
)
from alpha_research.figures.spec import (
    BandMark,
    BarMark,
    CandleMark,
    ErrorBarMark,
    FigureSpec,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Mark,
    Panel,
    RuleMark,
    ScatterMark,
    TableMark,
    ZoneMark,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

_SOLO = (LineMark, BandMark, ScatterMark, RuleMark, ZoneMark, CandleMark, BarMark, HistogramMark)


def _draw_mark(axes: Axes, figure: Figure, spec: FigureSpec, mark: Mark, index: int) -> None:
    kind = spec.x_kind
    if isinstance(mark, LineMark):
        pm.draw_line(axes, mark, kind, index)
    elif isinstance(mark, BandMark):
        pm.draw_band(axes, mark, kind, index)
    elif isinstance(mark, CandleMark):
        pm.draw_candle(axes, mark, kind)
    elif isinstance(mark, ScatterMark):
        pm.draw_scatter(axes, mark, kind, index)
    elif isinstance(mark, BarMark):
        pm.draw_bar(axes, mark, kind, index)
    elif isinstance(mark, HistogramMark):
        pm.draw_histogram(axes, mark, index)
    elif isinstance(mark, HeatmapMark):
        pm.draw_heatmap(axes, figure, mark)
    elif isinstance(mark, ZoneMark):
        pm.draw_zone(axes, mark, kind, index)
    elif isinstance(mark, RuleMark):
        pm.draw_rule(axes, mark, kind)
    elif isinstance(mark, ErrorBarMark):
        pm.draw_errorbar(axes, mark)
    elif isinstance(mark, TableMark):
        pm.draw_table(axes, mark)


def _thin(axes: Axes, which: str, limit: int) -> None:
    ps.hide_alternate_ticks(axes, which, limit)


def _style_axes(axes: Axes, spec: FigureSpec, panel: Panel, last: bool, drawn: bool) -> None:
    from matplotlib.ticker import FuncFormatter

    heat = any(isinstance(m, HeatmapMark | TableMark) for m in panel.marks)
    if panel.y_scale != "linear":
        axes.set_yscale(panel.y_scale)
    if panel.y_limits is not None:
        axes.set_ylim(*panel.y_limits)
    if panel.y_percent:
        axes.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
    if panel.y_zero_rule:
        axes.axhline(0.0, color="black", linewidth=0.8)
    if not heat:
        axes.grid(True, alpha=0.3)
    table = any(isinstance(m, TableMark) for m in panel.marks)
    if not table and not any(isinstance(m, ErrorBarMark) for m in panel.marks):
        axes.set_ylabel(ps.wrap(panel.y_label, 26) if not heat else panel.y_label)
    if panel.note is not None:
        axes.text(
            0.01,
            0.03,
            ps.wrap(panel.note, 60),
            transform=axes.transAxes,
            fontsize=8,
            va="bottom",
            bbox={"fc": "white", "ec": "0.6"},
        )
    if panel.legend and panel.legend_entries and drawn:
        axes.legend(loc="upper left", fontsize=8, ncol=min(len(panel.legend_entries), 3))
    if last and not table:
        axes.set_xlabel(spec.x_label)


def plt_align(axes: Axes) -> None:
    for label in axes.get_xticklabels():
        label.set_horizontalalignment("right")


def _x_axis(axes_list: list[Axes], spec: FigureSpec) -> None:
    if spec.x_kind == "time":
        import matplotlib.dates as dates

        mdates: Any = dates

        locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
        for axes in axes_list:
            if not axes.images and axes.get_xlim()[1] > 1000:
                axes.xaxis.set_major_locator(locator)
                axes.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    elif spec.x_kind == "category":
        for axes in axes_list:
            if axes.get_xlabel() or axes is axes_list[-1]:
                axes.set_xticks(range(len(spec.x_categories)), labels=list(spec.x_categories))
                if len(spec.x_categories) > 8:
                    axes.tick_params(axis="x", labelrotation=45)
                    axes.tick_params(axis="x", labelrotation=45)
                    plt_align(axes)
                _thin(axes, "x", 16)
    for axes in axes_list:
        if axes.images:
            _thin(axes, "y", 22)
            _thin(axes, "x", 16)


def _outline_cells(axes: Axes, plan: Plan) -> None:
    """Heatmaps: outline the highest cell (solid) and the lowest (dashed); no box hides a cell."""
    from matplotlib.patches import Rectangle

    for call, style in zip(plan.calls, ("-", "--"), strict=False):
        axes.add_patch(
            Rectangle((call.x - 0.5, call.y - 0.5), 1, 1, fill=False, ec="black", lw=2, ls=style)
        )


def _annotate(figure: Figure, spec: FigureSpec, axes_list: list[Axes]) -> None:
    held = held_back_span(spec)
    extent = time_extent(spec)
    for number, (axes, panel) in enumerate(zip(axes_list, spec.panels, strict=True)):
        plan = panel_plan(spec, panel)
        if held is not None:
            left = float(pm.x_values((extent[0] if extent else 0.0,), "time")[0])
            lo, hi = (float(v) for v in pm.x_values(held, "time"))
            axes.set_xlim(left, hi)
            ps.held_back_band(axes, lo, hi)
        if number == 0 and extent is not None:
            for a, b, label in figure_bands(spec):
                lo, hi = (float(v) for v in pm.x_values((a, b), "time"))
                ps.band(axes, lo, hi, label, y=0.93)
        for a, b, label in plan.bands:
            lo, hi = (float(v) for v in pm.x_values((a, b), spec.x_kind))
            ps.band(axes, lo, hi, label, y=0.86)
        axes.get_xlim()
        axes.get_ylim()
        used = [1] if panel.legend and panel.legend_entries else []
        if axes.images:
            _outline_cells(axes, plan)
            continue
        tables = [m for m in panel.marks if isinstance(m, TableMark)]
        if tables:
            ps.band(axes, 0.0, 1.0, f"stored evidence table: {len(tables[0].rows)} rows")
            continue
        for call in plan.calls[:3]:
            xy = (float(pm.x_values((call.x,), spec.x_kind)[0]), call.y)
            ps.callout(axes, call.text, xy, used)


def draw_spec(spec: FigureSpec, variant: str, sentences: list[str]) -> Figure:
    """Draw one variant; ``sentences`` fill the annotated box and are ignored when plain."""
    annotated = variant == "annotated"
    ratios = [panel.height_ratio for panel in spec.panels]
    body = max(3.8, 2.6 * sum(ratios))
    foot = 0.9 + (ps.box_height(sentences) + 0.1 if annotated else 0.0)
    top = 0.85
    figure = ps.new_figure(top + body + foot + 0.7)
    total = figure.get_figheight()
    grid = figure.add_gridspec(
        len(spec.panels),
        1,
        height_ratios=ratios,
        hspace=0.3,
        left=0.11,
        right=0.96,
        top=1 - top / total,
        bottom=(foot + 0.5) / total,
    )
    axes_list: list[Axes] = []
    for number, panel in enumerate(spec.panels):
        axes = figure.add_subplot(grid[number])
        drawn = False
        for index, mark in enumerate(panel.marks):
            _draw_mark(axes, figure, spec, mark, index)
            drawn = drawn or mark.label is not None
        _style_axes(axes, spec, panel, number == len(spec.panels) - 1, drawn)
        axes_list.append(axes)
    _x_axis(axes_list, spec)
    if spec.x_limits is not None and spec.x_kind != "category":
        low, high = (float(v) for v in pm.x_values(spec.x_limits, spec.x_kind))
        for axes in axes_list:
            axes.set_xlim(low, high)
    axes_list[0].set_title(ps.title_lines(spec.title, spec.subtitle), loc="left", fontsize=11)
    note = f" · {spec.truncation_note}" if spec.truncation_note else ""
    figure.text(0.01, 0.12 / total, ps.wrap(spec.caption + note, 170), fontsize=7, color="0.4")
    if annotated:
        _annotate(figure, spec, axes_list)
        ps.how_to_read(figure, sentences, 0.45)
    return figure
