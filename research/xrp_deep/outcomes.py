"""Forward outcomes: what "it worked" means, defined before any condition was tested.

Five outcome families, and the choice between them matters more than any individual condition:

* ``up_H`` — reached +10% at any point inside H bars. The optimistic reading: it counts a spike
  that closed straight back as a win, which is honest only for a trader watching every bar.
* ``down_H`` — reached −10%. Reported with equal prominence, because a study of a live long that
  measures only the upside is not a study, it is a comfort blanket.
* ``fwd_positive_H`` — the close after H bars is higher. The plainest possible question.
* ``barrier_H`` — the triple barrier: +10% before −7%, resolved pessimistically on a same-bar
  collision. **This is the only outcome that corresponds to an actual trade**, and where the other
  four disagree with it, believe this one.
* ``beat_btc_H`` — outperformed BTC over H bars. The relevant question for an altcoin long, since
  being up 8% while BTC is up 15% is a losing trade expressed in the wrong denominator.

Every outcome is undefined for the last H bars of the series, and that is carried as an explicit
validity mask rather than as a False. Treating "not enough future data" as "did not happen" would
systematically mark the most recent — and most relevant — bars as failures.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from research.xrp_deep import config as C
from research.xrp_deep.panel import Panel


@dataclass(frozen=True)
class Outcome:
    """One forward-looking label plus the mask of bars where it is defined."""

    key: str
    hit: np.ndarray  # bool
    valid: np.ndarray  # bool — False where the horizon runs off the end of the data
    horizon: int
    description: str

    @property
    def base_rate(self) -> float:
        n = int(self.valid.sum())
        return float(self.hit[self.valid].sum()) / n if n else float("nan")


def _forward_extremes(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, horizon: int
) -> tuple[np.ndarray, np.ndarray]:
    """Max high and min low over bars ``i+1 .. i+horizon``, as fractions of ``close[i]``."""
    n = close.size
    up = np.full(n, np.nan)
    down = np.full(n, np.nan)
    for i in range(n):
        end = min(i + horizon + 1, n)
        if end <= i + 1:
            continue
        base = close[i]
        if not np.isfinite(base) or base <= 0:
            continue
        up[i] = float(np.max(high[i + 1 : end])) / base - 1.0
        down[i] = float(np.min(low[i + 1 : end])) / base - 1.0
    return up, down


def _barrier(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, horizon: int
) -> tuple[np.ndarray, np.ndarray]:
    """Triple-barrier label: True where the up barrier is touched before the down barrier.

    A bar touching both resolves to the **stop**. Intraday order is unknowable from a daily bar, and
    the adverse assumption is the one that cannot flatter the result. Unresolved inside the horizon
    counts as not-won, which matches how a trader with a time stop would book it.
    """
    n = close.size
    hit = np.zeros(n, dtype=bool)
    valid = np.zeros(n, dtype=bool)
    for i in range(n):
        end = min(i + horizon + 1, n)
        if end <= i + 1 or not np.isfinite(close[i]) or close[i] <= 0:
            continue
        valid[i] = i + horizon < n
        up_level = close[i] * (1.0 + C.BARRIER_UP)
        down_level = close[i] * (1.0 - C.BARRIER_DOWN)
        for k in range(i + 1, end):
            touched_down = low[k] <= down_level
            touched_up = high[k] >= up_level
            if touched_down and C.BARRIER_PESSIMISTIC:
                break
            if touched_up:
                hit[i] = True
                break
            if touched_down:
                break
    return hit, valid


def build_outcomes(panel: Panel) -> dict[str, Outcome]:
    """Every outcome at every horizon in :data:`config.HORIZONS`."""
    high, low, close = panel.bars.high, panel.bars.low, panel.bars.close
    n = close.size
    out: dict[str, Outcome] = {}

    for h in C.HORIZONS:
        valid = np.zeros(n, dtype=bool)
        valid[: max(0, n - h)] = True
        up, down = _forward_extremes(high, low, close, h)

        out[f"up_{h}"] = Outcome(
            f"up_{h}",
            np.nan_to_num(up, nan=-9.0) >= C.UP_THRESHOLD,
            valid & np.isfinite(up),
            h,
            f"reached +{C.UP_THRESHOLD:.0%} within {h} days",
        )
        out[f"down_{h}"] = Outcome(
            f"down_{h}",
            np.nan_to_num(down, nan=9.0) <= -C.DOWN_THRESHOLD,
            valid & np.isfinite(down),
            h,
            f"reached -{C.DOWN_THRESHOLD:.0%} within {h} days",
        )

        fwd = np.full(n, np.nan)
        fwd[: n - h] = close[h:] / close[: n - h] - 1.0
        out[f"fwd_positive_{h}"] = Outcome(
            f"fwd_positive_{h}",
            np.nan_to_num(fwd, nan=-9.0) > 0.0,
            valid & np.isfinite(fwd),
            h,
            f"close is higher {h} days later",
        )

        hit, bvalid = _barrier(high, low, close, h)
        out[f"barrier_{h}"] = Outcome(
            f"barrier_{h}",
            hit,
            bvalid,
            h,
            f"+{C.BARRIER_UP:.0%} before -{C.BARRIER_DOWN:.0%} within {h} days",
        )

        btc = panel.features.get("btc_close")
        if btc is not None:
            btc_fwd = np.full(n, np.nan)
            btc_fwd[: n - h] = btc[h:] / btc[: n - h] - 1.0
            beat = np.isfinite(fwd) & np.isfinite(btc_fwd) & (fwd > btc_fwd)
            out[f"beat_btc_{h}"] = Outcome(
                f"beat_btc_{h}",
                beat,
                valid & np.isfinite(fwd) & np.isfinite(btc_fwd),
                h,
                f"outperformed BTC over {h} days",
            )
    return out


def primary_outcomes(outcomes: dict[str, Outcome]) -> dict[str, Outcome]:
    """The pre-registered headline set: one per outcome family at the primary horizon."""
    h = C.PRIMARY_HORIZON
    keys = [f"up_{h}", f"down_{h}", f"fwd_positive_{h}", f"barrier_{h}", f"beat_btc_{h}"]
    missing = [k for k in keys if k not in outcomes]
    if missing:
        raise DataError(f"primary outcomes missing: {missing}")
    return {k: outcomes[k] for k in keys}
