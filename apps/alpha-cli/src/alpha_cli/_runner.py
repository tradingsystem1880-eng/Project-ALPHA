"""Engine ↔ gauntlet orchestration helpers for the validation CLI.

The CLI is the only layer the import DAG lets touch both the backtest engine and the validation
gauntlet, so the glue lives here. This module currently owns the deterministic run id and the
walk-forward OOS stitch; the engine-running helpers (``load_bars``, ``run_full_backtest``) are added
with the backtest command.

Walk-forward for a *fixed-parameter* strategy is out-of-sample evaluation, not refitting. Fold
geometry is derived from the immutable session calendar, historical bars causally prime indicators
without creating orders or positions, and a fresh portfolio executes across the contiguous scored
test window. The resulting OOS metrics and chart evidence therefore describe the same state.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from alpha_cli._identity import RunIdentity, execution_fingerprint, strategy_fingerprint
from alpha_core import Bar, CorporateAction, DataError
from alpha_data.snapshot import snapshot_manifest_hash
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
    # opt-in risk controls (defaults preserve fixed-capital, no-halt behavior; the gauntlet and
    # optimizer reject them because the Tier-1 surrogate cannot model equity-path-dependent sizing)
    size_on_equity: bool = False
    halt_drawdown: float | None = None
    # kronos only: the content-addressed signal-cache key (data_dir/forecasts/<key>), set by
    # the CLI's auto-precompute. A KEY, never a path, so run ids stay machine-independent.
    # Adding this field shifted run ids for all runs created after it landed (no pinned ids).
    forecast_cache: str | None = None

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


def parse_strategy_params(
    strategy_name: str, items: Sequence[str] | None
) -> tuple[tuple[str, float], ...]:
    """Parse repeatable ``name=value`` CLI options into the spec's sorted ``strategy_params`` shape.

    Sorted by name so the same params in any CLI order produce the same ``RunSpec`` (and run id).
    Fails loud (``DataError``) on a malformed item or a non-numeric value.
    """
    from alpha_cli._schemas import normalize_params

    parsed: list[tuple[str, float]] = []
    for item in items or ():
        if "=" not in item:
            raise DataError(f"strategy param must be name=value, got {item!r}")
        name, _, raw = item.partition("=")
        name = name.strip()
        if not name:
            raise DataError(f"strategy param has empty name: {item!r}")
        try:
            parsed.append((name, float(raw)))
        except ValueError:
            raise DataError(f"strategy param {name!r} must be numeric, got {raw!r}") from None
    return normalize_params(strategy_name, tuple(parsed))


def parse_as_of(value: str | None) -> datetime | None:
    """Parse an optional canonical daily research cutoff as an inclusive UTC instant."""
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DataError(f"as_of must be canonical YYYY-MM-DD, got {value!r}") from exc
    if parsed.isoformat() != value:
        raise DataError(f"as_of must be canonical YYYY-MM-DD, got {value!r}")
    return datetime.combine(parsed, time(23, 59, 59), tzinfo=UTC)


def load_bars(
    symbol: str,
    *,
    data_dir: Path,
    snapshot_id: str | None = None,
    as_of: datetime | None = None,
) -> tuple[list[Bar], str | None]:
    """Load the point-in-time history for ``symbol`` — live store or a frozen snapshot.

    Reads through ``PointInTimeSource`` — the same look-ahead-safe seam strategies use. ``as_of``
    is the knowledge cutoff: bars after it are excluded and only corporate actions known by it are
    applied (defaults to a far future so the whole series is returned, actions applied). Backtests
    use the default; ``alpha data candles`` passes an ``--end`` so a chart can never show a bar past
    its window nor a split not yet known at the cutoff. With a ``snapshot_id`` the read is rooted at
    ``data_dir/snapshots/<id>`` (integrity-verified first), so the manifest's provenance claim is
    what the run actually consumed — the live store is wholesale-replaced by pulls and cannot back a
    reproducibility claim. Fails loud (``DataError``) on a missing/tampered snapshot or < 2 bars.
    """
    from alpha_data.snapshot import resolve_snapshot_dir, verify_snapshot
    from alpha_data.source import PointInTimeSource
    from alpha_data.store import ParquetStore

    if snapshot_id is not None:
        snap_dir = resolve_snapshot_dir(data_dir / "snapshots", snapshot_id)
        verify_snapshot(snap_dir)  # re-hash against the manifest before trusting the bytes
        store = ParquetStore(snap_dir)
    else:
        store = ParquetStore(data_dir / "store")
    source = PointInTimeSource(store, {symbol: store.read_actions(symbol)})
    when = as_of if as_of is not None else datetime(2999, 1, 1, tzinfo=UTC)
    bars = source.as_of(symbol, when)
    if len(bars) < 2:
        raise DataError(f"need >= 2 bars for {symbol!r} as of {when.date()}, got {len(bars)}")
    return bars, snapshot_id


def load_dividends(
    symbol: str,
    *,
    data_dir: Path,
    snapshot_id: str | None = None,
    as_of: datetime | None = None,
) -> list[CorporateAction]:
    """The symbol's knowledge-complete DIVIDEND actions from the store (or a frozen snapshot).

    Same store-selection rules as :func:`load_bars` (a snapshot read is integrity-verified);
    returns ``[]`` for symbols with no stored actions (crypto, stooq). The engine credits these
    at pay date against the pre-ex holding — decoupled from prices (spec §6.1.4).
    """
    from alpha_data.snapshot import resolve_snapshot_dir, verify_snapshot
    from alpha_data.source import PointInTimeSource
    from alpha_data.store import ParquetStore

    if snapshot_id is not None:
        snap_dir = resolve_snapshot_dir(data_dir / "snapshots", snapshot_id)
        verify_snapshot(snap_dir)
        store = ParquetStore(snap_dir)
    else:
        store = ParquetStore(data_dir / "store")
    source = PointInTimeSource(store, {symbol: store.read_actions(symbol)})
    when = as_of if as_of is not None else datetime(2999, 1, 1, tzinfo=UTC)
    return source.dividends_as_of(symbol, when)


def run_full_backtest(
    bars: Sequence[Bar],
    spec: RunSpec,
    *,
    dividends: Sequence[CorporateAction] = (),
    warmup_bars: Sequence[Bar] = (),
) -> BacktestResult:
    """Run ``spec``'s fixed-parameter strategy over ``bars`` once, net of costs.

    The single source of truth for both ``alpha backtest run`` and the validation gauntlet (and
    every synthetic Tier-2 path). The concrete strategy is resolved through the registry
    (``_strategies``); engine imports are lazy so the pure helpers above stay importable without
    dragging in nautilus.
    """
    from nautilus_trader.model.enums import AccountType

    from alpha_backtest.engine import run_backtest
    from alpha_backtest.feed import daily_bar_type, to_execution_feed
    from alpha_backtest.instruments import instrument_for
    from alpha_cli import _strategies

    symbol = bars[0].symbol
    instrument = instrument_for(symbol)  # slash pairs -> 5-decimal crypto, else equity
    bar_type = daily_bar_type(symbol)
    feed = to_execution_feed(
        bars,
        bar_type,
        price_precision=instrument.price_precision,  # sub-dollar tokens need the finer ticks
        slippage_bps=spec.slippage_bps,
    )
    strategy = _strategies.build_strategy(spec, instrument.id, bar_type)
    if warmup_bars:
        if warmup_bars[-1].ts >= bars[0].ts:
            raise DataError("warmup bars must end before the first executable bar")
        prime_history = getattr(strategy, "prime_history", None)
        if not callable(prime_history):
            raise DataError(
                f"strategy {spec.strategy_name!r} does not support causal history priming"
            )
        # Priming updates trailing indicators and deterministic rebalance cadence only.  It runs
        # before the strategy is attached to the engine, so no historical target, order, fill, or
        # position can cross the scored execution boundary.
        prime_history(warmup_bars)
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
    if account_kind == "CASH" and "/" in symbol:
        raise DataError(
            f"crypto pair {symbol!r} needs --account-type MARGIN: the SIM venue cannot hold a "
            "currency pair in a single-currency CASH account."
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
        dividends=dividends,
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


def _normalized_curve(
    rows: Sequence[tuple[datetime, float]], *, label: str
) -> list[tuple[datetime, float]]:
    if len(rows) < 2:
        raise DataError(f"{label} contains fewer than two scored sessions")
    first = float(rows[0][1])
    if not math.isfinite(first) or first <= 0.0:
        raise DataError(f"{label} begins with invalid equity {first!r}")
    return [(ts, float(value) / first) for ts, value in rows]


def _scope_execution(
    result: BacktestResult,
    *,
    equity: Sequence[tuple[datetime, float]],
    execution_dates: set[date],
    decision_dates: set[date],
) -> BacktestResult:
    """Keep only evidence which can affect the explicitly scored execution sessions."""
    orders = [row for row in result.order_trace if row.ts.date() in execution_dates]
    order_ids = {row.sequence_id: index for index, row in enumerate(orders, start=1)}
    scoped_orders = tuple(
        dataclasses.replace(row, sequence_id=order_ids[row.sequence_id]) for row in orders
    )
    scoped_fills = tuple(
        dataclasses.replace(
            row,
            sequence_id=index,
            order_sequence_id=order_ids[row.order_sequence_id],
        )
        for index, row in enumerate(
            (fill for fill in result.fill_trace if fill.order_sequence_id in order_ids),
            start=1,
        )
    )
    trades = [
        trade
        for trade in result.trades
        if trade.entry_ts.date() in execution_dates and trade.exit_ts.date() in execution_dates
    ]
    benchmark = [row for row in result.benchmark_curve if row[0].date() in execution_dates]
    if benchmark:
        baseline = benchmark[0][1]
        benchmark = [(ts, value / baseline) for ts, value in benchmark]
    return dataclasses.replace(
        result,
        orders=len(scoped_orders),
        fills=len(scoped_fills),
        rejected=sum(row.status.upper() == "REJECTED" for row in scoped_orders),
        trades=trades,
        equity_curve=list(equity),
        decision_trace=tuple(
            row for row in result.decision_trace if row.ts.date() in decision_dates
        ),
        indicator_trace=tuple(
            row for row in result.indicator_trace if row.ts.date() in decision_dates
        ),
        chart_annotations=tuple(
            row for row in result.chart_annotations if row.decision_ts.date() in decision_dates
        ),
        order_trace=scoped_orders,
        fill_trace=scoped_fills,
        portfolio_state_trace=tuple(
            row for row in result.portfolio_state_trace if row.ts.date() in execution_dates
        ),
        benchmark_curve=tuple(benchmark),
    )


def fresh_scored_execution(
    bars: Sequence[Bar],
    spec: RunSpec,
    *,
    first_scored_index: int,
    final_scored_index: int,
    dividends: Sequence[CorporateAction] = (),
    normalize_equity: bool,
) -> BacktestResult:
    """Prime causal history, then execute a fresh portfolio over one contiguous scored window.

    ``first_scored_index`` is the baseline equity session and ``final_scored_index`` is the final
    realized-equity session, both inclusive.  The immediately preceding close is executed only to
    originate a possible first-session fill; it is never itself scored or published as equity.
    """
    if not 0 < first_scored_index <= final_scored_index < len(bars):
        raise DataError("scored execution window is outside the available bar history")
    decision_index = first_scored_index - 1
    executable = bars[decision_index : final_scored_index + 1]
    fresh = run_full_backtest(
        executable,
        spec,
        dividends=dividends,
        warmup_bars=bars[:decision_index],
    )
    execution_dates = {bar.ts.date() for bar in bars[first_scored_index : final_scored_index + 1]}
    decision_dates = {bar.ts.date() for bar in bars[decision_index:final_scored_index]}
    raw_equity = [row for row in fresh.equity_curve if row[0].date() in execution_dates]
    if len(raw_equity) < 2:
        raise DataError("scored execution contains fewer than two sessions")
    equity = (
        _normalized_curve(raw_equity, label="scored execution") if normalize_equity else raw_equity
    )
    return _scope_execution(
        fresh,
        equity=equity,
        execution_dates=execution_dates,
        decision_dates=decision_dates,
    )


def _recalculate_fold_metrics(
    folds: Sequence[FoldSummary], returns: FloatArray, *, periods_per_year: int
) -> tuple[FoldSummary, ...]:
    """Recompute every fold verdict from the fresh-state OOS stream actually published."""
    rows: list[FoldSummary] = []
    offset = 0
    for fold in folds:
        values = returns[offset : offset + fold.n_test]
        if values.size != fold.n_test:
            raise DataError("fresh OOS stream does not reconcile to declared fold lengths")
        oos_return, oos_sharpe, oos_cagr = _fold_metrics(values, periods_per_year)
        rows.append(
            dataclasses.replace(
                fold,
                oos_return=oos_return,
                oos_sharpe=oos_sharpe,
                oos_cagr=oos_cagr,
            )
        )
        offset += fold.n_test
    if offset != returns.size:
        raise DataError("fresh OOS stream contains sessions outside declared folds")
    return tuple(rows)


def fresh_oos_execution(
    bars: Sequence[Bar],
    spec: RunSpec,
    *,
    dividends: Sequence[CorporateAction] = (),
) -> tuple[OOSResult, BacktestResult]:
    """Evaluate fixed rules OOS from a fresh portfolio and return matching causal evidence.

    Fold geometry depends only on the observed session calendar, not on discovery-run positions.
    A constant dummy curve therefore establishes the canonical windows without executing the
    strategy over discovery data.  The strategy is then history-primed without an engine and run
    exactly once from the prior close through the contiguous OOS sessions.  Reported metrics and
    every returned trace row consequently describe the same execution state.
    """
    layout = walk_forward_oos_for_spec([(bar.ts, 1.0) for bar in bars], spec)
    first_scored_index = layout.folds[0].test_start
    final_scored_index = layout.folds[-1].test_end
    result = fresh_scored_execution(
        bars,
        spec,
        first_scored_index=first_scored_index,
        final_scored_index=final_scored_index,
        dividends=dividends,
        normalize_equity=True,
    )
    values = np.asarray([value for _, value in result.equity_curve], dtype=np.float64)
    returns = to_returns(values)
    folds = _recalculate_fold_metrics(
        layout.folds,
        returns,
        periods_per_year=spec.periods_per_year,
    )
    return (
        OOSResult(
            oos_returns=returns,
            oos_equity=values,
            oos_timestamps=[ts for ts, _ in result.equity_curve],
            folds=folds,
        ),
        result,
    )


def fold_manifest(fold: FoldSummary, bars: Sequence[Bar]) -> dict[str, object]:
    """Project one OOS fold with explicit causal/session timestamps for chart attribution."""
    return {
        **dataclasses.asdict(fold),
        "train_start_ts": bars[fold.train_start].ts.isoformat(),
        "train_end_ts": bars[fold.train_end].ts.isoformat(),
        "test_decision_start_ts": bars[fold.test_start - 1].ts.isoformat(),
        "test_start_ts": bars[fold.test_start].ts.isoformat(),
        "test_end_ts": bars[fold.test_end].ts.isoformat(),
    }


@dataclass(frozen=True)
class OOSResult:
    """Stitched out-of-sample returns/equity (aligned timestamps) plus per-fold summaries."""

    oos_returns: FloatArray  # length N
    oos_equity: FloatArray  # length N+1, leading 1.0
    oos_timestamps: list[datetime]  # length N+1, one per equity point
    folds: tuple[FoldSummary, ...]


def source_fingerprint(bars: Sequence[Bar], *, dividends: Sequence[CorporateAction] = ()) -> str:
    """Hash the exact observed market-data content consumed by a run.

    The canonical JSON representation is independent of filesystem paths, Parquet encodings, and
    caller insertion order. This prevents mutable live-store revisions from targeting an existing
    immutable run directory while keeping equivalent snapshots/content on the same identity.
    """
    bar_rows = sorted(
        (
            bar.symbol,
            bar.ts.isoformat(),
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
        )
        for bar in bars
    )
    action_rows = sorted(
        (
            action.symbol,
            action.action_type.value,
            action.ex_date.isoformat(),
            action.announce_date.isoformat() if action.announce_date is not None else None,
            action.record_date.isoformat() if action.record_date is not None else None,
            action.pay_date.isoformat() if action.pay_date is not None else None,
            action.ratio,
            action.amount,
        )
        for action in dividends
    )
    canonical = json.dumps(
        {"bars": bar_rows, "dividends": action_rows},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(
        b"project-alpha-observed-market-data-v1\0" + canonical.encode("utf-8")
    ).hexdigest()


def combine_source_fingerprints(sources: Mapping[str, str]) -> str:
    """Combine named source digests into one order-independent multi-source digest."""
    for name, fingerprint in sources.items():
        if not name or len(fingerprint) != 64:
            raise DataError(f"invalid source fingerprint for {name!r}")
        try:
            int(fingerprint, 16)
        except ValueError:
            raise DataError(f"invalid source fingerprint for {name!r}") from None
    canonical = json.dumps(dict(sorted(sources.items())), separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(
        b"project-alpha-combined-observed-sources-v1\0" + canonical.encode("utf-8")
    ).hexdigest()


def numeric_source_fingerprint(values: Sequence[float], *, domain: str) -> str:
    """Hash an observed numeric source stream when its upstream artifact is the source contract."""
    canonical = json.dumps(list(values), separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(
        b"project-alpha-observed-numeric-source-v1\0"
        + domain.encode("utf-8")
        + b"\0"
        + canonical.encode("utf-8")
    ).hexdigest()


def run_identity_for(
    payload: Mapping[str, object],
    *,
    source_fingerprint: str | None = None,
    snapshot_hash: str | None = None,
) -> RunIdentity:
    """Build versioned identity including code, strategy, and observed source content."""
    from alpha_cli._identity import RUN_IDENTITY_VERSION, strategy_name_from_payload

    execution = execution_fingerprint()
    strategy = strategy_fingerprint(strategy_name_from_payload(payload))
    source = (
        source_fingerprint or hashlib.sha256(b"project-alpha-no-observed-source-v1").hexdigest()
    )
    payload_snapshot_hash = payload.get("snapshot_hash")
    if snapshot_hash is None and isinstance(payload_snapshot_hash, str):
        snapshot_hash = payload_snapshot_hash
    if snapshot_hash is not None:
        if len(snapshot_hash) != 64:
            raise DataError("snapshot_hash must be a 64-hex SHA-256 digest")
        try:
            int(snapshot_hash, 16)
        except ValueError:
            raise DataError("snapshot_hash must be a 64-hex SHA-256 digest") from None
    from alpha_cli.run_context import run_context_from_environment

    identity_payload = {
        "run_identity_version": RUN_IDENTITY_VERSION,
        "execution_fingerprint": execution,
        "strategy_fingerprint": strategy,
        "source_fingerprint": source,
        "snapshot_hash": snapshot_hash,
        "payload": payload,
    }
    run_context = run_context_from_environment()
    if run_context is not None:
        identity_payload["run_context"] = run_context
    canonical = json.dumps(
        identity_payload, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
    )
    return RunIdentity(
        run_id=hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
        execution_fingerprint=execution,
        strategy_fingerprint=strategy,
        source_fingerprint=source,
        snapshot_hash=snapshot_hash,
    )


def run_id_for(
    payload: Mapping[str, object],
    *,
    source_fingerprint: str | None = None,
    snapshot_hash: str | None = None,
) -> str:
    """A deterministic 16-hex-char id for a run, from its canonical (sorted-key) JSON payload.

    Same symbol + params + costs + seed → same id → same artifact directory → reproducible
    (spec §11.4). No wall-clock goes in, so re-running is byte-identical.
    """
    return run_identity_for(
        payload,
        source_fingerprint=source_fingerprint,
        snapshot_hash=snapshot_hash,
    ).run_id


def verified_snapshot_hash(data_dir: Path, snapshot_id: str | None) -> str | None:
    """Resolve one frozen snapshot to the exact verified manifest digest used by run identity."""
    if snapshot_id is None:
        return None
    from alpha_data.snapshot import resolve_snapshot_dir

    return snapshot_manifest_hash(resolve_snapshot_dir(data_dir / "snapshots", snapshot_id))


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
