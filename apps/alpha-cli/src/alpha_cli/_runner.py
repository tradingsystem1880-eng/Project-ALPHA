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
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from alpha_core import Bar, DataError
from alpha_validation import (
    FloatArray,
    FoldSummary,
    cagr,
    sharpe_ratio,
    to_returns,
    walk_forward_splits,
)

if TYPE_CHECKING:
    from alpha_backtest.results import BacktestResult


@dataclass(frozen=True)
class RunSpec:
    """The full, picklable specification of one backtest + walk-forward evaluation.

    Bundles the (pre-registered, fixed) strategy parameters, the cost/account model, and the
    walk-forward geometry so the same object drives the real run, every synthetic Tier-2 path, and
    the manifest. ``account_type`` is a plain string (``"CASH"``/``"MARGIN"``) so the spec stays
    free of nautilus imports and trivially picklable across a process pool.
    """

    lookback: int
    skip: int
    vol_window: int
    target_vol: float
    rebalance_every: int
    max_leverage: float
    allow_short: bool
    periods_per_year: int
    fee_bps: float
    slippage_bps: float
    starting_cash: float
    account_type: str
    train_size: int
    test_size: int
    embargo: int
    anchored: bool
    strategy_name: str = "ts_momentum"
    # per-strategy params not promoted to first-class fields, as sorted (name, value) pairs so the
    # spec stays one fixed, picklable, hashable shape across every strategy.
    strategy_params: tuple[tuple[str, float], ...] = ()

    def param(self, name: str, default: float) -> float:
        """Read a per-strategy parameter from ``strategy_params``, or ``default`` if absent."""
        for key, value in self.strategy_params:
            if key == name:
                return value
        return default

    @property
    def min_train(self) -> int:
        """Warmup floor (strategy-specific): the first scored OOS bar must be fully warmed up."""
        from alpha_cli import _strategies

        return _strategies.warmup_for(self)


def resolve_allow_short(allow_short: bool | None, account_type: str) -> bool:
    """Resolve the CLI's tri-state ``--allow-short`` default from the account type.

    ``None`` (flag omitted) becomes ``True`` on MARGIN and ``False`` on CASH — the only
    combination a CASH account can actually hold is long-flat. An explicit ``--allow-short`` on
    CASH is passed through so ``run_full_backtest`` fails loud instead of silently coercing.
    """
    if allow_short is None:
        return account_type.upper() == "MARGIN"
    return allow_short


def parse_strategy_params(items: Sequence[str] | None) -> tuple[tuple[str, float], ...]:
    """Parse repeatable ``name=value`` CLI options into the spec's sorted ``strategy_params`` shape.

    Sorted by name so the same params in any CLI order produce the same ``RunSpec`` (and run id).
    Fails loud (``DataError``) on a malformed item or a non-numeric value.
    """
    if not items:
        return ()
    parsed: dict[str, float] = {}
    for item in items:
        if "=" not in item:
            raise DataError(f"strategy param must be name=value, got {item!r}")
        name, _, raw = item.partition("=")
        name = name.strip()
        if not name:
            raise DataError(f"strategy param has empty name: {item!r}")
        try:
            parsed[name] = float(raw)
        except ValueError:
            raise DataError(f"strategy param {name!r} must be numeric, got {raw!r}") from None
    return tuple(sorted(parsed.items()))


def load_bars(
    symbol: str, *, data_dir: Path, snapshot_id: str | None = None
) -> tuple[list[Bar], str | None]:
    """Load the full point-in-time history for ``symbol`` — live store or a frozen snapshot.

    Reads through ``PointInTimeSource`` — the same look-ahead-safe seam strategies use — with a
    far-future ``as_of`` so the whole series is returned (corporate actions applied). With a
    ``snapshot_id`` the read is rooted at ``data_dir/snapshots/<id>`` (integrity-verified first),
    so the manifest's provenance claim is what the run actually consumed — the live store is
    wholesale-replaced by pulls and cannot back a reproducibility claim. Fails loud (``DataError``)
    on a missing/tampered snapshot or fewer than 2 bars.
    """
    from alpha_data.snapshot import verify_snapshot
    from alpha_data.source import PointInTimeSource
    from alpha_data.store import ParquetStore

    if snapshot_id is not None:
        snap_dir = data_dir / "snapshots" / snapshot_id
        verify_snapshot(snap_dir)  # re-hash against the manifest before trusting the bytes
        store = ParquetStore(snap_dir)
    else:
        store = ParquetStore(data_dir / "store")
    source = PointInTimeSource(store, {symbol: store.read_actions(symbol)})
    bars = source.as_of(symbol, datetime(2999, 1, 1, tzinfo=UTC))
    if len(bars) < 2:
        raise DataError(f"need >= 2 bars to backtest {symbol!r}, got {len(bars)}")
    return bars, snapshot_id


def run_full_backtest(bars: Sequence[Bar], spec: RunSpec) -> BacktestResult:
    """Run ``spec``'s fixed-parameter strategy over ``bars`` once, net of costs.

    The single source of truth for both ``alpha backtest run`` and the validation gauntlet (and
    every synthetic Tier-2 path). The concrete strategy is resolved through the registry
    (``_strategies``); engine imports are lazy so the pure helpers above stay importable without
    dragging in nautilus.
    """
    from nautilus_trader.model.enums import AccountType

    from alpha_backtest.engine import run_backtest
    from alpha_backtest.feed import daily_bar_type, to_execution_feed
    from alpha_backtest.instruments import equity_instrument
    from alpha_cli import _strategies

    symbol = bars[0].symbol
    instrument = equity_instrument(symbol)
    bar_type = daily_bar_type(symbol)
    feed = to_execution_feed(bars, bar_type, slippage_bps=spec.slippage_bps)
    strategy = _strategies.build_strategy(spec, instrument.id, bar_type)
    # Fail loud (golden rule): don't silently coerce a typo'd/cased value to CASH and drop leverage.
    account_kind = spec.account_type.upper()
    if account_kind not in ("CASH", "MARGIN"):
        raise DataError(f"account_type must be 'CASH' or 'MARGIN', got {spec.account_type!r}")
    # Fail loud (golden rule): a CASH venue denies a short-entry SELL wholesale, so the strategy
    # cannot even flatten - it silently rides a stale long through drawdowns (verified against the
    # engine). The combination is a configuration lie, not a runnable book.
    if account_kind == "CASH" and spec.allow_short:
        raise DataError(
            "allow_short=True is incompatible with a CASH account: short-entry sells are denied "
            "wholesale, stranding stale long positions. Use --account-type MARGIN for a "
            "long-short book, or --no-allow-short (the default) for long-flat."
        )
    account_type = AccountType.MARGIN if account_kind == "MARGIN" else AccountType.CASH
    return run_backtest(
        instrument,
        feed,
        strategy,
        starting_cash=spec.starting_cash,
        account_type=account_type,
        leverage=spec.max_leverage,
        fee_bps=spec.fee_bps,
    )


def walk_forward_oos_for_spec(
    equity_curve: Sequence[tuple[datetime, float]], spec: RunSpec
) -> OOSResult:
    """``walk_forward_oos`` driven by a ``RunSpec`` (shared by the real run and synthetic paths)."""
    return walk_forward_oos(
        equity_curve,
        train_size=spec.train_size,
        test_size=spec.test_size,
        embargo=spec.embargo,
        anchored=spec.anchored,
        periods_per_year=spec.periods_per_year,
        min_train=spec.min_train,
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
