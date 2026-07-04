"""Server-side inline SVG charts — so run-detail needs no JavaScript charting library.

Pure string builders: an equity series in, an ``<svg>`` out. Kept tiny and dependency-free; the
templates drop the returned markup straight into the page.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

_WIDTH = 720
_HEIGHT = 240
_PAD = 8


def fan_chart_svg(
    history: Sequence[float],
    bands: Mapping[str, Sequence[float]],
    *,
    width: int = _WIDTH,
    height: int = _HEIGHT,
) -> str:
    """A forecast outcome cone: history polyline + shaded quantile bands + dashed median.

    ``bands`` maps ``q05/q25/q50/q75/q95`` to per-step close values. The cone emanates from
    the last history point (the forecast origin). Fails loud (``ValueError``) on ragged band
    lengths — a malformed artifact should break the page, not draw a wrong chart.
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
    span = hi - lo
    inner_w = width - 2 * _PAD
    inner_h = height - 2 * _PAD
    n_total = len(history) + steps

    def _xy(index: int, value: float) -> str:
        x = _PAD + inner_w * index / (n_total - 1)
        frac = 0.5 if span == 0 else (value - lo) / span
        y = _PAD + inner_h * (1.0 - frac)
        return f"{x:.2f},{y:.2f}"

    origin_index = len(history) - 1
    origin = history[-1]

    def _band_polygon(upper: Sequence[float], lower: Sequence[float], opacity: float) -> str:
        top = [_xy(origin_index, origin)]
        top += [_xy(origin_index + 1 + i, v) for i, v in enumerate(upper)]
        bottom = [_xy(origin_index + 1 + i, v) for i, v in enumerate(lower)][::-1]
        pts = " ".join(top + bottom)
        return (
            f'<polygon fill="currentColor" fill-opacity="{opacity}" stroke="none" points="{pts}" />'
        )

    history_pts = " ".join(_xy(i, v) for i, v in enumerate(history))
    median_pts = " ".join(
        [_xy(origin_index, origin)]
        + [_xy(origin_index + 1 + i, v) for i, v in enumerate(bands["q50"])]
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" class="fan-chart" '
        f'preserveAspectRatio="none" role="img" aria-label="forecast cone">'
        + _band_polygon(bands["q95"], bands["q05"], 0.12)
        + _band_polygon(bands["q75"], bands["q25"], 0.25)
        + f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" '
        f'points="{history_pts}" />'
        + f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" '
        f'stroke-dasharray="5 4" points="{median_pts}" />' + "</svg>"
    )


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
