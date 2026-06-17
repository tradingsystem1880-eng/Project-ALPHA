"""Walk-forward OOS stitching + deterministic run id (``alpha_cli._runner``).

The OOS curve for a fixed-parameter strategy is one full backtest sliced into the scored test
windows (train windows are warmup only). These tests pin: the stitch equals the concatenation of
the test-window return slices, the warmup floor fails loud, fold bookkeeping is correct, and the
run id is a deterministic function of its inputs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_cli._runner import run_id_for, walk_forward_oos
from alpha_core import DataError
from alpha_validation import walk_forward_splits


def _equity_curve(n_returns: int, seed: int) -> tuple[list[tuple[datetime, float]], np.ndarray]:
    """A daily equity curve of ``n_returns + 1`` points; also return the true per-period returns."""
    rets = np.random.default_rng(seed).normal(0.001, 0.01, n_returns)
    vals = 100.0 * np.concatenate(([1.0], np.cumprod(1.0 + rets)))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    curve = [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]
    return curve, rets


_WF = dict(train_size=10, test_size=5, embargo=2, anchored=False, periods_per_year=252, min_train=8)


def test_stitch_equals_concatenated_test_windows() -> None:
    curve, rets = _equity_curve(30, seed=0)
    res = walk_forward_oos(curve, **_WF)  # type: ignore[arg-type]
    splits = walk_forward_splits(30, train_size=10, test_size=5, embargo=2)
    expected = np.concatenate([rets[s.test.start : s.test.stop] for s in splits])
    assert np.allclose(res.oos_returns, expected)
    # equity is the stitched curve rebased to 1.0 with a leading point
    assert res.oos_equity[0] == 1.0
    assert np.allclose(res.oos_equity, np.concatenate(([1.0], np.cumprod(1.0 + expected))))
    assert len(res.oos_timestamps) == res.oos_equity.size  # one timestamp per equity point


def test_folds_track_split_bounds_and_are_contiguous() -> None:
    curve, _ = _equity_curve(30, seed=1)
    res = walk_forward_oos(curve, **_WF)  # type: ignore[arg-type]
    splits = walk_forward_splits(30, train_size=10, test_size=5, embargo=2)
    assert len(res.folds) == len(splits)
    for fold, s in zip(res.folds, splits, strict=True):
        assert (fold.test_start, fold.test_end) == (s.test.start, s.test.stop)
        assert (fold.train_start, fold.train_end) == (s.train.start, s.train.stop)
        assert fold.n_test == 5
    # OOS test windows tile with no gaps across folds
    for i in range(len(res.folds) - 1):
        assert res.folds[i + 1].test_start == res.folds[i].test_end


def test_warmup_floor_fails_loud() -> None:
    curve, _ = _equity_curve(30, seed=2)
    with pytest.raises(DataError):
        walk_forward_oos(
            curve,
            train_size=10,
            test_size=5,
            embargo=2,
            anchored=False,
            periods_per_year=252,
            min_train=20,  # train_size 10 < 20 -> first OOS bar would be un-warmed
        )


def test_run_id_is_deterministic_and_sensitive() -> None:
    base = {"symbol": "SPY", "seed": 7, "train_size": 300, "fee_bps": 1.0}
    rid = run_id_for(base)
    assert len(rid) == 16 and all(c in "0123456789abcdef" for c in rid)
    assert run_id_for(dict(base)) == rid  # order-independent, value-determined
    assert run_id_for({**base, "seed": 8}) != rid  # any input change moves the id
