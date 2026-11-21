"""Draw each figure mark the way a notebook chart does: matplotlib defaults, no theme.

Colours come from matplotlib's own cycle (``C0``..``C9``). A reference line is black or
grey and dashed; one highlighted line is red; up and down use green and red. Nothing is
recomputed: every number was stored upstream.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from alpha_research.figures.spec import (
    BandMark,
    BarMark,
    CandleMark,
    ErrorBarMark,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Mark,
    RuleMark,
    ScatterMark,
    TableMark,
    ZoneMark,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

_ROLE_COLOUR = {"up": "C2", "down": "C3", "feature": "C3", "reference": "0.35", "neutral": "0.3"}


def x_values(values: tuple[float, ...], kind: str) -> Any:
    """Epoch seconds become matplotlib dates on a time axis; other kinds pass through."""
    array = np.asarray(values, dtype=float)
    if kind != "time":
        return array
    return array / 86400.0  # days since 1970-01-01, matplotlib's date unit


def _kwargs(mark: Mark, cycle_index: int) -> dict[str, Any]:
    """Colour and alpha for a mark: role colour, else the next default-cycle colour."""
    if mark.role == "categorical":
        colour = f"C{(mark.palette_index or 0) % 10}"
    elif mark.role == "substrate":
        colour = "0.6"
    elif mark.role in _ROLE_COLOUR:
        colour = _ROLE_COLOUR[mark.role]
    else:
        colour = f"C{cycle_index % 10}"
    return {"color": colour, "alpha": mark.alpha, "label": mark.label}


def draw_line(axes: Axes, mark: LineMark, kind: str, cycle_index: int) -> None:
    x = x_values(mark.x, kind)
    options = _kwargs(mark, cycle_index)
    width = mark.width if mark.width is not None else (2.4 if mark.role == "feature" else 1.2)
    style = "--" if mark.dashed else "-"
    axes.plot(
        x,
        mark.y,
        drawstyle="steps-post" if mark.step else "default",
        linestyle=style,
        linewidth=width,
        **options,
    )
    if mark.fill_to is not None:
        axes.fill_between(
            x,
            mark.y,
            mark.fill_to,
            color=options["color"],
            alpha=0.3 * mark.alpha,
            linewidth=0,
        )


def draw_band(axes: Axes, mark: BandMark, kind: str, cycle_index: int) -> None:
    options = _kwargs(mark, cycle_index)
    axes.fill_between(
        x_values(mark.x, kind),
        mark.lower,
        mark.upper,
        facecolor=options["color"],
        alpha=0.25 * mark.alpha,
        label=mark.label,
        linewidth=0,
    )


def draw_candle(axes: Axes, mark: CandleMark, kind: str) -> None:
    x = x_values(mark.x, kind)
    up = np.asarray(mark.close) >= np.asarray(mark.open)
    spacing = float(np.median(np.diff(x))) if len(x) > 1 else 1.0
    for selected, colour in ((up, "C2"), (~up, "C3")):
        if not selected.any():
            continue
        axes.vlines(
            x[selected],
            np.asarray(mark.low)[selected],
            np.asarray(mark.high)[selected],
            colors=colour,
            linewidth=0.8,
        )
        top = np.maximum(np.asarray(mark.open), np.asarray(mark.close))[selected]
        bottom = np.minimum(np.asarray(mark.open), np.asarray(mark.close))[selected]
        axes.bar(
            x[selected],
            np.maximum(top - bottom, 1e-12),
            bottom=bottom,
            width=spacing * 0.7,
            color=colour,
        )


def draw_scatter(axes: Axes, mark: ScatterMark, kind: str, cycle_index: int) -> None:
    options = _kwargs(mark, cycle_index)
    colour = options.pop("color")
    face = "none" if mark.hollow else colour
    axes.scatter(
        x_values(mark.x, kind),
        mark.y,
        s=mark.size,
        marker=mark.marker,
        facecolors=face,
        edgecolors=colour,
        **options,
    )


def draw_bar(axes: Axes, mark: BarMark, kind: str, cycle_index: int) -> None:
    x = x_values(mark.x, kind)
    options = _kwargs(mark, cycle_index)
    colour: Any = options.pop("color")
    if mark.signed_colour:
        colour = ["C2" if value >= 0 else "C3" for value in mark.y]
    spacing = float(np.min(np.diff(np.sort(x)))) if len(x) > 1 else 1.0
    width = mark.width if mark.width is not None else spacing * 0.8
    draw = axes.barh if mark.horizontal else axes.bar
    bars = draw(x, mark.y, width, color=colour, **options)
    for patch, hatched in zip(bars.patches, mark.hatched or (), strict=False):
        if hatched:
            patch.set_hatch("///")


def draw_histogram(axes: Axes, mark: HistogramMark, cycle_index: int) -> None:
    options = _kwargs(mark, cycle_index)
    widths = np.diff(np.asarray(mark.edges))
    axes.bar(
        mark.edges[:-1],
        mark.counts,
        width=widths,
        align="edge",
        edgecolor="white",
        linewidth=0.5,
        **options,
    )


def draw_heatmap(axes: Axes, figure: Figure, mark: HeatmapMark) -> None:
    from matplotlib.colors import TwoSlopeNorm

    data = np.array([[np.nan if v is None else v for v in row] for row in mark.values], dtype=float)
    finite = data[np.isfinite(data)]
    centre = mark.diverging_center
    norm = None
    cmap = "viridis"
    if centre is not None and finite.size and finite.min() < centre < finite.max():
        cmap, norm = "RdYlGn", TwoSlopeNorm(vmin=finite.min(), vcenter=centre, vmax=finite.max())
    image = axes.imshow(np.ma.masked_invalid(data), aspect="auto", cmap=cmap, norm=norm)
    figure.colorbar(image, ax=axes, label=mark.colorbar_label)
    axes.set_xticks(range(len(mark.columns)), labels=list(mark.columns))
    axes.set_yticks(range(len(mark.rows)), labels=list(mark.rows))
    if mark.cell_text and len(mark.rows) * len(mark.columns) <= 150:
        for r, row in enumerate(mark.cell_text):
            for c, text in enumerate(row):
                axes.text(c, r, text, ha="center", va="center", fontsize=6.5)


def draw_zone(axes: Axes, mark: ZoneMark, kind: str, cycle_index: int) -> None:
    low, high = (float(v) for v in x_values((mark.x0, mark.x1), kind))
    colour = _kwargs(mark, cycle_index)["color"]
    if mark.y0 is None or mark.y1 is None:
        axes.axvspan(low, high, facecolor=colour, alpha=0.15 * mark.alpha, lw=0)
    else:
        axes.fill_between([low, high], mark.y0, mark.y1, color=colour, alpha=0.15, lw=0)


def draw_rule(axes: Axes, mark: RuleMark, kind: str) -> None:
    colour = _ROLE_COLOUR.get(mark.role, "0.35")
    width = mark.width if mark.width is not None else 1.2
    style = "--" if mark.dashed else "-"
    if mark.orientation == "vertical":
        position = float(x_values((mark.position,), kind)[0])
        axes.axvline(position, color=colour, linestyle=style, linewidth=width, label=mark.label)
    else:
        axes.axhline(
            mark.position, color=colour, linestyle=style, linewidth=width, label=mark.label
        )


def draw_errorbar(axes: Axes, mark: ErrorBarMark) -> None:
    y = np.arange(len(mark.categories))
    point = np.asarray(mark.point)
    err = np.vstack([point - np.asarray(mark.lower), np.asarray(mark.upper) - point])
    axes.errorbar(point, y, xerr=err, fmt="o", capsize=3, label=mark.label)
    axes.set_yticks(y, labels=list(mark.categories))
    axes.invert_yaxis()


def draw_table(axes: Axes, mark: TableMark) -> None:
    axes.axis("off")
    cells = [list(row) for row in mark.rows] or [["no rows"] * len(mark.columns)]
    table = axes.table(
        cellText=cells, colLabels=list(mark.columns), loc="upper left", cellLoc="left"
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.auto_set_column_width(list(range(len(mark.columns))))
