"""Hardened future-poison guards for the trailing D1 / descriptive primitives (ADR-0025).

Three variants per primitive, each with the discriminating-power idiom of
``test_future_poison_pattern.py``:

1. **Extreme-value poison** — rewriting the future must leave the past byte-identical AND must
   change the future (else the guard is vacuous).
2. **Non-finite poison** — NaN/inf anywhere (even in the far future) must FAIL LOUD, never
   silently pass through into a "clean" prefix; silent NaN propagation is the classic leak.
3. **Must-fail leaky twin** — a deliberately non-causal twin (full-sample quantiles, centred
   window) is fed the same poison; the guard predicate must REJECT it, proving the guard has
   the power to catch the bug it exists for.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from alpha_core import DataError
from alpha_research.descriptives import volatility_regime_tags
from alpha_research.ic import rolling_rank_ic
from alpha_research.stability import rolling_effect_size

pytestmark = pytest.mark.bias_guard

_CUT = 45
_N = 70
_SIGNAL = [math.sin(i / 3.0) for i in range(_N)]
_OUTCOME = [math.cos(i / 5.0) + (i % 3) * 0.1 for i in range(_N)]
# heteroskedastic returns (vol ramps 0.5%→2%) so regime terciles are genuinely populated
_RETURNS = [
    float(v) for v in np.random.default_rng(3).normal(size=_N) * np.linspace(0.005, 0.02, _N)
]


def _poison_tail(values: list[float], fill: float) -> list[float]:
    return [*values[:_CUT], *([fill] * (_N - _CUT))]


# ---- 1. extreme-value poison: past unchanged, future changed -------------------------------


def test_rolling_rank_ic_prefix_is_immune_and_suffix_is_sensitive() -> None:
    clean = rolling_rank_ic(_SIGNAL, _OUTCOME, window=10)
    poisoned = rolling_rank_ic(
        _poison_tail(_SIGNAL, 99.0), _poison_tail(_OUTCOME, -99.0), window=10
    )
    assert poisoned[:_CUT] == clean[:_CUT]
    assert poisoned[_CUT:] != clean[_CUT:]  # discriminating power


def test_rolling_effect_size_prefix_is_immune_and_suffix_is_sensitive() -> None:
    clean = rolling_effect_size(_RETURNS, window=10)
    poisoned = rolling_effect_size(_poison_tail(_RETURNS, 9.9), window=10)
    assert poisoned[:_CUT] == clean[:_CUT]
    assert poisoned[_CUT:] != clean[_CUT:]


def test_volatility_regime_tags_prefix_is_immune_and_suffix_is_sensitive() -> None:
    clean = volatility_regime_tags(_RETURNS, window=10)
    poisoned = volatility_regime_tags(_poison_tail(_RETURNS, 9.9), window=10)
    assert poisoned[:_CUT] == clean[:_CUT]
    assert poisoned[_CUT:] != clean[_CUT:]


# ---- 2. non-finite poison fails loud, never silently ---------------------------------------


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_future_fails_loud_everywhere(bad: float) -> None:
    with pytest.raises(DataError, match="finite"):
        rolling_rank_ic(_SIGNAL, _poison_tail(_OUTCOME, bad), window=10)
    with pytest.raises(DataError, match="finite"):
        rolling_rank_ic(_poison_tail(_SIGNAL, bad), _OUTCOME, window=10)
    with pytest.raises(DataError, match="finite"):
        rolling_effect_size(_poison_tail(_RETURNS, bad), window=10)
    with pytest.raises(DataError, match="finite"):
        volatility_regime_tags(_poison_tail(_RETURNS, bad), window=10)


# ---- 3. must-fail leaky twins: the guard predicate rejects a non-causal implementation -----


def _leaky_full_sample_regime_tags(returns: list[float], *, window: int) -> list[str]:
    """The bug the causal version exists to prevent: thresholds from FULL-SAMPLE terciles."""
    array = np.asarray(returns, dtype=float)
    vols = [
        float(np.std(array[i - window + 1 : i + 1], ddof=1)) for i in range(window - 1, array.size)
    ]
    low, high = np.quantile(vols, (1 / 3, 2 / 3))
    tags = ["warmup"] * (window - 1)
    for vol in vols:
        tags.append("low" if vol <= low else "high" if vol >= high else "mid")
    return tags


def _leaky_centred_effect_size(outcomes: list[float], *, window: int) -> list[float | None]:
    """A centred window peeks ``window // 2`` steps into the future."""
    array = np.asarray(outcomes, dtype=float)
    half = window // 2
    out: list[float | None] = []
    for i in range(array.size):
        lo, hi = max(0, i - half), min(array.size, i + half + 1)
        chunk = array[lo:hi]
        sd = float(np.std(chunk, ddof=1)) if chunk.size > 1 else 0.0
        out.append(float(np.mean(chunk)) / sd if sd > 0.0 else None)
    return out


def test_leaky_full_sample_regime_twin_is_caught_by_the_guard() -> None:
    clean = _leaky_full_sample_regime_tags(_RETURNS, window=10)
    poisoned = _leaky_full_sample_regime_tags(_poison_tail(_RETURNS, 9.9), window=10)
    assert poisoned[:_CUT] != clean[:_CUT]  # the guard predicate would FAIL — as it must


def test_leaky_centred_effect_size_twin_is_caught_by_the_guard() -> None:
    clean = _leaky_centred_effect_size(_RETURNS, window=10)
    poisoned = _leaky_centred_effect_size(_poison_tail(_RETURNS, 9.9), window=10)
    assert poisoned[:_CUT] != clean[:_CUT]
