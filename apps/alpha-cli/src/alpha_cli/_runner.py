"""Engine ↔ gauntlet orchestration helpers for the validation CLI.

The CLI is the only layer the import DAG lets touch both the backtest engine and the validation
gauntlet, so the glue lives here. This module currently owns the deterministic run id and the
walk-forward OOS stitch; the engine-running helpers (``load_bars``, ``run_full_backtest``) are added
with the backtest command.

Walk-forward for a *fixed-parameter* strategy is out-of-sample evaluation, not refitting: one
deterministic full-series backtest is sliced into the scored test windows (the train windows are
indicator warmup). The OOS return stream is the concatenation of those test-window slices — and
because walk-forward test windows tile contiguously, that stream is gap-free.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from alpha_core import DataError
from alpha_validation import (
    FloatArray,
    FoldSummary,
    cagr,
    sharpe_ratio,
    to_returns,
    walk_forward_splits,
)


@dataclass(frozen=True)
class OOSResult:
    """Stitched out-of-sample returns/equity (aligned timestamps) plus per-fold summaries."""

    oos_returns: FloatArray  # length N
    oos_equity: FloatArray  # length N+1, leading 1.0
    oos_timestamps: list[datetime]  # length N+1, one per equity point
    folds: tuple[FoldSummary, ...]


def run_id_for(payload: Mapping[str, object]) -> str:
    """A deterministic 16-hex-char id for a run, from its canonical (sorted-key) JSON payload.

    Same symbol + params + costs + seed → same id → same artifact directory → reproducible
    (spec §11.4). No wall-clock goes in, so re-running is byte-identical.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _fold_metrics(slice_: FloatArray, periods_per_year: int) -> tuple[float, float, float]:
    """(cumulative return, annualized Sharpe, CAGR) for one fold's OOS return slice.

    Sharpe is NaN for a zero-variance (flat) fold and CAGR is NaN if the fold equity is
    non-positive — both are recorded rather than raised, so a degenerate fold never aborts the run.
    """
    oos_return = float(np.prod(1.0 + slice_) - 1.0)
    if slice_.size >= 2 and float(np.std(slice_, ddof=1)) > 0.0:
        oos_sharpe = sharpe_ratio(slice_, periods_per_year=periods_per_year)
    else:
        oos_sharpe = math.nan
    fold_equity = np.concatenate(([1.0], np.cumprod(1.0 + slice_)))
    if bool(np.all(fold_equity > 0.0)):
        oos_cagr = cagr(fold_equity, periods_per_year=periods_per_year)
    else:
        oos_cagr = math.nan
    return oos_return, oos_sharpe, oos_cagr


def walk_forward_oos(
    equity_curve: Sequence[tuple[datetime, float]],
    *,
    train_size: int,
    test_size: int,
    embargo: int,
    anchored: bool,
    periods_per_year: int,
    min_train: int,
) -> OOSResult:
    """Slice a full-run equity curve into its scored out-of-sample windows and stitch them.

    ``min_train`` is the strategy's warmup floor (``max(lookback+skip+1, vol_window+1)``); a
    ``train_size`` below it would let the first scored OOS bar come from an un-warmed strategy, so
    it fails loud (``DataError``). Fails loud too when no fold fits the series.
    """
    if train_size < min_train:
        raise DataError(
            f"train_size {train_size} < warmup floor {min_train} "
            "(max(lookback+skip+1, vol_window+1)); the first OOS bar would be un-warmed"
        )
    timestamps = [ts for ts, _ in equity_curve]
    values = np.array([v for _, v in equity_curve], dtype=np.float64)
    returns = to_returns(values)  # returns[i] is realized at timestamps[i+1]
    splits = walk_forward_splits(
        returns.size,
        train_size=train_size,
        test_size=test_size,
        embargo=embargo,
        anchored=anchored,
    )
    if not splits:
        raise DataError("walk-forward produced no folds for the given sizes")

    folds: list[FoldSummary] = []
    test_slices: list[FloatArray] = []
    test_indices: list[int] = []
    for i, sp in enumerate(splits):
        sl = returns[sp.test.start : sp.test.stop]
        test_slices.append(sl)
        test_indices.extend(range(sp.test.start, sp.test.stop))
        oos_return, oos_sharpe, oos_cagr = _fold_metrics(sl, periods_per_year)
        folds.append(
            FoldSummary(
                index=i,
                train_start=sp.train.start,
                train_end=sp.train.stop,
                test_start=sp.test.start,
                test_end=sp.test.stop,
                n_test=int(sl.size),
                oos_return=oos_return,
                oos_sharpe=oos_sharpe,
                oos_cagr=oos_cagr,
            )
        )

    oos_returns = np.concatenate(test_slices)
    oos_equity = np.concatenate(([1.0], np.cumprod(1.0 + oos_returns)))
    # equity point 0 sits at the first OOS session; point j+1 at the session the return realizes
    first_test_start = splits[0].test.start
    oos_timestamps = [timestamps[first_test_start]] + [timestamps[k + 1] for k in test_indices]
    return OOSResult(
        oos_returns=oos_returns,
        oos_equity=oos_equity,
        oos_timestamps=oos_timestamps,
        folds=tuple(folds),
    )
