"""Minimal nautilus ``BacktestEngine`` run harness for the v1 daily slice.

Configured ``bar_execution=False`` so bars drive strategy *decisions* only — fills come from the
open-priced quotes produced by ``feed.to_execution_feed``, giving the spec's "decide on close of t,
fill at open of t+1" convention. Returns a ``BacktestResult`` (counts + closed-trade log +
per-session mark-to-market equity curve).
"""

from __future__ import annotations

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
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Currency, Money
from nautilus_trader.trading.strategy import Strategy

from alpha_backtest.frictions import BpsFeeModel
from alpha_backtest.results import BacktestResult, Trade
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
        result = BacktestResult(
            orders=len(engine.trader.generate_orders_report()),
            fills=len(engine.trader.generate_order_fills_report()),
            trades=_closed_trades(engine),
            equity_curve=recorder.curve,
            rejected=int(getattr(strategy, "rejections", 0)),
        )
    finally:
        engine.dispose()
    return result
