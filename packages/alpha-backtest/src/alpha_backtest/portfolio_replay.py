"""Deterministic synchronized long-only target-weight replay.

The existing Nautilus harness is intentionally single-instrument.  Running one engine per symbol
would give every leg an independent cash account and would therefore not reconcile a rotating
cross-sectional book.  This ALPHA-owned execution seam keeps one cash ledger, marks every symbol
on the same sessions, decides target quantities from close ``t`` only, and fills those fixed
orders at the open of ``t+1`` with declared fees and side-aware slippage.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from alpha_backtest.results import BacktestResult, FillTrace, OrderTrace, Trade
from alpha_core import Bar, DataError, DecisionTrace, IndicatorTrace

_CLOSE_OFFSET = timedelta(hours=23)
_EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class WeightTarget:
    """One symbol's causal score and target weight for a synchronized execution session."""

    symbol: str
    origin_ts: datetime
    available_at: datetime
    target_ts: datetime
    target_weight: float
    score: float
    fold: int


@dataclass(frozen=True, slots=True)
class ReplayPeriod:
    """One scored open-to-open OOS holding period."""

    fold: int
    target_ts: datetime
    exit_ts: datetime
    gross_return: float
    net_return: float
    benchmark_return: float
    excess_return: float
    turnover: float
    fees: float
    slippage_cost: float


@dataclass(frozen=True, slots=True)
class PortfolioReplayResult:
    """Canonical engine ledger plus per-period ML validation handoff values."""

    backtest: BacktestResult
    periods: tuple[ReplayPeriod, ...]

    def reconciled_order_fills(self) -> tuple[tuple[OrderTrace, FillTrace], ...]:
        """Return every fill paired with its exact run-local parent order."""
        orders = {order.sequence_id: order for order in self.backtest.order_trace}
        return tuple((orders[fill.order_sequence_id], fill) for fill in self.backtest.fill_trace)


@dataclass(frozen=True, slots=True)
class _ScheduledOrder:
    sequence_id: int
    decision_ts: datetime
    instrument_id: str
    symbol: str
    side: str
    quantity: float


def _finite(value: float, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise DataError(f"{label} must be finite")
    return result


def _validated_panel(
    bars_by_symbol: Mapping[str, Sequence[Bar]],
) -> tuple[tuple[str, ...], list[datetime]]:
    symbols = tuple(sorted(bars_by_symbol))
    if len(symbols) < 2:
        raise DataError(f"multi-asset replay requires >= 2 symbols, got {len(symbols)}")
    reference: list[datetime] | None = None
    for symbol in symbols:
        bars = list(bars_by_symbol[symbol])
        if len(bars) < 3:
            raise DataError(f"multi-asset replay needs >= 3 bars for {symbol!r}")
        if any(bar.symbol != symbol for bar in bars):
            raise DataError(f"bar symbol mismatch in replay panel for {symbol!r}")
        sessions = [bar.ts for bar in bars]
        if any(left >= right for left, right in zip(sessions, sessions[1:], strict=False)):
            raise DataError(f"replay sessions must be strictly increasing for {symbol!r}")
        if any(
            (right - left).total_seconds() < 24 * 3600
            for left, right in zip(sessions, sessions[1:], strict=False)
        ):
            raise DataError("multi-asset replay supports daily sessions only")
        if reference is None:
            reference = sessions
        elif sessions != reference:
            raise DataError("multi-asset replay requires a fully aligned session rectangle")
    assert reference is not None
    return symbols, reference


def _validated_targets(
    targets: Sequence[WeightTarget],
    *,
    symbols: tuple[str, ...],
    sessions: list[datetime],
) -> tuple[dict[datetime, tuple[WeightTarget, ...]], dict[datetime, tuple[WeightTarget, ...]]]:
    if not targets:
        raise DataError("multi-asset replay requires at least one target cross-section")
    session_index = {session: index for index, session in enumerate(sessions)}
    grouped: dict[datetime, list[WeightTarget]] = {}
    seen: set[tuple[datetime, str]] = set()
    for target in targets:
        key = (target.target_ts, target.symbol)
        if key in seen:
            raise DataError(f"duplicate replay target for {target.symbol!r} at {target.target_ts}")
        seen.add(key)
        if target.symbol not in symbols:
            raise DataError(f"replay target symbol {target.symbol!r} is outside the panel")
        _finite(target.score, "replay score")
        weight = _finite(target.target_weight, "target_weight")
        if not 0.0 <= weight <= 1.0:
            raise DataError(f"target_weight must be in [0, 1], got {weight}")
        if target.fold < 0:
            raise DataError(f"fold must be >= 0, got {target.fold}")
        grouped.setdefault(target.target_ts, []).append(target)

    by_target: dict[datetime, tuple[WeightTarget, ...]] = {}
    by_origin: dict[datetime, tuple[WeightTarget, ...]] = {}
    expected_symbols = set(symbols)
    for execution_ts, raw_group in grouped.items():
        group = tuple(sorted(raw_group, key=lambda row: row.symbol))
        if {row.symbol for row in group} != expected_symbols:
            raise DataError(f"target {execution_ts} must contain the complete universe")
        origins = {row.origin_ts for row in group}
        folds = {row.fold for row in group}
        if len(origins) != 1 or len(folds) != 1:
            raise DataError("each target cross-section must share one origin and fold")
        origin = next(iter(origins))
        origin_index = session_index.get(origin)
        target_index = session_index.get(execution_ts)
        if origin_index is None or target_index != origin_index + 1:
            raise DataError("target execution must be the aligned session after its origin")
        if target_index + 1 >= len(sessions):
            raise DataError("each replay target needs a following open for its OOS return")
        decision_ts = origin + _CLOSE_OFFSET
        if any(row.available_at != decision_ts for row in group):
            raise DataError("prediction available_at must equal its canonical decision close")
        if not math.isclose(
            sum(row.target_weight for row in group), 1.0, rel_tol=0.0, abs_tol=1e-12
        ):
            raise DataError("each target cross-section must sum to one")
        if origin in by_origin:
            raise DataError(f"multiple replay cross-sections share origin {origin}")
        by_target[execution_ts] = group
        by_origin[origin] = group
    return by_target, by_origin


def run_weight_replay(
    bars_by_symbol: Mapping[str, Sequence[Bar]],
    targets: Sequence[WeightTarget],
    *,
    starting_cash: float = 1_000_000.0,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> PortfolioReplayResult:
    """Replay synchronized long-only target weights with one causal cash/position ledger.

    Target quantities are fixed at the decision close from then-known closes and net liquidation.
    The next open only determines execution price.  Sells execute before buys; if an overnight gap
    plus costs makes the desired buys exceed cash, all buys are scaled pro-rata and their orders
    are marked ``PARTIALLY_FILLED`` rather than borrowing or silently dropping a symbol.
    """
    cash = _finite(starting_cash, "starting_cash")
    fee_rate = _finite(fee_bps, "fee_bps") / 10_000.0
    slippage_rate = _finite(slippage_bps, "slippage_bps") / 10_000.0
    if cash <= 0.0:
        raise DataError(f"starting_cash must be > 0, got {cash}")
    if not 0.0 <= fee_rate < 1.0 or not 0.0 <= slippage_rate < 1.0:
        raise DataError("fee_bps and slippage_bps must each be in [0, 10000)")

    symbols, sessions = _validated_panel(bars_by_symbol)
    by_target, by_origin = _validated_targets(targets, symbols=symbols, sessions=sessions)
    bars = {symbol: {bar.ts: bar for bar in bars_by_symbol[symbol]} for symbol in symbols}
    positions = dict.fromkeys(symbols, 0.0)
    average_entry = dict.fromkeys(symbols, 0.0)
    entry_times: dict[str, datetime | None] = dict.fromkeys(symbols)
    scheduled: dict[datetime, list[_ScheduledOrder]] = {}
    decisions: list[DecisionTrace] = []
    indicators: list[IndicatorTrace] = []
    orders: list[OrderTrace] = []
    fills: list[FillTrace] = []
    trades: list[Trade] = []
    next_order_id = 1
    next_fill_id = 1

    target_sessions = sorted(by_target)
    first_target = target_sessions[0]
    endpoint_for_target = {
        target: sessions[sessions.index(target) + 1] for target in target_sessions
    }
    target_for_endpoint = {endpoint: target for target, endpoint in endpoint_for_target.items()}
    entry_equity: dict[datetime, float] = {}
    endpoint_equity: dict[datetime, float] = {}
    period_fees = dict.fromkeys(target_sessions, 0.0)
    period_slippage = dict.fromkeys(target_sessions, 0.0)
    period_notional = dict.fromkeys(target_sessions, 0.0)
    baseline: tuple[datetime, float] | None = None

    first_origin_index = sessions.index(next(iter(by_target[first_target])).origin_ts)
    final_endpoint_index = sessions.index(endpoint_for_target[target_sessions[-1]])
    relevant_sessions = sessions[first_origin_index : final_endpoint_index + 1]

    def marked_equity(when: datetime, field: str) -> float:
        value = cash + sum(
            positions[symbol] * float(getattr(bars[symbol][when], field)) for symbol in symbols
        )
        if not math.isfinite(value) or value <= 0.0:
            raise DataError(f"replay net liquidation became non-positive at {when}: {value}")
        return value

    for session in relevant_sessions:
        open_equity = marked_equity(session, "open")
        if session == first_target:
            baseline = (session, open_equity)
        if session in by_target:
            entry_equity[session] = open_equity
        ending_target = target_for_endpoint.get(session)
        if ending_target is not None:
            endpoint_equity[ending_target] = open_equity

        pending = scheduled.pop(session, [])
        attribution = session if session in by_target else ending_target
        sells = [order for order in pending if order.side == "SELL"]
        buys = [order for order in pending if order.side == "BUY"]

        def record_fill(
            order: _ScheduledOrder,
            quantity: float,
            price: float,
            *,
            when: datetime = session,
            cost_target: datetime | None = attribution,
        ) -> None:
            nonlocal cash, next_fill_id
            raw_open = bars[order.symbol][when].open
            notional = quantity * price
            fee = notional * fee_rate
            if order.side == "SELL":
                cash += notional - fee
                previous_qty = positions[order.symbol]
                if quantity > previous_qty + _EPSILON:
                    raise DataError(f"long-only replay attempted to short {order.symbol}")
                closed = min(quantity, previous_qty)
                if closed > _EPSILON:
                    entry = entry_times[order.symbol]
                    if entry is None:
                        raise DataError(f"missing entry provenance for {order.symbol}")
                    entry_price = average_entry[order.symbol]
                    trades.append(
                        Trade(
                            instrument_id=order.instrument_id,
                            side="BUY",
                            quantity=closed,
                            entry_price=entry_price,
                            exit_price=price,
                            entry_ts=entry,
                            exit_ts=when,
                            realized_pnl=(price - entry_price) * closed,
                            realized_return=price / entry_price - 1.0,
                        )
                    )
                positions[order.symbol] = max(0.0, previous_qty - quantity)
                if positions[order.symbol] <= _EPSILON:
                    positions[order.symbol] = 0.0
                    average_entry[order.symbol] = 0.0
                    entry_times[order.symbol] = None
            else:
                cash -= notional + fee
                previous_qty = positions[order.symbol]
                new_qty = previous_qty + quantity
                average_entry[order.symbol] = (
                    previous_qty * average_entry[order.symbol] + quantity * price
                ) / new_qty
                positions[order.symbol] = new_qty
                if previous_qty <= _EPSILON:
                    entry_times[order.symbol] = when
            if cost_target is not None:
                period_fees[cost_target] += fee
                period_slippage[cost_target] += quantity * abs(price - raw_open)
                period_notional[cost_target] += quantity * raw_open
            fills.append(
                FillTrace(
                    sequence_id=next_fill_id,
                    order_sequence_id=order.sequence_id,
                    ts=when,
                    instrument_id=order.instrument_id,
                    side=order.side,
                    quantity=quantity,
                    price=price,
                )
            )
            next_fill_id += 1

        for order in sorted(sells, key=lambda item: item.symbol):
            fill_price = bars[order.symbol][session].open * (1.0 - slippage_rate)
            quantity = min(order.quantity, positions[order.symbol])
            if quantity > _EPSILON:
                record_fill(order, quantity, fill_price)
            orders.append(
                OrderTrace(
                    sequence_id=order.sequence_id,
                    ts=order.decision_ts + timedelta(microseconds=1),
                    instrument_id=order.instrument_id,
                    side=order.side,
                    quantity=order.quantity,
                    filled_quantity=quantity,
                    status=(
                        "FILLED" if quantity + _EPSILON >= order.quantity else "PARTIALLY_FILLED"
                    ),
                )
            )

        buy_requirements = [
            order.quantity
            * bars[order.symbol][session].open
            * (1.0 + slippage_rate)
            * (1.0 + fee_rate)
            for order in buys
        ]
        required_cash = sum(buy_requirements)
        buy_scale = min(1.0, max(0.0, cash) / required_cash) if required_cash > 0.0 else 1.0
        for order in sorted(buys, key=lambda item: item.symbol):
            quantity = order.quantity * buy_scale
            fill_price = bars[order.symbol][session].open * (1.0 + slippage_rate)
            if quantity > _EPSILON:
                record_fill(order, quantity, fill_price)
            status = (
                "REJECTED"
                if quantity <= _EPSILON
                else "FILLED"
                if quantity + _EPSILON >= order.quantity
                else "PARTIALLY_FILLED"
            )
            orders.append(
                OrderTrace(
                    sequence_id=order.sequence_id,
                    ts=order.decision_ts + timedelta(microseconds=1),
                    instrument_id=order.instrument_id,
                    side=order.side,
                    quantity=order.quantity,
                    filled_quantity=quantity,
                    status=status,
                )
            )
        if abs(cash) <= 1e-8:
            cash = 0.0

        if ending_target is not None and session not in by_target:
            endpoint_equity[ending_target] = marked_equity(session, "open")

        group = by_origin.get(session)
        if group is not None:
            desired = {row.symbol: row.target_weight for row in group}
            score = {row.symbol: row.score for row in group}
            reason = "ml_oos_top_quintile"
        elif session in by_target:
            desired = dict.fromkeys(symbols, 0.0)
            score = {}
            reason = "ml_oos_horizon_flatten"
        else:
            continue

        close_equity = marked_equity(session, "close")
        decision_ts = session + _CLOSE_OFFSET
        execution_ts = sessions[sessions.index(session) + 1]
        next_orders: list[_ScheduledOrder] = []
        for symbol in symbols:
            target_quantity = desired[symbol] * close_equity / bars[symbol][session].close
            decisions.append(
                DecisionTrace(
                    ts=decision_ts,
                    instrument_id=f"{symbol}.SIM",
                    signal=1 if desired[symbol] > 0.0 else 0,
                    target_quantity=target_quantity,
                    reason=reason,
                )
            )
            indicators.append(
                IndicatorTrace(
                    ts=decision_ts,
                    instrument_id=f"{symbol}.SIM",
                    name="target_weight",
                    value=desired[symbol],
                    unit="fraction",
                )
            )
            if symbol in score:
                indicators.append(
                    IndicatorTrace(
                        ts=decision_ts,
                        instrument_id=f"{symbol}.SIM",
                        name="ml_score",
                        value=score[symbol],
                        unit="score",
                    )
                )
            delta = target_quantity - positions[symbol]
            if abs(delta) <= _EPSILON:
                continue
            next_orders.append(
                _ScheduledOrder(
                    sequence_id=next_order_id,
                    decision_ts=decision_ts,
                    instrument_id=f"{symbol}.SIM",
                    symbol=symbol,
                    side="BUY" if delta > 0.0 else "SELL",
                    quantity=abs(delta),
                )
            )
            next_order_id += 1
        scheduled[execution_ts] = next_orders

    if scheduled:
        raise DataError("replay ended with unexecuted scheduled orders")
    if any(quantity > _EPSILON for quantity in positions.values()):
        raise DataError("replay ended with a non-flat position after its fixed OOS horizon")
    if baseline is None or set(endpoint_equity) != set(target_sessions):
        raise DataError("replay failed to reconcile every target to one following-open endpoint")

    equity_curve = [baseline]
    periods: list[ReplayPeriod] = []
    previous_equity = float(baseline[1])
    for target_ts in target_sessions:
        exit_ts = endpoint_for_target[target_ts]
        equity = endpoint_equity[target_ts]
        equity_curve.append((exit_ts, equity))
        group = by_target[target_ts]
        gross_return = sum(
            row.target_weight
            * (bars[row.symbol][exit_ts].open / bars[row.symbol][target_ts].open - 1.0)
            for row in group
        )
        benchmark_return = sum(
            bars[symbol][exit_ts].open / bars[symbol][target_ts].open - 1.0 for symbol in symbols
        ) / len(symbols)
        net_return = equity / previous_equity - 1.0
        periods.append(
            ReplayPeriod(
                fold=group[0].fold,
                target_ts=target_ts,
                exit_ts=exit_ts,
                gross_return=gross_return,
                net_return=net_return,
                benchmark_return=benchmark_return,
                excess_return=net_return - benchmark_return,
                turnover=period_notional[target_ts] / entry_equity[target_ts],
                fees=period_fees[target_ts],
                slippage_cost=period_slippage[target_ts],
            )
        )
        previous_equity = equity

    order_trace = tuple(sorted(orders, key=lambda item: item.sequence_id))
    fill_trace = tuple(sorted(fills, key=lambda item: item.sequence_id))
    return PortfolioReplayResult(
        backtest=BacktestResult(
            orders=len(order_trace),
            fills=len(fill_trace),
            trades=trades,
            equity_curve=[(ts, value) for ts, value in equity_curve],
            rejected=sum(order.status == "REJECTED" for order in order_trace),
            decision_trace=tuple(decisions),
            indicator_trace=tuple(indicators),
            order_trace=order_trace,
            fill_trace=fill_trace,
        ),
        periods=tuple(periods),
    )
