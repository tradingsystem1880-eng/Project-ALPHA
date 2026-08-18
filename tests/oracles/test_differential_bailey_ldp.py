"""Differential oracles: production PSR/DSR/expected-max/PBO vs independent loop transcriptions.

The references in ``tests/oracles/_reference/bailey_ldp.py`` were transcribed from the papers
without reading the production code; agreement to ~1e-10 on random inputs is strong evidence
that the vectorised numpy/scipy implementation is a faithful transcription too. Disagreement
localises the bug to one side. Sources are cited in the reference module.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from alpha_validation.dsr import (
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from alpha_validation.overfitting import probability_of_backtest_overfitting
from tests.oracles._reference import bailey_ldp as ref

pytestmark = pytest.mark.oracle

_RETURNS = st.lists(
    st.floats(min_value=-0.1, max_value=0.1, allow_nan=False, allow_infinity=False),
    min_size=8,
    max_size=120,
).filter(lambda r: np.std(r, ddof=1) > 1e-6)


@given(_RETURNS, st.floats(min_value=-0.5, max_value=0.5))
@settings(max_examples=100, deadline=None)
def test_psr_matches_the_reference_transcription(returns: list[float], benchmark: float) -> None:
    assert probabilistic_sharpe_ratio(returns, benchmark_sr=benchmark) == pytest.approx(
        ref.psr(returns, benchmark), rel=1e-10, abs=1e-12
    )


@given(st.floats(min_value=1e-6, max_value=10.0), st.integers(min_value=1, max_value=50_000))
@settings(max_examples=100, deadline=None)
def test_expected_max_sharpe_matches_the_reference_transcription(v: float, n: int) -> None:
    assert expected_max_sharpe(v, n) == pytest.approx(ref.sr0(v, n), rel=1e-12, abs=1e-15)


@given(
    _RETURNS,
    st.lists(
        st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=40,
    ).filter(lambda t: np.std(t, ddof=1) > 1e-6),
)
@settings(max_examples=100, deadline=None)
def test_dsr_matches_the_reference_transcription(returns: list[float], trials: list[float]) -> None:
    result = deflated_sharpe(returns, trial_sharpes=trials)
    assert result.dsr == pytest.approx(ref.dsr(returns, trials), rel=1e-10, abs=1e-12)
    assert result.psr == pytest.approx(ref.psr(returns), rel=1e-10, abs=1e-12)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("n_blocks", [4, 6, 8])
def test_pbo_matches_the_reference_transcription(seed: int, n_blocks: int) -> None:
    rng = np.random.default_rng(seed)
    t, s = 96, 7
    m = rng.normal(0.0, 0.01, size=(t, s))
    m[:, seed % s] += 0.004  # one mildly better config so ranks are not pure noise
    result = probability_of_backtest_overfitting(m, n_blocks=n_blocks)
    ref_pbo, ref_logits = ref.pbo(m.tolist(), n_blocks)
    assert result.pbo == pytest.approx(ref_pbo)
    assert np.allclose(result.logits, ref_logits, rtol=1e-10, atol=1e-12)
