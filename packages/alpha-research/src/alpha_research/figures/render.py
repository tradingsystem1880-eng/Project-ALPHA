"""Byte-stable Matplotlib rendering of a :class:`FigureSpec`.

The visual grammar is mechanical rather than a matter of taste. Price and other context
are drawn in a thin recessive gray (``substrate``); the series the figure is about takes
the one saturated accent (``subject``); a *detected* thing takes gold and always carries
its value in place (``feature``); baselines and thresholds are dashed and muted
(``reference``). A reader can therefore tell, without a caption, which marks are evidence
and which are backdrop.

Determinism is designed in, not hoped for. Every known source of drift is closed:

* the Agg/SVG backends are forced, and ``pyplot`` is never touched (it carries global
  figure state and a GUI backend probe);
* rcParams are seeded from ``rcParamsDefault``, so a developer's ``matplotlibrc`` cannot
  leak into an artifact;
* ``svg.hashsalt`` is pinned, because its default is a per-process UUID that lands in
  every element id;
* ``Date``/``Software`` metadata are suppressed, removing the SVG ``<dc:date>`` stamp and
  the PNG ``tEXt`` chunk;
* the bundled DejaVu faces are required explicitly, so a missing font fails loudly
  instead of silently substituting and reflowing every label;
* ``tight_layout``/``bbox_inches="tight"`` are never used -- both re-measure text and make
  the output depend on font rasterisation;
* ticks are placed by this module, not by a locator heuristic, and formatted with ASCII
  ``strftime`` codes that carry no locale.

Nothing here computes a statistic. See :mod:`alpha_research.figures.spec`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any, Final, Literal

from alpha_core import DataError
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
    ValueLabel,
    ZoneMark,
)
from alpha_research.figures.theme import Theme, load_theme
from alpha_research.figures.version import RENDERER_VERSION

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps matplotlib out of import time
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

FigureFormat = Literal["svg", "png"]

#: Role -> (colour attribute, line weight, z-order). The single table that makes the look
#: consistent across every figure in the catalogue.
_ROLE_STYLE: Final[dict[str, tuple[str, float, int]]] = {
    "substrate": ("substrate", 0.8, 1),
    "reference": ("muted", 0.9, 2),
    "neutral": ("ink_dim", 1.2, 2),
    "subject": ("accent", 1.6, 3),
    "up": ("up", 1.4, 3),
    "down": ("down", 1.4, 3),
    "categorical": ("accent", 1.5, 3),
    "feature": ("gold", 2.0, 4),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class FigureSize:
    width_in: float
    height_in: float
    dpi: int = 144

    def __post_init__(self) -> None:
        if self.width_in <= 0 or self.height_in <= 0:
            raise DataError("FigureSize dimensions must be positive")
        if self.dpi <= 0:
            raise DataError("FigureSize.dpi must be positive")

    def as_key(self) -> dict[str, float | int]:
        return {"width_in": self.width_in, "height_in": self.height_in, "dpi": self.dpi}


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderOptions:
    theme: Theme
    size: FigureSize
    fmt: FigureFormat = "svg"
    background: Literal["theme", "transparent"] = "theme"
    #: Embedding glyph outlines makes bytes viewer-independent but turns text into paths.
    #: Structural tests flip this off so they can assert on real ``<text>`` elements;
    #: production always leaves it on, and the accompanying JSON metadata plus the host
    #: page's ``alt``/``figcaption`` carry the accessible text.
    text_as_paths: bool = True


#: Vertical space reserved for title + subtitle, and for the x-axis label, the one-line
#: answer and the provenance strip. Fixed inches so panel height stays honest as panels
#: are added, and so no layout engine has to measure text to decide.
HEADER_IN: Final = 0.86
FOOTER_IN: Final = 1.02


def default_size(panel_count: int) -> FigureSize:
    """A height that grows with stacked panels but keeps a constant panel aspect."""
    if panel_count < 1:
        raise DataError("a figure needs at least one panel")
    return FigureSize(width_in=11.0, height_in=HEADER_IN + FOOTER_IN + 1.55 * panel_count)


def _colour(theme: Theme, mark: Mark) -> str:
    if mark.role == "categorical":
        assert mark.palette_index is not None  # validated in spec
        return theme.series_colour(mark.palette_index)
    attribute, _, _ = _ROLE_STYLE[mark.role]
    return str(getattr(theme, attribute))


def _weight(mark: Mark) -> float:
    width = getattr(mark, "width", None)
    if width is not None:
        return float(width)
    return _ROLE_STYLE[mark.role][1]


def _zorder(mark: Mark) -> int:
    return _ROLE_STYLE[mark.role][2] + mark.z


def _rc(options: RenderOptions) -> dict[str, Any]:
    theme = options.theme
    face = "none" if options.background == "transparent" else theme.bg
    return {
        "figure.facecolor": face,
        "figure.edgecolor": face,
        "savefig.facecolor": face,
        "savefig.edgecolor": face,
        "savefig.transparent": options.background == "transparent",
        "axes.facecolor": "none",
        "axes.edgecolor": theme.line,
        "axes.labelcolor": theme.ink_dim,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": theme.grid,
        "grid.linewidth": 0.6,
        "grid.alpha": 1.0,
        "text.color": theme.ink,
        "xtick.color": theme.muted,
        "ytick.color": theme.muted,
        "xtick.labelcolor": theme.muted,
        "ytick.labelcolor": theme.muted,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "font.family": "sans-serif",
        "font.sans-serif": [theme.font_family],
        "font.monospace": [theme.font_mono],
        "font.size": theme.base_font_pt,
        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.handletextpad": 0.5,
        "legend.columnspacing": 1.2,
        "legend.labelcolor": theme.ink_dim,
        "legend.fontsize": theme.base_font_pt - 0.5,
        "lines.solid_capstyle": "round",
        "path.simplify": False,  # simplification thresholds have drifted between releases
        "svg.fonttype": "path" if options.text_as_paths else "none",
        "svg.hashsalt": f"alpha-figures-v{RENDERER_VERSION}",
        "timezone": "UTC",
        "date.autoformatter.day": "%Y-%m-%d",
    }


def _require_fonts(theme: Theme) -> None:
    from matplotlib import font_manager

    for family in (theme.font_family, theme.font_mono):
        try:
            font_manager.findfont(family, fallback_to_default=False)
        except Exception as error:  # noqa: BLE001 - re-raised as a typed platform error
            raise DataError(
                f"figure font {family!r} is unavailable; figures would silently reflow. "
                "It ships inside the pinned matplotlib wheel -- check the environment."
            ) from error


def _time_ticks(low: float, high: float) -> tuple[list[float], list[str]]:
    """Evenly spaced, ASCII-formatted ticks placed here rather than by a locator.

    Positions are inset from the axis limits: a label centred on the very edge is drawn
    half outside the axes and gets clipped by the figure boundary.
    """
    span_days = (high - low) / 86400.0
    fmt = "%Y" if span_days > 2200 else "%Y-%m" if span_days > 120 else "%Y-%m-%d"
    count = 6
    inset = 0.045
    span = high - low
    positions = [
        low + span * (inset + (1 - 2 * inset) * index / (count - 1)) for index in range(count)
    ]
    labels = [datetime.fromtimestamp(value, tz=UTC).strftime(fmt) for value in positions]
    return positions, labels


def _apply_value_label(
    axes: Axes,
    theme: Theme,
    label: ValueLabel,
    x: float,
    y: float,
    colour: str,
    *,
    va: Literal["top", "center", "bottom"] = "center",
    dy_pt: float | None = None,
) -> None:
    axes.annotate(
        label.text,
        xy=(x, y),
        xytext=(label.dx_pt, label.dy_pt if dy_pt is None else dy_pt),
        textcoords="offset points",
        ha=label.ha,
        va=va,
        fontsize=theme.base_font_pt - 1.0,
        color=colour,
        zorder=9,
        annotation_clip=False,
    )


def _draw_line(axes: Axes, theme: Theme, mark: LineMark) -> None:
    colour, weight = _colour(theme, mark), _weight(mark)
    plot = axes.step if mark.step else axes.plot
    kwargs: dict[str, Any] = {
        "color": colour,
        "linewidth": weight,
        "alpha": mark.alpha,
        "zorder": _zorder(mark),
        "label": mark.label,
        "solid_joinstyle": "round",
    }
    if mark.step:
        kwargs["where"] = "post"
    if mark.dashed:
        kwargs["dashes"] = (4, 3)
    plot(mark.x, mark.y, **kwargs)
    if mark.fill_to is not None:
        axes.fill_between(
            mark.x,
            mark.y,
            mark.fill_to,
            color=colour,
            alpha=min(0.22, mark.alpha * 0.22),
            linewidth=0,
            zorder=_zorder(mark) - 1,
            step="post" if mark.step else None,
        )
    if mark.end_label is not None:
        _apply_value_label(axes, theme, mark.end_label, mark.x[-1], mark.y[-1], colour)


def _draw_band(axes: Axes, theme: Theme, mark: BandMark) -> None:
    axes.fill_between(
        mark.x,
        mark.lower,
        mark.upper,
        color=_colour(theme, mark),
        alpha=mark.alpha,
        linewidth=0,
        zorder=_zorder(mark) - 1,
        label=mark.label,
    )


def _draw_candle(axes: Axes, theme: Theme, mark: CandleMark) -> None:
    if len(mark.x) > 1:
        widths = [b - a for a, b in zip(mark.x, mark.x[1:], strict=False)]
        body = min(widths) * 0.62
    else:
        body = 0.62
    for index in range(len(mark.x)):
        rising = mark.close[index] >= mark.open[index]
        colour = theme.up if rising else theme.down
        axes.vlines(
            mark.x[index],
            mark.low[index],
            mark.high[index],
            color=colour,
            linewidth=0.6,
            alpha=mark.alpha,
            zorder=_zorder(mark),
        )
        low = min(mark.open[index], mark.close[index])
        span = mark.high[index] - mark.low[index]
        # A doji has zero body; give it a hairline so the session stays visible.
        height = abs(mark.close[index] - mark.open[index]) or span * 0.01
        axes.add_patch(
            _rectangle(
                mark.x[index] - body / 2, low, body, height, colour, mark.alpha, _zorder(mark)
            )
        )


def _rectangle(
    x: float, y: float, width: float, height: float, colour: str, alpha: float, z: int
) -> Any:
    from matplotlib.patches import Rectangle

    return Rectangle(
        (x, y), width, height, facecolor=colour, edgecolor="none", alpha=alpha, zorder=z
    )


def _draw_scatter(axes: Axes, theme: Theme, mark: ScatterMark) -> None:
    colour = _colour(theme, mark)
    axes.scatter(
        mark.x,
        mark.y,
        s=mark.size,
        marker=mark.marker,
        facecolors="none" if mark.hollow else colour,
        edgecolors=colour,
        linewidths=1.0,
        alpha=mark.alpha,
        zorder=_zorder(mark) + 1,
        label=mark.label,
    )


def _draw_bar(axes: Axes, theme: Theme, mark: BarMark) -> None:
    if mark.signed_colour:
        colours = [theme.up if value >= 0 else theme.down for value in mark.y]
    else:
        colours = [_colour(theme, mark)] * len(mark.y)
    hatches = mark.hatched or ((False,) * len(mark.x))
    width = mark.width
    if width is None:
        gaps = [b - a for a, b in zip(mark.x, mark.x[1:], strict=False)]
        width = (min(gaps) * 0.82) if gaps else 0.82
    draw = axes.barh if mark.horizontal else axes.bar
    for index, (position, value) in enumerate(zip(mark.x, mark.y, strict=True)):
        draw(
            position,
            value,
            width,
            color="none" if hatches[index] else colours[index],
            edgecolor=theme.muted if hatches[index] else "none",
            hatch="///" if hatches[index] else None,
            linewidth=0.6 if hatches[index] else 0,
            alpha=mark.alpha,
            zorder=_zorder(mark),
            label=mark.label if index == 0 else None,
        )


def _draw_histogram(axes: Axes, theme: Theme, mark: HistogramMark) -> None:
    lefts = mark.edges[:-1]
    widths = [b - a for a, b in zip(mark.edges, mark.edges[1:], strict=False)]
    axes.bar(
        lefts,
        mark.counts,
        width=widths,
        align="edge",
        color=_colour(theme, mark),
        alpha=mark.alpha,
        linewidth=0,
        zorder=_zorder(mark),
        label=mark.label,
    )


def _draw_heatmap(axes: Axes, theme: Theme, mark: HeatmapMark, figure: Figure) -> None:
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm

    grid = np.array(
        [[math.nan if value is None else value for value in row] for row in mark.values],
        dtype=float,
    )
    finite = grid[np.isfinite(grid)]
    if finite.size == 0:
        # Every cell is absent -- an optimisation sweep where nothing completed, say. The
        # grid still has to be drawn: the reader needs to see that the configurations were
        # tried and failed, which a raised error or an omitted figure would both hide.
        finite = np.zeros(1, dtype=float)
    if mark.diverging_center is not None:
        reach = (
            max(
                abs(float(finite.min()) - mark.diverging_center),
                abs(float(finite.max()) - mark.diverging_center),
            )
            or 1.0
        )
        cmap = LinearSegmentedColormap.from_list(
            "alpha_diverging", [theme.down, theme.bg, theme.up]
        )
        norm: Normalize = TwoSlopeNorm(
            vmin=mark.diverging_center - reach,
            vcenter=mark.diverging_center,
            vmax=mark.diverging_center + reach,
        )
    else:
        cmap = LinearSegmentedColormap.from_list("alpha_sequential", [theme.bg, theme.accent])
        norm = Normalize(vmin=float(finite.min()), vmax=float(finite.max()))
    # `with_extremes`, not `set_bad`: the latter is pending deprecation, and this repo
    # turns warnings into errors, so a warning here is a broken figure.
    shaded = cmap.with_extremes(bad=theme.panel)
    masked = np.ma.masked_invalid(grid)
    mesh = axes.pcolormesh(
        np.arange(len(mark.columns) + 1),
        np.arange(len(mark.rows) + 1),
        masked,
        cmap=shaded,
        norm=norm,
        edgecolors=theme.bg,
        linewidth=1.5,
        rasterized=False,  # a rasterised artist embeds a PNG blob and breaks byte stability
        zorder=_zorder(mark),
    )
    axes.set_xticks([index + 0.5 for index in range(len(mark.columns))], labels=list(mark.columns))
    axes.set_yticks([index + 0.5 for index in range(len(mark.rows))], labels=list(mark.rows))
    axes.invert_yaxis()
    axes.grid(visible=False)
    for spine in axes.spines.values():
        spine.set_visible(False)
    if mark.cell_text:
        for row_index, row in enumerate(mark.cell_text):
            for col_index, text in enumerate(row):
                if not text:
                    continue
                axes.text(
                    col_index + 0.5,
                    row_index + 0.5,
                    text,
                    ha="center",
                    va="center",
                    fontsize=theme.base_font_pt - 1.5,
                    color=theme.ink,
                    zorder=_zorder(mark) + 1,
                )
    bar = figure.colorbar(mesh, ax=axes, pad=0.012, fraction=0.026)
    bar.set_label(mark.colorbar_label, color=theme.ink_dim, fontsize=theme.base_font_pt - 0.5)
    # The outline picks up axes.edgecolor from rcParams, which is already theme.line.
    bar.ax.tick_params(colors=theme.muted, labelsize=theme.base_font_pt - 1.5)


def _draw_zone(axes: Axes, theme: Theme, mark: ZoneMark) -> None:
    colour = _colour(theme, mark)
    if mark.y0 is None or mark.y1 is None:
        axes.axvspan(
            mark.x0,
            mark.x1,
            color=colour,
            alpha=mark.alpha,
            linewidth=0,
            zorder=0,
            label=mark.label,
        )
    else:
        axes.add_patch(
            _rectangle(
                mark.x0, mark.y0, mark.x1 - mark.x0, mark.y1 - mark.y0, colour, mark.alpha, 0
            )
        )
    if mark.corner_label is not None:
        _apply_value_label(axes, theme, mark.corner_label, mark.x0, axes.get_ylim()[1], colour)


def _draw_rule(axes: Axes, theme: Theme, mark: RuleMark) -> None:
    colour, weight = _colour(theme, mark), _weight(mark)
    line = axes.axvline if mark.orientation == "vertical" else axes.axhline
    handle = line(
        mark.position,
        color=colour,
        linewidth=weight,
        alpha=mark.alpha,
        zorder=_zorder(mark),
        label=mark.label,
    )
    if mark.dashed:
        handle.set_dashes([4.0, 3.0])
    if mark.annotate is not None:
        # Sit the label clear of its own line and inset from the axis edge, so a full-width
        # rule does not end up with its value overprinted on the dashes or clipped away.
        if mark.orientation == "vertical":
            low, high = axes.get_ylim()
            _apply_value_label(
                axes, theme, mark.annotate, mark.position, high, colour, va="top", dy_pt=-4.0
            )
            del low
        else:
            left, right = axes.get_xlim()
            anchor = right - (right - left) * 0.02
            _apply_value_label(
                axes, theme, mark.annotate, anchor, mark.position, colour, va="bottom", dy_pt=4.0
            )


def _draw_errorbar(axes: Axes, theme: Theme, mark: ErrorBarMark) -> None:
    colour = _colour(theme, mark)
    positions = list(range(len(mark.categories)))
    for index, position in enumerate(positions):
        low, high, point = mark.lower[index], mark.upper[index], mark.point[index]
        # Colour by what the interval actually says, which is the whole point of a forest plot.
        tone = theme.up if low > 0 else theme.down if high < 0 else theme.gold
        axes.hlines(position, low, high, color=tone, linewidth=1.6, zorder=_zorder(mark))
        axes.vlines([low, high], position - 0.12, position + 0.12, color=tone, linewidth=1.2)
        axes.scatter([point], [position], s=26, color=tone, zorder=_zorder(mark) + 1)
    axes.set_yticks(positions, labels=list(mark.categories))
    axes.invert_yaxis()
    del colour


def _draw_table(axes: Axes, theme: Theme, mark: TableMark) -> None:
    axes.axis("off")
    if not mark.rows:
        axes.text(0.0, 0.5, "no rows", color=theme.muted, fontsize=theme.base_font_pt, va="center")
        return
    # First column reads as a label, the rest as figures, so they right-align.
    rest: list[Literal["left", "right"]] = ["right"] * (len(mark.columns) - 1)
    default_align: tuple[Literal["left", "right"], ...] = ("left", *rest)
    align = mark.align or default_align
    columns = len(mark.columns)
    widths = [1.0 / columns] * columns
    top, row_height = 0.95, min(0.16, 0.9 / (len(mark.rows) + 1))
    for index, name in enumerate(mark.columns):
        axes.text(
            sum(widths[:index]) + (widths[index] if align[index] == "right" else 0.0),
            top,
            name,
            ha=align[index],
            va="top",
            fontsize=theme.base_font_pt - 1.0,
            color=theme.faint,
            transform=axes.transAxes,
        )
    for row_index, row in enumerate(mark.rows):
        y = top - row_height * (row_index + 1)
        for index, cell in enumerate(row):
            axes.text(
                sum(widths[:index]) + (widths[index] if align[index] == "right" else 0.0),
                y,
                cell,
                ha=align[index],
                va="top",
                fontsize=theme.base_font_pt - 0.5,
                color=theme.ink_dim,
                family="monospace",
                transform=axes.transAxes,
            )


def _draw_mark(axes: Axes, figure: Figure, theme: Theme, mark: Mark) -> None:
    match mark:
        case LineMark():
            _draw_line(axes, theme, mark)
        case BandMark():
            _draw_band(axes, theme, mark)
        case CandleMark():
            _draw_candle(axes, theme, mark)
        case ScatterMark():
            _draw_scatter(axes, theme, mark)
        case BarMark():
            _draw_bar(axes, theme, mark)
        case HistogramMark():
            _draw_histogram(axes, theme, mark)
        case HeatmapMark():
            _draw_heatmap(axes, theme, mark, figure)
        case ZoneMark():
            _draw_zone(axes, theme, mark)
        case RuleMark():
            _draw_rule(axes, theme, mark)
        case ErrorBarMark():
            _draw_errorbar(axes, theme, mark)
        case TableMark():
            _draw_table(axes, theme, mark)
        case _:  # pragma: no cover - the union is exhaustive
            raise DataError(f"no renderer for mark {type(mark).__name__}")


def _fit_label(label: str, budget: int) -> str:
    """Wrap a y-label to fit its panel, and only elide when wrapping cannot save it.

    A y-label is rotated, so the panel's HEIGHT is what constrains it -- which is why a
    short stacked panel could only show "Ratio (dim…". Rotated text has width to spare,
    though, so a second line costs nothing and keeps the unit the label exists to state.
    """
    if len(label) <= budget:
        return label
    words = label.split(" ")
    candidates: list[int] = []
    # Break before the parenthetical first: "Price" / "(native quote)" keeps the quantity
    # and its unit each whole, where a purely balanced split would cut "(native" from
    # "quote)". Only if that does not fit do we fall back to the most even break.
    paren = next((index for index, word in enumerate(words) if word.startswith("(")), None)
    if paren is not None and 0 < paren < len(words):
        candidates.append(paren)
    if len(words) > 1:
        candidates.append(
            min(
                range(1, len(words)),
                key=lambda cut: max(len(" ".join(words[:cut])), len(" ".join(words[cut:]))),
            )
        )
    for cut in candidates:
        first, second = " ".join(words[:cut]), " ".join(words[cut:])
        if max(len(first), len(second)) <= budget:
            return f"{first}\n{second}"
    return label[: budget - 1] + "…"


def _finish_panel(
    axes: Axes,
    theme: Theme,
    panel: Panel,
    spec: FigureSpec,
    last: bool,
    panel_count: int = 1,
    panel_height_in: float | None = None,
) -> None:
    size = theme.base_font_pt - (0.5 if panel_count < 4 else 1.5)
    # A y-label is rotated, so what constrains it is the panel's HEIGHT, not the panel
    # count. Budgeting by count alone let a four-panel figure print 22-character labels
    # into 0.9-inch panels, where consecutive labels ran into each other and into the
    # panel above. One character occupies roughly 0.6 of the font size in points.
    if panel_height_in is None:
        budget = 34 if panel_count < 4 else 22
    else:
        budget = max(8, int(panel_height_in * 72.0 / (size * 0.62)))
    axes.set_ylabel(_fit_label(panel.y_label, budget), fontsize=size)
    if panel.y_scale != "linear":
        axes.set_yscale(panel.y_scale)
    if panel.y_limits is not None:
        axes.set_ylim(*panel.y_limits)
    if panel.y_percent:
        from matplotlib.ticker import FuncFormatter

        axes.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
    if panel.y_zero_rule:
        axes.axhline(0.0, color=theme.line, linewidth=0.8, zorder=1)
    if panel.note is not None:
        # The note sits inside the axes, so it can land on the data -- and it did, straight
        # across the price line. A panel-coloured box behind it keeps both readable rather
        # than choosing which one to lose.
        axes.text(
            0.006,
            0.04,
            panel.note,
            transform=axes.transAxes,
            fontsize=theme.base_font_pt - 1.5,
            color=theme.gold,
            va="bottom",
            zorder=6,
            bbox={
                "facecolor": theme.panel,
                "edgecolor": theme.line,
                "boxstyle": "square,pad=0.28",
                "linewidth": 0.6,
            },
        )
    entries = panel.legend_entries
    if panel.legend and entries:
        axes.legend(loc="upper left", ncol=min(len(entries), 4), fontsize=theme.base_font_pt - 0.5)
    if last:
        axes.set_xlabel(spec.x_label, fontsize=theme.base_font_pt - 0.5)
    else:
        axes.tick_params(labelbottom=False)


def _apply_x_axis(axes_list: list[Axes], spec: FigureSpec, theme: Theme) -> None:
    if spec.x_kind == "category":
        positions = list(range(len(spec.x_categories)))
        axes_list[-1].set_xticks(positions, labels=list(spec.x_categories))
        return
    if spec.x_kind != "time":
        return
    if any(isinstance(mark, HeatmapMark) for panel in spec.panels for mark in panel.marks):
        return
    low, high = axes_list[0].get_xlim()
    if spec.x_limits is not None:
        low, high = spec.x_limits
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        return
    tick_positions, labels = _time_ticks(low, high)
    axes_list[-1].set_xticks(tick_positions, labels=labels)
    for axes in axes_list:
        axes.set_xlim(low, high)


def render_figure(spec: FigureSpec, options: RenderOptions | None = None) -> bytes:
    """Render ``spec`` to deterministic image bytes.

    Pure: no filesystem, no clock, no network. Publication and caching belong to the CLI.
    """
    import matplotlib

    matplotlib.use("Agg", force=True)
    from matplotlib import rc_context
    from matplotlib.figure import Figure

    resolved = options or RenderOptions(theme=load_theme(), size=default_size(spec.panel_count))
    theme = resolved.theme
    # Seed from the shipped defaults, never the live rcParams: a developer's matplotlibrc
    # would otherwise silently change the bytes of a published artifact.
    defaults: dict[str, Any] = dict(matplotlib.rcParamsDefault.items())
    style: dict[str, Any] = {**defaults, **_rc(resolved)}
    # matplotlib types every rc key as one exhaustive Literal; a plain str-keyed dict
    # is the only practical way to compose one.
    with rc_context(style):  # type: ignore[arg-type]
        _require_fonts(theme)
        figure = Figure(figsize=(resolved.size.width_in, resolved.size.height_in))
        _attach_canvas(figure, resolved.fmt)
        grid = figure.add_gridspec(
            nrows=spec.panel_count,
            ncols=1,
            height_ratios=[panel.height_ratio for panel in spec.panels],
            hspace=0.12,
        )
        shares = not any(
            isinstance(mark, HeatmapMark | ErrorBarMark | TableMark)
            for panel in spec.panels
            for mark in panel.marks
        )
        axes_list: list[Axes] = []
        plot_in = resolved.size.height_in - HEADER_IN - FOOTER_IN
        ratio_total = sum(panel.height_ratio for panel in spec.panels) or 1.0
        for index, panel in enumerate(spec.panels):
            axes = figure.add_subplot(
                grid[index, 0], sharex=axes_list[0] if (shares and axes_list) else None
            )
            for mark in sorted(panel.marks, key=_zorder):
                _draw_mark(axes, figure, theme, mark)
            _finish_panel(
                axes,
                theme,
                panel,
                spec,
                last=index == spec.panel_count - 1,
                panel_count=spec.panel_count,
                panel_height_in=plot_in * panel.height_ratio / ratio_total,
            )
            axes_list.append(axes)
        if shares:
            _apply_x_axis(axes_list, spec, theme)
        _draw_chrome(figure, theme, spec, resolved)
        return _save(figure, resolved, spec)


def _attach_canvas(figure: Figure, fmt: FigureFormat) -> None:
    if fmt == "svg":
        from matplotlib.backends.backend_svg import FigureCanvasSVG

        FigureCanvasSVG(figure)
    else:
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        FigureCanvasAgg(figure)


def _draw_chrome(figure: Figure, theme: Theme, spec: FigureSpec, options: RenderOptions) -> None:
    """Title, subtitle, the one-line answer, and the provenance strip.

    Positions are fixed fractions rather than a layout engine's output: ``tight_layout``
    measures rendered text, which makes the geometry depend on font rasterisation.
    """
    height = options.size.height_in
    left = 0.055
    # Reserved bands, in inches, converted to figure fractions. Everything is measured from
    # the physical page rather than from rendered text extents, so the geometry cannot shift
    # with font rasterisation.
    header_in = HEADER_IN
    footer_in = FOOTER_IN
    figure.text(
        left,
        1 - 0.28 / height,
        spec.title,
        ha="left",
        va="top",
        fontsize=theme.base_font_pt + 3.5,
        fontweight="bold",
        color=theme.ink,
    )
    figure.text(
        left,
        1 - 0.54 / height,
        spec.subtitle,
        ha="left",
        va="top",
        fontsize=theme.base_font_pt - 0.5,
        color=theme.muted,
    )
    answer = spec.plain_language_answer
    if spec.truncation_note:
        answer = f"{answer}  ({spec.truncation_note})"
    figure.text(
        left,
        0.40 / height,
        answer,
        ha="left",
        va="bottom",
        fontsize=theme.base_font_pt - 0.5,
        color=theme.ink_dim,
    )
    if spec.caption:
        figure.text(
            left,
            0.16 / height,
            spec.caption,
            ha="left",
            va="bottom",
            fontsize=theme.base_font_pt - 2.0,
            color=theme.faint,
            family="monospace",
        )
    # Reserve a right gutter: an end-of-line value label is drawn outside the axes and
    # would otherwise be clipped by the page edge -- exactly the label most worth reading.
    figure.subplots_adjust(
        left=left + 0.005,
        right=0.952,
        top=1 - header_in / height,
        bottom=footer_in / height,
    )


def _metadata(spec: FigureSpec) -> dict[str, str | None]:
    """Teaching text travels with the file, and no clock does.

    ``Date`` and ``Software`` are explicitly ``None``: the first removes the SVG
    ``<dc:date>`` element, the second the PNG ``tEXt`` software chunk. Both would
    otherwise make two identical renders differ.
    """
    return {
        "Date": None,
        "Software": None,
        "Title": spec.title,
        "Description": spec.plain_language_answer,
        "Question": spec.question,
        "Uncertainty": spec.uncertainty,
        "Caveat": spec.caveat,
        "FigureID": spec.figure_id,
        "RendererVersion": str(RENDERER_VERSION),
    }


def _save(figure: Figure, options: RenderOptions, spec: FigureSpec) -> bytes:
    buffer = BytesIO()
    metadata = _metadata(spec)
    if options.fmt == "svg":
        # The SVG writer only understands the Dublin Core keys; the rest would raise.
        figure.savefig(
            buffer,
            format="svg",
            metadata={
                "Date": None,
                "Title": spec.title,
                "Description": spec.plain_language_answer,
                "Creator": "alpha_research.figures",
            },
            transparent=options.background == "transparent",
        )
    else:
        figure.savefig(
            buffer,
            format="png",
            dpi=options.size.dpi,
            metadata=metadata,
            transparent=options.background == "transparent",
        )
    figure.clear()
    payload = buffer.getvalue()
    _assert_no_timestamp(payload, options.fmt)
    return payload


def _assert_no_timestamp(payload: bytes, fmt: FigureFormat) -> None:
    """Fail loud rather than publish a figure that can never match its own cache key."""
    if fmt == "svg" and b"dc:date" in payload:
        raise DataError("rendered SVG carries a creation date; byte stability is broken")
    if fmt == "png" and b"Matplotlib" in payload:
        raise DataError("rendered PNG carries a software stamp; byte stability is broken")
