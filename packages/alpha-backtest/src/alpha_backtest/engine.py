"""Minimal nautilus ``BacktestEngine`` run harness for the v1 daily slice.

Configured ``bar_execution=False`` so bars drive strategy *decisions* only — fills come from the
open-priced quotes produced by ``feed.to_execution_feed``, giving the spec's "decide on close of t,
fill at open of t+1" convention. Returns a ``BacktestResult`` (counts + closed-trade log +
per-session mark-to-market equity curve).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.common.actor import Actor
from nautilus_trader.config import LoggingConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Currency, Money
from nautilus_trader.trading.strategy import Strategy

from alpha_backtest.frictions import BpsFeeModel
from alpha_backtest.results import (
    BacktestResult,
    FillTrace,
    OrderTrace,
    PortfolioStateTrace,
    Trade,
)
from alpha_core import ActionType, CorporateAction, DataError

_NS_PER_SECOND = 1_000_000_000


def _ns_to_dt(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / _NS_PER_SECOND, tz=UTC)


def _sum_pnls(pnls: Any) -> float:
    """Sum a nautilus per-currency PnL dict to a float (single base currency in v1)."""
    return float(sum(money.as_double() for money in pnls.values()))


class _EquityRecorder(Actor):  # type: ignore[misc]  # nautilus Actor is untyped (Cython)
    """Snapshots net-liquidation equity once per session (on each open quote).

    ``equity = starting_cash + realized PnL + unrealized PnL + credited dividend cash`` —
    account-type-agnostic and net of commissions (nautilus realized PnL already nets fees), so an
    open position is marked to market each session rather than reporting realized cash only.

    Dividends ride the decoupled cash channel (spec §6.1.4): entitlement is the net position held
    BEFORE the ex-date session's open (this actor samples pre-fill, so the position it reads at
    the first session at/after ``ex_date`` is exactly the pre-ex holding); the cash lands in the
    curve from the first session at/after ``pay_date`` (``ex_date`` when the vendor gave no pay
    date). A short position is debited. A ``pay_date`` beyond the last session never credits —
    the backtest window simply ends before the cash arrives.
    """

    def __init__(
        self,
        instrument_id: InstrumentId,
        venue: Venue,
        starting_cash: float,
        dividends: Sequence[CorporateAction] = (),
    ) -> None:
        super().__init__()
        self._iid = instrument_id
        self._venue = venue
        self._starting_cash = starting_cash
        for div in dividends:
            if div.action_type is not ActionType.DIVIDEND or div.amount is None:
                raise DataError(
                    f"equity recorder takes DIVIDEND actions with an amount, got {div!r}"
                )
        # (ex_date, effective pay date, amount), ex-ascending; consumed front-to-front
        self._pending: list[tuple[date, date, float]] = sorted(
            (d.ex_date, d.pay_date if d.pay_date is not None else d.ex_date, float(d.amount))
            for d in dividends
            if d.amount is not None
        )
        self._payable: list[tuple[date, float]] = []  # (pay date, entitled cash)
        self.credited_cash = 0.0  # cash already landed (pay date reached)
        self.curve: list[tuple[datetime, float]] = []

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self._iid)

    def _settle_dividends(self, session: date) -> None:
        """Entitle ex-crossed dividends at the pre-fill position; land cash at/after pay."""
        while self._pending and self._pending[0][0] <= session:
            _, pay, amount = self._pending.pop(0)
            shares = float(self.portfolio.net_position(self._iid))  # pre-fill = pre-ex holding
            if shares != 0.0:
                self._payable.append((pay, amount * shares))
        still_due: list[tuple[date, float]] = []
        for pay, cash in self._payable:
            if pay <= session:
                self.credited_cash += cash
            else:
                still_due.append((pay, cash))
        self._payable = still_due

    def on_quote_tick(self, quote: QuoteTick) -> None:
        # Sampled after the portfolio has marked to this quote but BEFORE a strategy order
        # submitted on the same quote settles (the order fills after this snapshot), so a fill
        # session's fee/spread shows up from the NEXT sample; run_backtest re-samples the terminal
        # state so a final-session fill is never lost.
        ts = _ns_to_dt(quote.ts_event)
        self._settle_dividends(ts.date())
        equity = (
            self._starting_cash
            + _sum_pnls(self.portfolio.realized_pnls(self._venue))
            + _sum_pnls(self.portfolio.unrealized_pnls(self._venue))
            + self.credited_cash
        )
        self.curve.append((ts, equity))


def _closed_trades(engine: BacktestEngine) -> list[Trade]:
    trades: list[Trade] = []
    for p in engine.cache.positions_closed():
        trades.append(
            Trade(
                instrument_id=str(p.instrument_id),
                side="BUY" if p.entry == OrderSide.BUY else "SELL",
                quantity=p.peak_qty.as_double(),
                entry_price=float(p.avg_px_open),
                exit_price=float(p.avg_px_close),
                entry_ts=_ns_to_dt(p.ts_opened),
                exit_ts=_ns_to_dt(p.ts_closed),
                realized_pnl=p.realized_pnl.as_double(),
                realized_return=float(p.realized_return),
            )
        )
    return trades


def _execution_trace(
    engine: BacktestEngine,
) -> tuple[tuple[OrderTrace, ...], tuple[FillTrace, ...]]:
    """Canonicalize engine orders/fills without persisting vendor UUIDs or opaque event ids."""

    def order_key(order: Any) -> tuple[Any, ...]:
        raw: dict[str, Any] = order.to_dict()
        fill_signature = tuple(
            (
                int(event.ts_event),
                str(event.instrument_id),
                "BUY" if event.order_side == OrderSide.BUY else "SELL",
                float(event.last_qty),
                float(event.last_px),
            )
            for event in order.events
            if isinstance(event, OrderFilled)
        )
        return (
            int(order.ts_init),
            str(raw["instrument_id"]),
            str(raw["side"]),
            float(raw["quantity"]),
            float(raw["filled_qty"]),
            str(raw["status"]),
            fill_signature,
        )

    # Persisted semantics (including fill history) fully determine ordering. If two keys tie, their
    # projected rows are identical, so cache enumeration cannot change the resulting bytes. Vendor
    # and client UUIDs never participate in ordering or persistence.
    orders = sorted(engine.cache.orders(), key=order_key)
    order_trace: list[OrderTrace] = []
    pending_fills: list[tuple[int, int, int, OrderFilled]] = []
    for sequence_id, order in enumerate(orders, start=1):
        raw: dict[str, Any] = order.to_dict()
        order_trace.append(
            OrderTrace(
                sequence_id=sequence_id,
                ts=_ns_to_dt(int(order.ts_init)),
                instrument_id=str(raw["instrument_id"]),
                side=str(raw["side"]),
                quantity=float(raw["quantity"]),
                filled_quantity=float(raw["filled_qty"]),
                status=str(raw["status"]),
            )
        )
        for event_index, event in enumerate(order.events):
            if isinstance(event, OrderFilled):
                pending_fills.append((int(event.ts_event), sequence_id, event_index, event))

    fill_trace: list[FillTrace] = []
    sorted_fills = sorted(pending_fills, key=lambda item: (item[0], item[1], item[2]))
    for sequence_id, (_, order_id, _, event) in enumerate(sorted_fills, start=1):
        fill_trace.append(
            FillTrace(
                sequence_id=sequence_id,
                order_sequence_id=order_id,
                ts=_ns_to_dt(int(event.ts_event)),
                instrument_id=str(event.instrument_id),
                side="BUY" if event.order_side == OrderSide.BUY else "SELL",
                quantity=float(event.last_qty),
                price=float(event.last_px),
            )
        )
    return tuple(order_trace), tuple(fill_trace)


def _portfolio_and_benchmark_trace(
    data: Sequence[Data],
    equity_curve: Sequence[tuple[datetime, float]],
    fill_trace: Sequence[FillTrace],
) -> tuple[tuple[PortfolioStateTrace, ...], tuple[tuple[datetime, float], ...]]:
    """Derive post-fill exposure/turnover and a passive price benchmark from engine evidence."""

    quotes: list[tuple[datetime, float]] = []
    seen_timestamps: set[datetime] = set()
    for item in data:
        if not isinstance(item, QuoteTick):
            continue
        ts = _ns_to_dt(item.ts_event)
        if ts in seen_timestamps:
            raise DataError(f"duplicate opening quote timestamp in engine feed: {ts.isoformat()}")
        seen_timestamps.add(ts)
        midpoint = (float(item.bid_price) + float(item.ask_price)) / 2.0
        if midpoint <= 0.0:
            raise DataError(f"opening quote midpoint must be positive, got {midpoint}")
        quotes.append((ts, midpoint))
    if not quotes:
        return (), ()
    quotes.sort(key=lambda item: item[0])
    equity_by_ts = dict(equity_curve)
    if len(equity_by_ts) != len(equity_curve):
        raise DataError("equity curve has duplicate session timestamps")
    fills_by_ts: dict[datetime, list[FillTrace]] = {}
    for fill in fill_trace:
        fills_by_ts.setdefault(fill.ts, []).append(fill)
    quote_timestamps = {ts for ts, _ in quotes}
    unmatched = sorted(set(fills_by_ts) - quote_timestamps)
    if unmatched:
        raise DataError(
            "fill timestamps do not reconcile to opening quotes: "
            + ", ".join(ts.isoformat() for ts in unmatched)
        )
    position = 0.0
    states: list[PortfolioStateTrace] = []
    first_midpoint = quotes[0][1]
    benchmark: list[tuple[datetime, float]] = []
    for ts, midpoint in quotes:
        if ts not in equity_by_ts:
            raise DataError(f"opening quote {ts.isoformat()} has no canonical equity sample")
        equity = equity_by_ts[ts]
        if equity <= 0.0 or not math.isfinite(equity):
            raise DataError(f"portfolio analytics require positive finite equity, got {equity}")
        notional = 0.0
        for fill in sorted(fills_by_ts.get(ts, ()), key=lambda item: item.sequence_id):
            direction = 1.0 if fill.side == "BUY" else -1.0
            position += direction * fill.quantity
            notional += abs(fill.quantity * fill.price)
        signed_exposure = position * midpoint / equity
        states.append(
            PortfolioStateTrace(
                ts=ts,
                gross_exposure=abs(signed_exposure),
                net_exposure=signed_exposure,
                turnover=notional / equity,
            )
        )
        benchmark.append((ts, midpoint / first_midpoint))
    return tuple(states), tuple(benchmark)


def run_backtest(
    instrument: Instrument,
    data: Sequence[Data],
    strategy: Strategy,
    *,
    starting_cash: float = 1_000_000.0,
    currency: Currency = USD,
    account_type: AccountType = AccountType.CASH,
    leverage: float = 1.0,
    fee_bps: float = 0.0,
    dividends: Sequence[CorporateAction] = (),
) -> BacktestResult:
    """Run ``strategy`` over ``data`` for ``instrument``; return counts + trade log + equity curve.

    ``data`` should come from ``feed.to_execution_feed`` (open quotes + close-stamped decision
    bars). The venue uses a NETTING OMS with ``bar_execution=False`` so only the quotes fill orders
    — a market order decided on the close of t fills at the open of t+1. The account defaults to
    CASH (no shorting; equities are long-flat per spec §7); pass ``AccountType.MARGIN`` (where
    ``leverage`` applies) for the long-short crypto/FX path. ``dividends`` are DIVIDEND
    ``CorporateAction``s for this instrument: cash is credited to the equity curve at pay date
    against the pre-ex holding (see ``_EquityRecorder``) — decoupled from prices, per spec §6.1.4.
    """
    if fee_bps < 0.0:
        raise DataError(f"fee_bps must be >= 0 (a negative fee pays you to trade), got {fee_bps}")
    engine = BacktestEngine(
        config=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            logging=LoggingConfig(bypass_logging=True),
        )
    )
    # CASH accounts are inherently unlevered — nautilus rejects a non-1 leverage on them — so only a
    # MARGIN venue takes the configured leverage. (An oversized notional on CASH is then denied at
    # order time and surfaced via the rejection count, not crashed at venue setup.)
    venue_leverage = Decimal(str(leverage)) if account_type == AccountType.MARGIN else Decimal(1)
    engine.add_venue(
        venue=instrument.id.venue,
        oms_type=OmsType.NETTING,
        account_type=account_type,
        base_currency=currency,
        starting_balances=[Money(starting_cash, currency)],
        default_leverage=venue_leverage,
        fee_model=BpsFeeModel(fee_bps) if fee_bps > 0 else None,
        bar_execution=False,  # bars decide; quotes fill (t+1 open) — see module docstring
    )
    recorder = _EquityRecorder(instrument.id, instrument.id.venue, starting_cash, dividends)
    engine.add_instrument(instrument)
    engine.add_data(list(data))
    engine.add_actor(recorder)
    engine.add_strategy(strategy)
    try:
        engine.run()
        # nautilus stops the run (without raising) when the account balance goes negative or a
        # handler errors; with logging bypassed that would silently yield a TRUNCATED curve and
        # nonsense downstream stats. Fail loud instead.
        n_sessions = sum(1 for d in data if isinstance(d, QuoteTick))
        if len(recorder.curve) != n_sessions:
            raise DataError(
                f"engine stopped after {len(recorder.curve)} of {n_sessions} sessions - "
                "usually the account balance went negative (fees/slippage on a full-balance "
                "fill). Lower target_vol or max_leverage, or raise starting_cash."
            )
        # A fill on the FINAL quote settles after that session's snapshot; without this terminal
        # re-sample its fee/spread would be permanently missing and final_equity overstated.
        if recorder.curve:
            terminal = (
                starting_cash
                + _sum_pnls(recorder.portfolio.realized_pnls(instrument.id.venue))
                + _sum_pnls(recorder.portfolio.unrealized_pnls(instrument.id.venue))
                + recorder.credited_cash
            )
            recorder.curve[-1] = (recorder.curve[-1][0], terminal)
        order_trace, fill_trace = _execution_trace(engine)
        portfolio_state_trace, benchmark_curve = _portfolio_and_benchmark_trace(
            data, recorder.curve, fill_trace
        )
        result = BacktestResult(
            orders=len(engine.trader.generate_orders_report()),
            fills=len(engine.trader.generate_order_fills_report()),
            trades=_closed_trades(engine),
            equity_curve=recorder.curve,
            rejected=int(getattr(strategy, "rejections", 0)),
            decision_trace=tuple(getattr(strategy, "decision_trace", ())),
            indicator_trace=tuple(getattr(strategy, "indicator_trace", ())),
            chart_annotations=tuple(getattr(strategy, "chart_annotations", ())),
            order_trace=order_trace,
            fill_trace=fill_trace,
            portfolio_state_trace=portfolio_state_trace,
            benchmark_curve=benchmark_curve,
            benchmark_kind="passive_open_to_open_price_only",
        )
    finally:
        engine.dispose()
    return result
