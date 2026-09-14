"""Future-poison guard for the PIP pattern miner walk-forward signal."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import pip_windows
from alpha_research.pip_miner import walk_forward_pip_signal

pytestmark = pytest.mark.bias_guard

CUT = 399  # a retrain bar: the model refit here must not see the poison either


def _signal(log_close: np.ndarray) -> np.ndarray:
    pw = pip_windows(log_close, lookback=24, n_pips=5)
    return walk_forward_pip_signal(
        pw.matrix,
        pw.end_index,
        log_close,
        train_bars=300,
        step_bars=100,
        hold=6,
        k_range=(3, 5),
        seed=9,
    )


def test_poisoning_bars_after_cut_leaves_signal_up_to_cut_unchanged() -> None:
    log_close = np.cumsum(np.random.default_rng(3).normal(0.0, 0.01, size=700))
    base = _signal(log_close)
    poisoned = log_close.copy()
    poisoned[CUT + 1 :] = poisoned[CUT] + np.cumsum(
        np.random.default_rng(99).normal(0.002, 0.03, size=poisoned.size - CUT - 1)
    )
    again = _signal(poisoned)
    assert np.array_equal(base[: CUT + 1], again[: CUT + 1])
    assert base[299:].any()


def test_leaky_twin_that_fits_on_poisoned_bars_is_caught() -> None:
    """A miner that trains past the cut moves the pre-cut signal; the guard is not vacuous."""
    log_close = np.cumsum(np.random.default_rng(3).normal(0.0, 0.01, size=700))
    poisoned = log_close.copy()
    poisoned[CUT + 1 :] = poisoned[CUT] + np.cumsum(
        np.random.default_rng(99).normal(0.002, 0.03, size=poisoned.size - CUT - 1)
    )
    pw = pip_windows(log_close, lookback=24, n_pips=5)
    pw_poisoned = pip_windows(poisoned, lookback=24, n_pips=5)

    def leaky(matrix: np.ndarray, closes: np.ndarray) -> np.ndarray:
        # trains once on the WHOLE series (bars after CUT included), then predicts every bar
        from alpha_research.pip_miner import fit_pip_clusters, predict_pip_cluster

        ends = pw.end_index
        keep = ends + 6 <= closes.size - 1
        model = fit_pip_clusters(
            matrix[keep],
            ends[keep],
            closes,
            train_end=closes.size - 1,
            hold=6,
            k_range=(3, 5),
            seed=9,
        )
        return np.array([predict_pip_cluster(model, row).signal for row in matrix])

    honest = leaky(pw.matrix, log_close)
    leaked = leaky(pw_poisoned.matrix, poisoned)
    assert not np.array_equal(honest[: CUT - 23], leaked[: CUT - 23])
