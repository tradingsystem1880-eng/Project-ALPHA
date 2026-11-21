"""The one standard figure look, and the annotation primitives for the annotated variant.

A plain figure is what a quant draws in a research notebook: white face, matplotlib's own
default colour cycle, a light grid, a plain title, labelled axes and a legend. Nothing here
chooses a colour of its own except grey for reference marks. The annotated variant adds
callouts, labelled bands, a hatched held-back band and a "How to read this chart" box.

Display only: every number drawn here arrives from a stored run artefact.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

FIGURE_WIDTH_IN: Final = 12.0
DPI: Final = 100
BOX: Final = {"boxstyle": "square", "fc": "white", "ec": "0.4", "lw": 0.8}
ARROW: Final = {"arrowstyle": "->", "color": "0.2", "lw": 1.0}
#: Named crisis windows drawn as labelled bands when they fall inside a time axis.
CRISES: Final = (
    ("2000-03-01", "2002-10-31", "2000-02 bust"),
    ("2007-10-01", "2009-03-31", "2008 crisis"),
    ("2020-02-01", "2020-04-30", "2020"),
)
#: Slots for callout boxes: axes-fraction anchor plus alignment, always inside the axes.
SLOTS: Final = (
    (0.98, 0.97, "right", "top"),
    (0.02, 0.97, "left", "top"),
    (0.98, 0.03, "right", "bottom"),
    (0.02, 0.03, "left", "bottom"),
    (0.5, 0.97, "center", "top"),
    (0.5, 0.03, "center", "bottom"),
    (0.98, 0.5, "right", "center"),
    (0.02, 0.5, "left", "center"),
)
_WRAP: Final = 34
HOW_WIDTH: Final = 165


def pct(value: float, places: int = 1) -> str:
    return f"{value * 100:.{places}f}%"


def month(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m")


def new_figure(height_in: float) -> Figure:
    """A pyplot-free figure on matplotlib defaults: white face, default cycle and fonts."""
    import matplotlib

    matplotlib.use("Agg", force=True)
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(FIGURE_WIDTH_IN, height_in), dpi=DPI, facecolor="white")
    FigureCanvasAgg(figure)
    return figure


def to_bytes(figure: Figure, fmt: str) -> bytes:
    """Deterministic bytes: no date, no software stamp, a pinned SVG hash salt."""
    import matplotlib

    buffer = BytesIO()
    meta = {"Software": None} if fmt == "png" else {"Date": None}
    with matplotlib.rc_context({"svg.hashsalt": "alpha-figures", "svg.fonttype": "path"}):
        figure.savefig(buffer, format=fmt, dpi=DPI, metadata=meta, facecolor="white")
    figure.clear()
    return buffer.getvalue()


def wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width))


def _coverage(axes: Axes, rect: tuple[float, float, float, float]) -> int:
    """How many plotted vertices fall inside a candidate box (axes-fraction coordinates)."""
    inverse = axes.transAxes.inverted()
    left, bottom, right, top = rect
    count = 0
    for line in axes.get_lines():
        data = np.asarray(line.get_xydata(), dtype=float)
        if len(data) == 0:
            continue
        points = inverse.transform(axes.transData.transform(data))
        inside = (
            (points[:, 0] >= left)
            & (points[:, 0] <= right)
            & (points[:, 1] >= bottom)
            & (points[:, 1] <= top)
        )
        count += int(inside.sum())
    for container in axes.containers:
        for patch in getattr(container, "patches", []):
            box = patch.get_window_extent()
            low = inverse.transform((box.x0, box.y0))
            high = inverse.transform((box.x1, box.y1))
            if low[0] < right and high[0] > left and low[1] < top and high[1] > bottom:
                count += 5
    return count


def _slot_rect(
    slot: tuple[float, float, str, str], width: float, height: float
) -> tuple[float, float, float, float]:
    x, y, ha, va = slot
    left = x if ha == "left" else x - width if ha == "right" else x - width / 2
    bottom = y if va == "bottom" else y - height if va == "top" else y - height / 2
    return (left, bottom, left + width, bottom + height)


def callout(
    axes: Axes, text: str, xy: tuple[float, float], used: list[int], *, fontsize: float = 8.5
) -> None:
    """A boxed note with an arrow to ``xy`` (data coordinates), kept off the plotted data."""
    body = wrap(text, _WRAP)
    lines = body.count("\n") + 1
    width, height = 0.3, 0.06 + 0.05 * lines
    px, py = axes.transAxes.inverted().transform(axes.transData.transform(xy))

    def cost(i: int) -> tuple[int, float]:
        rect = _slot_rect(SLOTS[i], width, height)
        return _coverage(axes, rect), (SLOTS[i][0] - px) ** 2 + (SLOTS[i][1] - py) ** 2

    best = min((i for i in range(len(SLOTS)) if i not in used), key=cost, default=0)
    used.append(best)
    x, y, ha, va = SLOTS[best]
    axes.annotate(
        body,
        xy=xy,
        xycoords="data",
        xytext=(x, y),
        textcoords="axes fraction",
        fontsize=fontsize,
        ha=ha,
        va=va,
        bbox=BOX,
        arrowprops=ARROW,
        zorder=10,
        annotation_clip=False,
    )


def band(
    axes: Axes, x0: float, x1: float, label: str, *, alpha: float = 0.15, y: float = 0.985
) -> None:
    """A labelled shaded span over the full axes height (data x coordinates)."""
    axes.axvspan(
        x0,
        x1,
        facecolor="0.5",
        alpha=alpha,
        lw=0,
    )
    axes.text(
        x0,
        y,
        " " + label,
        transform=axes.get_xaxis_transform(),
        ha="left",
        va="top",
        fontsize=8,
        color="0.25",
        clip_on=True,
    )


def held_back_band(axes: Axes, start: float, end: float) -> None:
    """The hatched band for data the run never used: the reserved period."""
    axes.axvspan(start, end, facecolor="none", hatch="///", edgecolor="0.6", lw=0)
    axes.text(
        (start + end) / 2,
        0.5,
        "held back, not used",
        transform=axes.get_xaxis_transform(),
        rotation=90,
        ha="center",
        va="center",
        fontsize=9,
        color="0.25",
        bbox={"fc": "white", "ec": "none", "alpha": 0.85},
    )


def box_height(sentences: list[str], width_chars: int = HOW_WIDTH) -> float:
    """Inches the "How to read this chart" box needs for these sentences."""
    lines = wrap(" ".join(sentences), width_chars).count("\n") + 1
    return 0.6 + 0.19 * lines


def how_to_read(
    figure: Figure, sentences: list[str], bottom_in: float, width_chars: int = HOW_WIDTH
) -> None:
    """Draw the explanation box with its lower edge ``bottom_in`` above the figure foot."""
    body = wrap(" ".join(sentences), width_chars)
    total = figure.get_figheight()
    figure.text(
        0.01,
        bottom_in / total,
        "How to read this chart\n" + body,
        fontsize=9,
        ha="left",
        va="bottom",
        linespacing=1.35,
        bbox={"fc": "0.97", "ec": "0.6", "lw": 0.8, "boxstyle": "square,pad=0.5"},
    )


def title_lines(title: str, subtitle: str) -> str:
    return f"{title}\n{wrap(subtitle, 120)}" if subtitle else title


def hide_alternate_ticks(axes: Axes, which: str = "x", limit: int = 14) -> None:
    """Thin crowded category labels so no two tick labels overlap."""
    labels: list[Any] = axes.get_xticklabels() if which == "x" else axes.get_yticklabels()
    step = max(1, -(-len(labels) // limit))
    for index, label in enumerate(labels):
        label.set_visible(index % step == 0)
