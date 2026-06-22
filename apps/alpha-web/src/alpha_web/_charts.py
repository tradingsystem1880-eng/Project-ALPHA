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
