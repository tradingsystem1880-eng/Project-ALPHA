"""The observed-value note on a null histogram: short, and kept inside the plot."""

from __future__ import annotations

from alpha_research.figures import ValueLabel


def observed_label(observed: float, percentile: object, low: float, high: float) -> ValueLabel:
    """Say the observed value and its percentile once.

    A rule in the right half of the range gets a right-aligned label, so the text runs back
    over the plot instead of off its edge; the short text keeps it from covering the bars.
    """
    text = f"observed {observed:.3f}"
    if isinstance(percentile, int | float) and not isinstance(percentile, bool):
        text += f" · pct {float(percentile) * 100:.0f}"
    if observed > (low + high) / 2:
        return ValueLabel(text=text, ha="right", dx_pt=-6.0)
    return ValueLabel(text=text)
