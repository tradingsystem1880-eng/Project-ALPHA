"""Server-side inline SVG charts — so run-detail needs no JavaScript charting library.

Pure string builders: series in, an ``<svg>`` out. Kept tiny and dependency-free; the
templates drop the returned markup straight into the page (dark theme, see app.css).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

_WIDTH = 720
_HEIGHT = 240
_PAD = 8

# fan-chart palette (the web IDE is dark-only; see static/app.css)
_GRID = "#262b35"
_GRID_TEXT = "#8b93a3"
_HISTORY = "#5b9dff"
_MEDIAN = "#5eead4"
_BAND = "#5eead4"
_ORIGIN = "#c9a227"

_FAN_HEIGHT = 380
_FAN_PAD_LEFT = 10
_FAN_PAD_RIGHT = 64  # room for the right-edge price labels
_FAN_PAD_TOP = 20
_FAN_PAD_BOTTOM = 16
_FAN_GRIDLINES = 5


def _price_label(value: float) -> str:
    return f"{value:,.0f}" if value >= 1_000 else f"{value:,.2f}"


def fan_chart_svg(
    history: Sequence[float],
    bands: Mapping[str, Sequence[float]],
    *,
    width: int = _WIDTH,
    height: int = _FAN_HEIGHT,
) -> str:
    """A forecast outcome cone: history line, shaded quantile bands, dashed median,
    price gridlines with right-edge labels, and a marked forecast origin.

    ``bands`` maps ``q05/q25/q50/q75/q95`` to per-step close values; the cone emanates
    from the last history point. Fails loud (``ValueError``) on ragged band lengths — a
    malformed artifact should break the page, not draw a wrong chart.
    """
    steps = len(bands.get("q50", ()))
    for name in ("q05", "q25", "q50", "q75", "q95"):
        if len(bands.get(name, ())) != steps:
            raise ValueError(f"band {name!r} length {len(bands.get(name, ()))} != {steps}")
    if not history or steps == 0:
        return (
            f'<svg viewBox="0 0 {width} {height}" class="fan-chart" '
            f'preserveAspectRatio="none" role="img" aria-label="no forecast cone"></svg>'
        )

    lo = min(min(history), min(bands["q05"]))
    hi = max(max(history), max(bands["q95"]))
    headroom = (hi - lo) * 0.04 or abs(hi) * 0.01 or 1.0
    lo, hi = lo - headroom, hi + headroom
    span = hi - lo
    inner_w = width - _FAN_PAD_LEFT - _FAN_PAD_RIGHT
    inner_h = height - _FAN_PAD_TOP - _FAN_PAD_BOTTOM
    n_total = len(history) + steps

    def _x(index: int) -> float:
        return _FAN_PAD_LEFT + inner_w * index / (n_total - 1)

    def _y(value: float) -> float:
        return _FAN_PAD_TOP + inner_h * (1.0 - (value - lo) / span)

    def _xy(index: int, value: float) -> str:
        return f"{_x(index):.2f},{_y(value):.2f}"

    origin_index = len(history) - 1
    origin = history[-1]
    origin_x = _x(origin_index)
    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" class="fan-chart" role="img" '
        f'aria-label="forecast cone">'
    ]

    # price gridlines + right-edge labels
    for i in range(_FAN_GRIDLINES):
        value = lo + span * i / (_FAN_GRIDLINES - 1)
        gy = _y(value)
        parts.append(
            f'<line x1="{_FAN_PAD_LEFT}" y1="{gy:.2f}" x2="{_FAN_PAD_LEFT + inner_w}" '
            f'y2="{gy:.2f}" stroke="{_GRID}" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{width - 4}" y="{gy + 4:.2f}" text-anchor="end" '
            f'fill="{_GRID_TEXT}" font-size="11">{_price_label(value)}</text>'
        )

    # forecast-origin marker
    parts.append(
        f'<line x1="{origin_x:.2f}" y1="{_FAN_PAD_TOP}" x2="{origin_x:.2f}" '
        f'y2="{_FAN_PAD_TOP + inner_h}" stroke="{_ORIGIN}" stroke-width="1" '
        f'stroke-dasharray="3 4" opacity="0.8" />'
    )
    parts.append(
        f'<text x="{origin_x + 5:.2f}" y="{_FAN_PAD_TOP + 11}" fill="{_ORIGIN}" '
        f'font-size="11">forecast start</text>'
    )

    def _band_polygon(upper: Sequence[float], lower: Sequence[float], opacity: float) -> str:
        top = [_xy(origin_index, origin)]
        top += [_xy(origin_index + 1 + i, v) for i, v in enumerate(upper)]
        bottom = [_xy(origin_index + 1 + i, v) for i, v in enumerate(lower)][::-1]
        return (
            f'<polygon fill="{_BAND}" fill-opacity="{opacity}" stroke="none" '
            f'points="{" ".join(top + bottom)}" />'
        )

    parts.append(_band_polygon(bands["q95"], bands["q05"], 0.14))
    parts.append(_band_polygon(bands["q75"], bands["q25"], 0.28))

    history_pts = " ".join(_xy(i, v) for i, v in enumerate(history))
    parts.append(
        f'<polyline fill="none" stroke="{_HISTORY}" stroke-width="1.6" points="{history_pts}" />'
    )
    median_pts = " ".join(
        [_xy(origin_index, origin)]
        + [_xy(origin_index + 1 + i, v) for i, v in enumerate(bands["q50"])]
    )
    parts.append(
        f'<polyline fill="none" stroke="{_MEDIAN}" stroke-width="1.8" '
        f'stroke-dasharray="5 4" points="{median_pts}" />'
    )
    parts.append("</svg>")
    return "".join(parts)


def equity_svg(values: Sequence[float], *, width: int = _WIDTH, height: int = _HEIGHT) -> str:
    """An equity curve as a single-polyline SVG scaled to ``width`` x ``height``.

    Returns an axis-free sparkline (a placeholder ``<svg>`` with no polyline when there is nothing
    to draw). The y-axis spans the series min..max; a flat series sits on the mid-line.
    """
    if len(values) < 2:
        return (
            f'<svg viewBox="0 0 {width} {height}" class="equity-chart" '
            f'preserveAspectRatio="none" role="img" aria-label="no equity curve"></svg>'
        )
    lo, hi = min(values), max(values)
    span = hi - lo
    inner_w = width - 2 * _PAD
    inner_h = height - 2 * _PAD
    n = len(values)
    points = []
    for i, v in enumerate(values):
        x = _PAD + inner_w * i / (n - 1)
        # invert y (SVG origin top-left); a flat series (span 0) pins to the mid-line
        frac = 0.5 if span == 0 else (v - lo) / span
        y = _PAD + inner_h * (1.0 - frac)
        points.append(f"{x:.2f},{y:.2f}")
    return (
        f'<svg viewBox="0 0 {width} {height}" class="equity-chart" '
        f'preserveAspectRatio="none" role="img" aria-label="equity curve">'
        f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" '
        f'points="{" ".join(points)}" /></svg>'
    )
