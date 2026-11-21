"""Figure builders: returns."""

from __future__ import annotations

import math

import numpy as np

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _truncation, pct
from alpha_core import DataError
from alpha_research.figures import (
    FigureSpec,
    HistogramMark,
    LineMark,
    Panel,
    RuleMark,
    ScatterMark,
    ValueLabel,
)


# --------------------------------------------------------------------------- risk
def _bin_edges(values: np.ndarray, low: float, high: float) -> tuple[float, ...]:
    """Equal bins over [low, high] by the Freedman-Diaconis rule, clamped to 15..60 bins."""
    q75, q25 = np.percentile(values, [75, 25])
    width = 2.0 * (q75 - q25) / (len(values) ** (1.0 / 3.0)) if len(values) > 1 else 0.0
    count = int(math.ceil((high - low) / width)) if width > 0 else 30
    count = max(15, min(60, count))
    return tuple(float(edge) for edge in np.linspace(low, high, count + 1))


def return_distribution(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "return_distribution.parquet")
    hist = frame.filter(frame["kind"] == "histogram").sort("index")
    if hist.is_empty():
        raise DataError("no stored return histogram for this run")
    qq = frame.filter(frame["kind"] == "qq")
    left = src.floats(hist["left"], name="left")
    right = src.floats(hist["right"], name="right")
    counts: tuple[float, ...] = src.floats(hist["count"], name="count")
    edges = (*left, right[-1])
    total = sum(counts)
    if qq.is_empty():
        centres = [(a + b) / 2 for a, b in zip(left, right, strict=True)]
        mean = sum(c * n for c, n in zip(centres, counts, strict=True)) / total
        sigma = math.sqrt(
            sum(n * (c - mean) ** 2 for c, n in zip(centres, counts, strict=True)) / total
        )
        note = "approximate: the stored histogram holds no single returns"
    else:
        # The Q-Q points are every stored daily return, sorted. The mean read from bin
        # centres was only an estimate and could flip sign; the stored returns cannot.
        sample = np.asarray(src.floats(qq["sample"], name="sample"), dtype=float)
        mean, sigma = float(sample.mean()), float(sample.std())
        total = float(sample.size)
        # Range from the 0.5% and 99.5% quantiles; the rare outliers stay in the Q-Q figure.
        low, high = (float(v) for v in np.percentile(sample, [0.5, 99.5]))
        if high <= low:
            low, high = float(sample.min()), float(sample.max())
        if high <= low:
            high = low + 1e-9
        edges = _bin_edges(sample, low, high)
        inside = sample[(sample >= low) & (sample <= high)]
        counts = tuple(float(v) for v in np.histogram(inside, bins=np.asarray(edges))[0])
        note = ""
    sigma = sigma or 1e-12
    width = edges[1] - edges[0]
    curve_x = tuple(edges[0] + (edges[-1] - edges[0]) * i / 200 for i in range(201))
    scale = total * width / (sigma * math.sqrt(2 * math.pi))
    curve_y = tuple(scale * math.exp(-0.5 * ((x - mean) / sigma) ** 2) for x in curve_x)
    answer = (
        f"Daily returns averaged {pct(mean, 2)} with a {pct(sigma, 2)} standard deviation "
        f"across {int(total):,} sessions."
    )
    return ctx.spec(
        "return_distribution",
        x_label="Daily return (ratio)",
        x_kind="numeric",
        artifacts=("return_distribution.parquet",),
        answer=answer + (f" ({note})" if note else ""),
        truncation=(
            "x range covers the 0.5% to 99.5% quantiles of daily returns" if note == "" else None
        ),
        panels=(
            Panel(
                panel_id="histogram",
                y_label="Sessions (count)",
                y_unit="count",
                marks=(
                    HistogramMark(
                        edges=edges, counts=counts, role="subject", alpha=0.8, label="Observed"
                    ),
                    LineMark(
                        x=curve_x,
                        y=curve_y,
                        role="reference",
                        dashed=True,
                        label="Normal reference",
                    ),
                    RuleMark(
                        orientation="vertical",
                        position=mean,
                        role="feature",
                        width=1.2,
                        annotate=ValueLabel(text=f"mean {pct(mean, 2)}"),
                    ),
                ),
            ),
        ),
    )


def qq_normal(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "return_distribution.parquet")
    qq = frame.filter(frame["kind"] == "qq").sort("index")
    if qq.is_empty():
        raise DataError("no stored Q-Q points for this run")
    picked = src.sample(qq.height, 2000)
    view = qq[picked]
    theoretical = src.floats(view["theoretical"], name="theoretical")
    observed = src.floats(view["sample"], name="sample")
    slope = (
        sum(t * s for t, s in zip(theoretical, observed, strict=True))
        / sum(t * t for t in theoretical)
        if any(theoretical)
        else 1.0
    )
    reference = tuple(slope * value for value in theoretical)
    tail = max(abs(observed[0] - reference[0]), abs(observed[-1] - reference[-1]))
    return ctx.spec(
        "qq_normal",
        x_label="Normal quantile (z_score)",
        x_kind="numeric",
        artifacts=("return_distribution.parquet",),
        truncation=_truncation(qq.height, len(picked), "points"),
        answer=(
            f"The extreme tails depart from the normal reference by up to {pct(tail, 2)} of "
            "daily return, which is the usual signature of fat tails."
        ),
        panels=(
            Panel(
                panel_id="qq",
                y_label="Observed return (ratio)",
                y_unit="ratio",
                marks=(
                    LineMark(
                        x=theoretical,
                        y=reference,
                        role="reference",
                        dashed=True,
                        label="Normal reference",
                    ),
                    ScatterMark(
                        x=theoretical,
                        y=observed,
                        role="subject",
                        size=8.0,
                        label="Observed quantile",
                    ),
                ),
            ),
        ),
    )
