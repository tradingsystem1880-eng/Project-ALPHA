"""Server-side inline SVG charts — so run-detail needs no JavaScript charting library.

Pure string builders: an equity series in, an ``<svg>`` out. Kept tiny and dependency-free; the
templates drop the returned markup straight into the page.
"""

from __future__ import annotations

from collections.abc import Sequence

_WIDTH = 720
_HEIGHT = 240
_PAD = 8


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


def forecast_svg(
    history: Sequence[float],
    forecast: Sequence[float],
    *,
    p10: Sequence[float] | None = None,
    p90: Sequence[float] | None = None,
    width: int = _WIDTH,
    height: int = _HEIGHT,
) -> str:
    """History (solid) + forecast continuation (dashed) on one shared y-scale.

    The optional p10/p90 close band renders as a translucent polygon under the forecast
    line; a 1px vertical divider marks the history/forecast boundary. Placeholder ``<svg>``
    when there is nothing to draw.
    """
    total = len(history) + len(forecast)
    if len(history) < 1 or len(forecast) < 1 or total < 2:
        return (
            f'<svg viewBox="0 0 {width} {height}" class="equity-chart" '
            f'preserveAspectRatio="none" role="img" aria-label="no forecast"></svg>'
        )
    all_values = [*history, *forecast, *(p10 or []), *(p90 or [])]
    lo, hi = min(all_values), max(all_values)
    span = hi - lo
    inner_w = width - 2 * _PAD
    inner_h = height - 2 * _PAD

    def _xy(i: int, v: float) -> tuple[float, float]:
        x = _PAD + inner_w * i / (total - 1)
        frac = 0.5 if span == 0 else (v - lo) / span
        return x, _PAD + inner_h * (1.0 - frac)

    def _pts(pairs: list[tuple[float, float]]) -> str:
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in pairs)

    history_pts = [_xy(i, v) for i, v in enumerate(history)]
    # the forecast polyline starts AT the last history point so the line is continuous
    offset = len(history) - 1
    forecast_pts = [history_pts[-1]] + [_xy(offset + 1 + i, v) for i, v in enumerate(forecast)]
    divider_x = history_pts[-1][0]

    band = ""
    if p10 is not None and p90 is not None and len(p10) == len(forecast) == len(p90):
        upper = [_xy(offset + 1 + i, v) for i, v in enumerate(p90)]
        lower = [_xy(offset + 1 + i, v) for i, v in enumerate(p10)]
        band = (
            f'<polygon fill="currentColor" fill-opacity="0.12" stroke="none" '
            f'points="{_pts(upper + list(reversed(lower)))}" />'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" class="equity-chart" '
        f'preserveAspectRatio="none" role="img" aria-label="history and forecast">'
        f"{band}"
        f'<line x1="{divider_x:.2f}" y1="{_PAD}" x2="{divider_x:.2f}" y2="{height - _PAD}" '
        f'stroke="currentColor" stroke-opacity="0.35" stroke-width="1" />'
        f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" '
        f'points="{_pts(history_pts)}" />'
        f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" '
        f'stroke-dasharray="4 3" points="{_pts(forecast_pts)}" /></svg>'
    )
