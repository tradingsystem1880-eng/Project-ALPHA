"""Metamorphic relations for CSCV probability of backtest overfitting (Bailey et al. 2016).

Primary source: Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest
Overfitting" (J. Computational Finance 2016): S blocks, C(S, S/2) in-sample/out-of-sample
splits, logit of the IS-best config's OOS relative rank, PBO = share of non-positive logits.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.overfitting import probability_of_backtest_overfitting

pytestmark = pytest.mark.oracle

_RNG = np.random.default_rng(11)


def _noise_matrix(t: int = 256, s: int = 12) -> np.ndarray:
    return _RNG.normal(0.0, 0.01, size=(t, s))


def test_split_count_is_the_central_binomial_coefficient() -> None:
    for n_blocks in (2, 4, 8, 10, 16):
        result = probability_of_backtest_overfitting(_noise_matrix(t=64), n_blocks=n_blocks)
        assert result.n_splits == math.comb(n_blocks, n_blocks // 2)
        assert result.logits.shape == (result.n_splits,)


def test_pbo_is_invariant_to_column_permutation() -> None:
    """Which column a config sits in is arbitrary; PBO and the logit multiset must not move."""
    m = _noise_matrix()
    base = probability_of_backtest_overfitting(m, n_blocks=8)
    permuted = probability_of_backtest_overfitting(m[:, ::-1], n_blocks=8)
    assert permuted.pbo == pytest.approx(base.pbo)
    assert np.allclose(np.sort(permuted.logits), np.sort(base.logits))


def test_pbo_is_invariant_to_a_common_positive_rescaling() -> None:
    """The default statistic is a Sharpe, so scaling every return by k>0 changes nothing."""
    m = _noise_matrix()
    base = probability_of_backtest_overfitting(m, n_blocks=8)
    scaled = probability_of_backtest_overfitting(m * 3.7, n_blocks=8)
    assert scaled.pbo == pytest.approx(base.pbo)
    assert np.allclose(scaled.logits, base.logits)


def test_pbo_is_the_share_of_non_positive_logits_and_pass_follows_the_threshold() -> None:
    result = probability_of_backtest_overfitting(_noise_matrix(), n_blocks=8, threshold=0.5)
    assert result.pbo == pytest.approx(float(np.mean(result.logits <= 0.0)))
    assert result.passed == (result.pbo <= 0.5)
    strict = probability_of_backtest_overfitting(_noise_matrix(), n_blocks=8, threshold=0.01)
    assert strict.passed == (strict.pbo <= 0.01)


def test_pure_noise_sits_near_one_half() -> None:
    """With no skill anywhere the IS-best config's OOS rank is uniform ⇒ PBO ≈ 0.5.

    Tolerance: 70 splits per matrix over 8 independent matrices; the logits within one matrix
    are dependent, so a loose ±0.2 band on the average is used rather than a binomial bound.
    """
    pbos = [
        probability_of_backtest_overfitting(_noise_matrix(t=512, s=10), n_blocks=8).pbo
        for _ in range(8)
    ]
    assert 0.3 < float(np.mean(pbos)) < 0.7


def test_one_genuinely_superior_config_drives_pbo_to_zero() -> None:
    """A config that dominates in every block is IS-best AND OOS-best in every split."""
    m = _noise_matrix(t=256, s=8)
    m[:, 3] += 0.05  # a large, persistent edge relative to 0.01 noise
    result = probability_of_backtest_overfitting(m, n_blocks=8)
    assert result.pbo == 0.0
    assert bool(np.all(result.logits > 0.0))


def test_a_config_that_flips_sign_between_halves_is_maximally_overfit() -> None:
    """Winner in one block set, loser in the complement ⇒ every split's IS-best fails OOS."""
    t, s = 64, 6
    m = np.zeros((t, s))
    m += _RNG.normal(0.0, 1e-4, size=(t, s))  # tiny noise so Sharpe is defined everywhere
    # config 0 is +1 in even blocks and -1 in odd blocks; config 1 the mirror image
    block = t // 2  # n_blocks=2 => two blocks
    m[:block, 0] += 0.01
    m[block:, 0] -= 0.01
    m[:block, 1] -= 0.01
    m[block:, 1] += 0.01
    result = probability_of_backtest_overfitting(m, n_blocks=2)
    assert result.n_splits == 2
    assert result.pbo == 1.0


def test_shape_and_parameter_guards_fail_loud() -> None:
    m = _noise_matrix(t=32, s=3)
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(m[:, :1], n_blocks=4)  # < 2 configs
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(m, n_blocks=3)  # odd
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(m, n_blocks=64)  # more blocks than rows
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(m, threshold=1.0)
    poisoned = m.copy()
    poisoned[0, 0] = math.nan
    with pytest.raises(DataError):
        probability_of_backtest_overfitting(poisoned, n_blocks=4)
