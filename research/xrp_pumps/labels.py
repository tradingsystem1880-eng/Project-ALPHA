"""Forward-looking pump labels, and the ``valid`` mask that keeps them honest.

A label answers: *starting from this bar, did price rise by X within Y days?* Two properties of that
question decide whether the resulting statistics mean anything.

**The mask.** For the last Y days of the series the answer is not yet known. Scoring those bars as
"no pump" biases every rate downward by a predictable amount, and worse, biases it *unevenly* across
conditions — any predictor that fires more often near the end of the record gets penalised. So each
label ships with a boolean ``valid`` array marking the bars whose outcome is genuinely determined.

**The overlap.** Consecutive daily bars share 29 of the 30 days in their forward windows. They are
not thirty observations; they are close to one. :func:`overlap_for` computes the deflation factor
that :func:`~alpha_validation.conditional.conditional_lift` applies before any interval is formed.
Skipping this step is the single most effective way to manufacture a significant result from noise.

A label is also computed for a **-20% mirror**. A condition that raises the odds of a large upward
move while raising the odds of a large downward move equally has detected volatility, not direction.
That is the most common way a breakout study fools its author, and it costs one extra column to
check.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_validation import effective_sample_size, overlap_factor
from research.xrp_pumps import config as C


@dataclass(frozen=True)
class Label:
    """One realised pump definition over one series."""

    name: str
    horizon_bars: int
    hit: np.ndarray  # bool: the definition was met
    valid: np.ndarray  # bool: the forward window is complete, so ``hit`` is meaningful
    forward_return: np.ndarray  # the raw max-to-horizon return, for descriptive plots
    threshold: float  # the realised threshold (resolved, for a relative definition)

    @property
    def base_rate(self) -> float:
        n = int(np.count_nonzero(self.valid))
        if n == 0:
            raise DataError(f"label {self.name!r} has no valid bars")
        return float(np.count_nonzero(self.hit & self.valid)) / n


def forward_max_return(closes: np.ndarray, horizon: int) -> np.ndarray:
    """Best return achievable within the next ``horizon`` bars, from each bar's close.

    Maximum rather than end-of-window return, because "did XRP pump" is a question about whether the
    move happened at all, not about whether it was still intact on a particular later day. Using the
    endpoint would score a +60% spike that gave half of it back as a non-event, which is not how
    anyone holding the position would describe it.
    """
    if horizon < 1:
        raise DataError(f"horizon must be >= 1, got {horizon}")
    n = closes.size
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        end = min(i + horizon + 1, n)
        if end <= i + 1:
            continue
        out[i] = float(np.max(closes[i + 1 : end])) / closes[i] - 1.0
    return out


def forward_min_return(closes: np.ndarray, horizon: int) -> np.ndarray:
    """Worst return within the next ``horizon`` bars — the mirror used for the symmetry check."""
    if horizon < 1:
        raise DataError(f"horizon must be >= 1, got {horizon}")
    n = closes.size
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        end = min(i + horizon + 1, n)
        if end <= i + 1:
            continue
        out[i] = float(np.min(closes[i + 1 : end])) / closes[i] - 1.0
    return out


def make_label(
    closes: np.ndarray, pump: C.PumpDefinition, timeframe: str, *, downside: bool = False
) -> Label:
    """Realise one pump definition against a close series.

    A *relative* definition (``relative_quantile`` set) resolves its threshold from the sample's own
    forward-return distribution rather than a fixed percentage. That is the label that survives a
    change of regime: "a top-decile 30-day move" means something in 2018 and in 2026, where "+20%"
    describes a routine week in one and an exceptional quarter in the other.

    The threshold for a relative label is computed **over the whole sample**, which is a deliberate
    and stated compromise: it makes the label sample-dependent (mildly in-sample) but keeps the base
    rate fixed at exactly the quantile, which is what makes lift comparable across assets. The
    absolute definitions carry no such caveat and are the ones the confirmatory test uses.
    """
    horizon = C.bars(pump.horizon_days, timeframe)
    fwd = forward_min_return(closes, horizon) if downside else forward_max_return(closes, horizon)
    valid = np.isfinite(fwd)
    # The last `horizon` bars have a truncated window even where `fwd` is finite: the maximum over
    # 3 remaining days is not a 30-day maximum. Mask them explicitly.
    valid[max(0, closes.size - horizon) :] = False

    if pump.is_relative:
        pool = fwd[valid]
        if pool.size < 50:
            raise DataError(f"{pump.label}: only {pool.size} resolved bars — cannot set a quantile")
        threshold = float(np.quantile(pool, 1.0 - pump.relative_quantile))
    else:
        threshold = float(pump.threshold)

    hit = np.zeros(closes.size, dtype=bool)
    if downside:
        hit[valid] = fwd[valid] <= threshold
    else:
        hit[valid] = fwd[valid] >= threshold

    return Label(
        name=("down" if downside else "") + pump.label,
        horizon_bars=horizon,
        hit=hit,
        valid=valid,
        forward_return=fwd,
        threshold=threshold,
    )


def overlap_for(label: Label) -> float:
    """Deflation factor for a label's forward-window overlap.

    Every bar is an event here — the study conditions on bar state, not on discrete pattern
    occurrences — so the number of independent observations the series can hold is simply its span
    divided by the horizon. Reuses the same primitive the head-and-shoulders study used, so the two
    studies' sample sizes are directly comparable.
    """
    n = int(np.count_nonzero(label.valid))
    if n == 0:
        raise DataError(f"label {label.name!r} has no valid bars")
    return overlap_factor(n, span_bars=n, horizon_bars=label.horizon_bars)


def effective_n(label: Label) -> float:
    """Independent-observation count behind a label — the number every interval is built on."""
    n = int(np.count_nonzero(label.valid))
    return effective_sample_size(n, span_bars=n, horizon_bars=label.horizon_bars)


def all_labels(
    closes: np.ndarray, timeframe: str, *, include_power: bool = True
) -> dict[str, Label]:
    """Every pump definition plus the downside mirror, keyed by label name.

    ``include_power`` adds the two shorter horizons declared post-hoc in
    :data:`~research.xrp_pumps.config.POWER_PUMPS`. They are kept in the same dict rather than a
    parallel structure so nothing downstream can accidentally treat them as pre-registered — the
    report separates them by name, and :data:`PRE_REGISTERED` below is the authoritative list.
    """
    out: dict[str, Label] = {}
    pumps = (*C.PUMPS, *C.POWER_PUMPS) if include_power else C.PUMPS
    for pump in pumps:
        try:
            lab = make_label(closes, pump, timeframe)
        except DataError as exc:
            print(f"    label {pump.label}: {exc}")
            continue
        out[lab.name] = lab
    mirror = make_label(closes, C.DRAWDOWN_MIRROR, timeframe, downside=True)
    out[mirror.name] = mirror
    return out


#: The label names a confirmatory claim may rest on. Anything else is descriptive or post-hoc.
PRE_REGISTERED: tuple[str, ...] = tuple(p.label for p in C.PUMPS)
POST_HOC: tuple[str, ...] = tuple(p.label for p in C.POWER_PUMPS)
