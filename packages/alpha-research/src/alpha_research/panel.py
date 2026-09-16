"""Cross-sectional panel primitives for the screening lane (edge-first Phase C, 2026-09-11).

Every input is a ``T×N`` float panel (dates × names). ``NaN`` means "name absent on that date";
``inf`` fails loud. A date with fewer than ``min_names`` finite pairs yields ``None`` (undefined,
never fabricated). Ranks are average ranks over a stable sort in the caller's canonical column
order: tied observations receive average ranks; bucket membership is order-deterministic.
Nothing here is randomised.

Sources and local design conventions are identified in the function docstrings. Descriptive
ICIR is not a portfolio information ratio or an estimate of independent breadth. Fama &
MacBeth (1973) supplies the cross-sectional regression framework. Quantile monotonicity is a plain
rank correlation of bucket index against bucket mean, not the Patton–Timmermann MR test.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_research._arrays import average_ranks, pearson_or_none

PANEL_VERSION = 1


@dataclass(frozen=True)
class IcSeries:
    """Per-date Spearman IC and its summary; ``None`` statistics are undefined, not zero."""

    values: list[float | None]
    mean: float | None
    std: float | None
    icir: float | None
    t_stat: float | None
    hit_rate: float | None
    n_dates: int


@dataclass(frozen=True)
class QuantileReport:
    mean_by_quantile: list[float]
    spread: float
    monotonicity: float | None
    n_dates: int


@dataclass(frozen=True)
class FamaMacBeth:
    mean_slopes: list[float]
    t_stats: list[float | None]
    n_dates: int


def _panel(values: object) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise DataError("panel inputs must be numeric rectangular arrays") from exc
    if array.ndim != 2:
        raise DataError("panel inputs must be two-dimensional dates × names arrays")
    if np.isinf(array).any():
        raise DataError("panel inputs must contain only finite or NaN values")
    return array


def _panels(first: object, *others: object) -> list[np.ndarray]:
    """Coerce panels that must share one shape and hold at least three dates."""
    arrays = [_panel(first), *(_panel(o) for o in others)]
    if any(a.shape != arrays[0].shape for a in arrays):
        raise DataError("panel inputs must share one shape")
    if arrays[0].shape[0] < 3:
        raise DataError("panel statistics require at least three dates")
    return arrays


def _min_names(min_names: int) -> int:
    if type(min_names) is not int or min_names < 3:
        raise DataError(f"min_names must be an integer >= 3; got {min_names!r}")
    return min_names


def _sample_std(values: np.ndarray) -> float | None:
    return None if values.size < 2 else float(np.std(values, ddof=1))


def cross_sectional_ic(signal: object, outcome: object, *, min_names: int = 5) -> IcSeries:
    """Per-date Spearman IC; sample-std ICIR and plain t = ICIR·√n over scored dates.

    Rank association: Spearman (1904), DOI 10.2307/1412159; average-rank ties agree
    with scipy.stats.spearmanr. The mean/sample-std and sqrt(n) relation follows
    Sharpe (1994), "The Sharpe Ratio", Ex Post section:
    https://web.stanford.edu/~wfsharpe/art/sr/SR.htm. These are descriptive IC
    summaries, not portfolio Sharpe ratios; serial dependence is not corrected.
    """
    signals, outcomes = _panels(signal, outcome)
    min_names = _min_names(min_names)
    values: list[float | None] = []
    for t in range(signals.shape[0]):
        mask = np.isfinite(signals[t]) & np.isfinite(outcomes[t])
        if int(mask.sum()) < min_names:
            values.append(None)
            continue
        values.append(
            pearson_or_none(average_ranks(signals[t][mask]), average_ranks(outcomes[t][mask]))
        )
    scored = np.asarray([v for v in values if v is not None], dtype=float)
    if scored.size == 0:
        return IcSeries(values, None, None, None, None, None, 0)
    mean = float(np.mean(scored))
    std = _sample_std(scored)
    icir = None if std is None or std == 0.0 else mean / std
    t_stat = None if icir is None else icir * math.sqrt(scored.size)
    return IcSeries(values, mean, std, icir, t_stat, float(np.mean(scored > 0.0)), int(scored.size))


def forward_outcomes(closes: object, *, horizon: int) -> np.ndarray:
    """``closes[t+h]/closes[t] − 1`` where both closes exist and are finite; NaN otherwise.

    Arithmetic outcome construction, not an inferential estimator. Primary local
    DESIGN: docs/superpowers/plans/2026-09-11-edge-first-phase-c-screening-lane.md,
    C1 forward_outcomes (including endpoint admission).

    Row ``t`` is defined only when ``t + h <= T − 1``: a horizon that runs off the panel is NaN,
    never a shorter return.
    """
    panel = _panel(closes)
    if not (panel[np.isfinite(panel)] > 0.0).all():
        raise DataError("close panel must be strictly positive where present")
    n_dates = panel.shape[0]
    if type(horizon) is not int or not 1 <= horizon < n_dates:
        raise DataError(
            f"forward horizon must be an integer in [1, {n_dates - 1}]; got {horizon!r}"
        )
    out = np.full(panel.shape, np.nan)
    out[: n_dates - horizon] = panel[horizon:] / panel[:-horizon] - 1.0
    return out


def _validate_horizons(horizons: Sequence[int], n_dates: int) -> tuple[int, ...]:
    if not horizons or any(type(h) is not int for h in horizons):
        raise DataError("horizons must be a non-empty sequence of integers")
    if list(horizons) != sorted(set(horizons)) or horizons[0] < 1 or horizons[-1] >= n_dates:
        raise DataError(f"horizons must be strictly increasing integers in [1, {n_dates - 1}]")
    return tuple(int(h) for h in horizons)


def ic_decay(
    signal: object,
    closes: object,
    *,
    horizons: Sequence[int] = (1, 5, 10, 21),
    min_names: int = 5,
) -> dict[int, IcSeries]:
    """Cross-sectional IC series against forward returns at each horizon.

    Each horizon uses Spearman (1904), DOI 10.2307/1412159, as in cross_sectional_ic.
    Horizon and endpoint policies are the local Phase-C C1 DESIGN contract in
    docs/superpowers/plans/2026-09-11-edge-first-phase-c-screening-lane.md.
    No fitted decay model is assumed.
    """
    signals, close_panel = _panels(signal, closes)
    valid = _validate_horizons(horizons, close_panel.shape[0])
    return {
        h: cross_sectional_ic(
            signals, forward_outcomes(close_panel, horizon=h), min_names=min_names
        )
        for h in valid
    }


def ic_half_life(decay: Mapping[int, float | None]) -> float | None:
    """Horizon at which the mean IC first falls to half its shortest-horizon value.

    ``decay`` maps horizon to mean IC (``{h: series.mean for h, series in ic_decay(...).items()}``).

    Linear interpolation between the last horizon above half and the first at or below it;
    ``None`` when the base IC is undefined or non-positive, when a horizon is undefined, or when
    the IC never halves inside the measured horizons.

    Local DESIGN summary of Spearman (1904) rank IC (DOI 10.2307/1412159), specified
    in docs/superpowers/plans/2026-09-11-edge-first-phase-c-screening-lane.md, C1.
    Linear first-crossing interpolation is our policy, not that paper's estimator
    or an exponential-decay fit.
    """
    if not decay:
        raise DataError("ic_half_life needs at least one horizon")
    if any(v is not None and not math.isfinite(v) for v in decay.values()):
        raise DataError("ic_half_life decay values must be finite or None")
    horizons = sorted(decay)
    base = decay[horizons[0]]
    if base is None or base <= 0.0:
        return None
    half = base / 2.0
    previous_h, previous_v = horizons[0], base
    for h in horizons[1:]:
        value = decay[h]
        if value is None:
            return None
        if value <= half:
            return previous_h + (h - previous_h) * (previous_v - half) / (previous_v - value)
        previous_h, previous_v = h, value
    return None


def _bucket_bounds(n_names: int, quantiles: int) -> list[tuple[int, int]]:
    """Equal-count buckets over stable-sorted positions.

    Bottom and top hold exactly ``n // q`` names each so a long/short spread is symmetric; the
    ``n mod q`` leftover names sit in the middle of the ranking, spread over the inner buckets
    (unbucketed when ``q == 2``).
    """
    base = n_names // quantiles
    inner = quantiles - 2
    if inner == 0:
        return [(0, base), (n_names - base, n_names)]
    start, stop = base, n_names - base
    width = stop - start
    middle = [(start + k * width // inner, start + (k + 1) * width // inner) for k in range(inner)]
    return [(0, base), *middle, (n_names - base, n_names)]


def _validate_quantiles(quantiles: int, min_names: int) -> None:
    """``quantiles <= min_names`` guarantees every scored date fills the top and bottom bucket."""
    if type(quantiles) is not int or not 2 <= quantiles <= min_names:
        raise DataError(
            f"quantiles must be an integer in [2, min_names={min_names}]; got {quantiles!r}"
        )


def quantile_returns(
    signal: object, outcome: object, *, quantiles: int = 5, min_names: int = 5
) -> QuantileReport:
    """Mean outcome per signal-rank bucket, spread and descriptive rank monotonicity.

    Portfolio-sort concept: Fama & French (1992), DOI 10.1111/j.1540-6261.1992.tb04398.x.
    Monotonicity uses Spearman (1904), DOI 10.2307/1412159, not an MR test.
    Equal date weighting and canonical tie order are local DESIGN: each extreme
    holds n//q names; inner buckets share the remainder (unbucketed only for q=2).
    See docs/superpowers/plans/2026-09-17-cancellation-and-research-walkthrough.md.
    """
    signals, outcomes = _panels(signal, outcome)
    min_names = _min_names(min_names)
    _validate_quantiles(quantiles, min_names)
    sums = np.zeros(quantiles)
    n_dates = 0
    for t in range(signals.shape[0]):
        mask = np.isfinite(signals[t]) & np.isfinite(outcomes[t])
        if int(mask.sum()) < min_names:
            continue
        order = np.argsort(signals[t][mask], kind="stable")
        present = outcomes[t][mask]
        for k, (lo, hi) in enumerate(_bucket_bounds(int(mask.sum()), quantiles)):
            sums[k] += float(np.mean(present[order[lo:hi]]))
        n_dates += 1
    if n_dates == 0:
        raise DataError("quantile_returns has no scorable dates")
    means = sums / n_dates
    monotonicity = pearson_or_none(
        average_ranks(np.arange(quantiles, dtype=float)), average_ranks(means)
    )
    return QuantileReport(
        [float(m) for m in means], float(means[-1] - means[0]), monotonicity, n_dates
    )


def bucket_turnover(signal: object, *, quantiles: int = 5, min_names: int = 5) -> float:
    """Mean fraction of top/bottom-bucket slots whose name left between consecutive dates.

    Only names present on both dates count; the denominator is the number of top plus bottom
    slots on the earlier date.

    Primary local DESIGN: docs/superpowers/plans/2026-09-11-edge-first-phase-c-screening-lane.md,
    C1 bucket_turnover. Both dates are ranked on their common-name subset. This
    replacement-count proxy excludes listing/delisting and weight drift; it is
    not total portfolio turnover.
    """
    signals = _panel(signal)
    if signals.shape[0] < 2:
        raise DataError("bucket_turnover requires at least two dates")
    min_names = _min_names(min_names)
    _validate_quantiles(quantiles, min_names)
    fractions: list[float] = []
    for t in range(1, signals.shape[0]):
        mask = np.isfinite(signals[t - 1]) & np.isfinite(signals[t])
        n_present = int(mask.sum())
        if n_present < min_names:
            continue
        names = np.flatnonzero(mask)
        bounds = _bucket_bounds(n_present, quantiles)
        leavers = 0
        slots = 0
        for lo, hi in (bounds[0], bounds[-1]):
            before = set(names[np.argsort(signals[t - 1][mask], kind="stable")[lo:hi]].tolist())
            after = set(names[np.argsort(signals[t][mask], kind="stable")[lo:hi]].tolist())
            leavers += len(before - after)
            slots += len(before)
        fractions.append(leavers / slots)
    if not fractions:
        raise DataError("bucket_turnover has no consecutive date pair with enough names")
    return float(np.mean(fractions))


def cost_adjusted_spread(spread: float, turnover: float, *, cost_bps: float) -> float:
    """``spread − 4·turnover·cost_bps/1e4`` with ``cost_bps`` a ONE-WAY cost per unit notional.

    ``turnover`` is the fraction of top-plus-bottom slots replaced (``bucket_turnover``); each
    replaced slot in a $1-per-leg book sells the leaver and buys the entrant, so the traded
    notional per period is ``4·turnover`` and the drag on the long-minus-short spread is
    ``4·turnover·cost``.

    Primary local accounting DESIGN: Phase-C C1 cost convention in
    docs/superpowers/plans/2026-09-11-edge-first-phase-c-screening-lane.md.
    Equal long/short notional follows the zero-investment discussion in Sharpe
    (1994), https://web.stanford.edu/~wfsharpe/art/sr/SR.htm. The factor four is
    two legs times exit+entry, not an empirical cost model. Price drift and
    universe entry/exit are not modeled by this replacement-only proxy.
    """
    if any(type(v) is bool or not math.isfinite(v) for v in (spread, turnover, cost_bps)):
        raise DataError("cost_adjusted_spread inputs must be finite numbers")
    if cost_bps < 0.0:
        raise DataError("cost_bps must be non-negative")
    return spread - 4.0 * turnover * cost_bps / 1e4


def _design(rows: Sequence[np.ndarray]) -> np.ndarray:
    return np.column_stack([np.ones(rows[0].size), *rows])


def _solve(design: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank < design.shape[1]:
        raise DataError("cross-sectional design matrix is rank deficient (collinear factors)")
    return np.asarray(beta, dtype=float)


def fama_macbeth(factors: Sequence[object], outcome: object, *, min_names: int = 5) -> FamaMacBeth:
    """Per-date OLS of outcome on the factors with an intercept; slopes averaged over dates.

    ``t = mean/std·√n`` with the sample std of the per-date slopes (Fama & MacBeth 1973, no
    overlap correction); ``None`` when fewer than two dates or the slopes do not disperse.
    """
    if not factors:
        raise DataError("fama_macbeth needs at least one factor panel")
    outcomes, *panels = _panels(outcome, *factors)
    min_names = _min_names(min_names)
    slopes: list[np.ndarray] = []
    for t in range(outcomes.shape[0]):
        mask = np.isfinite(outcomes[t])
        for p in panels:
            mask &= np.isfinite(p[t])
        if int(mask.sum()) < min_names:
            continue
        beta = _solve(_design([p[t][mask] for p in panels]), outcomes[t][mask])
        slopes.append(beta[1:])
    if not slopes:
        raise DataError("fama_macbeth has no scorable dates")
    matrix = np.vstack(slopes)
    means = matrix.mean(axis=0)
    t_stats: list[float | None] = []
    for k in range(matrix.shape[1]):
        std = _sample_std(matrix[:, k])
        if std is None or std <= 1e-12 * max(1.0, abs(float(means[k]))):
            t_stats.append(None)  # no dispersion across dates (e.g. noiseless data)
        else:
            t_stats.append(float(means[k]) / std * math.sqrt(matrix.shape[0]))
    return FamaMacBeth([float(m) for m in means], t_stats, int(matrix.shape[0]))


def orthogonalize(signal: object, controls: Sequence[object], *, min_names: int = 5) -> np.ndarray:
    """Per-date residual of the signal regressed on the controls with an intercept.

    NaN where the signal or any control is absent, or where fewer than ``min_names`` names remain.

    Intercept OLS residualization uses the least-squares framework in Fama &
    MacBeth (1973), pp. 616-619, DOI 10.1086/260061. Per-date masking, minimum size
    and rank rejection are local DESIGN; residualization is not a causal-confounding
    correction.
    """
    if not controls:
        raise DataError("orthogonalize needs at least one control panel")
    signals, *panels = _panels(signal, *controls)
    min_names = _min_names(min_names)
    residual = np.full(signals.shape, np.nan)
    for t in range(signals.shape[0]):
        mask = np.isfinite(signals[t])
        for p in panels:
            mask &= np.isfinite(p[t])
        if int(mask.sum()) < min_names:
            continue
        design = _design([p[t][mask] for p in panels])
        beta = _solve(design, signals[t][mask])
        residual[t, mask] = signals[t][mask] - design @ beta
    return residual


__all__ = [
    "PANEL_VERSION",
    "FamaMacBeth",
    "IcSeries",
    "QuantileReport",
    "bucket_turnover",
    "cost_adjusted_spread",
    "cross_sectional_ic",
    "fama_macbeth",
    "forward_outcomes",
    "ic_decay",
    "ic_half_life",
    "orthogonalize",
    "quantile_returns",
]
