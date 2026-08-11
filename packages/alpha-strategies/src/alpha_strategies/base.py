"""Shared nautilus wiring for vol-targeted long/flat/short strategies (spec §7).

``VolTargetStrategy`` factors out the execution lifecycle every signal-based strategy in ALPHA
shares: accumulate OHLC history, rebalance on a fixed cadence, turn a ``{-1,0,1}`` signal into a
vol-targeted position, decide on the close of bar ``t`` and fill at the open of ``t+1`` (the
look-ahead-free convention enforced by ``alpha_backtest.feed`` + ``bar_execution=False``). Concrete
strategies implement only the pure ``_signal`` hook. (``TimeSeriesMomentum`` predates this base and
remains the standalone reference implementation; this base is the template for the rest.)
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType, QuoteTick
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.events import OrderCanceled, OrderExpired, OrderFilled
from nautilus_trader.model.identifiers import AccountId, ClientOrderId, InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from alpha_core import (
    Bar,
    ChartAnnotationTrace,
    DataError,
    DecisionTrace,
    ExecutionEventSink,
    IndicatorTrace,
)
from alpha_strategies.sizing import realized_volatility, vol_target_size


@dataclass(frozen=True, slots=True)
class PaperRiskLimits:
    """Absolute limits derived by ``alpha_cli`` from an approved paper risk profile."""

    max_order_notional: float
    max_position_notional: float
    max_gross_notional: float
    daily_loss_fraction: float
    max_open_orders: int
    max_quote_age_seconds: float
    intent_id: str
    account_id: str | None = None
    expected_position_units: float = 0.0
    order_cutoff: datetime | None = None

    def __post_init__(self) -> None:
        positive = (
            self.max_order_notional,
            self.max_position_notional,
            self.max_gross_notional,
            self.daily_loss_fraction,
            self.max_quote_age_seconds,
        )
        if any(not math.isfinite(value) or value <= 0.0 for value in positive):
            raise DataError("paper risk limits must be finite and positive")
        if self.max_order_notional > self.max_position_notional:
            raise DataError("paper max order notional cannot exceed max position notional")
        if self.max_position_notional > self.max_gross_notional:
            raise DataError("paper max position notional cannot exceed max gross notional")
        if not 0.0 < self.daily_loss_fraction < 1.0 or self.max_open_orders < 1:
            raise DataError("invalid paper daily-loss or open-order limit")
        if len(self.intent_id) != 64 or any(
            character not in "0123456789abcdef" for character in self.intent_id
        ):
            raise DataError("paper intent id must be a lowercase SHA-256")
        if self.account_id is not None and not self.account_id.startswith("DU"):
            raise DataError("paper risk account must be an IBKR DU… account")
        if not math.isfinite(self.expected_position_units):
            raise DataError("paper expected position must be finite")
        if self.order_cutoff is not None and (
            self.order_cutoff.tzinfo is None or self.order_cutoff.utcoffset() is None
        ):
            raise DataError("paper order cutoff must be timezone-aware")


def _sum_money(pnls: Any) -> float:
    """Sum a nautilus per-currency PnL dict to a float (single base currency in v1)."""
    return float(sum(money.as_double() for money in pnls.values()))


def normalize_order_quantity(
    delta: float, *, size_precision: int, size_increment: float
) -> Quantity | None:
    """Return a valid venue quantity without changing the legacy integer-lot SIM path.

    Existing simulations round to the nearest integer, so that exact behavior is retained when
    the instrument advertises precision ``0`` and increment ``1``.  Fractional live quantities
    are rounded down to the nearest positive venue increment to avoid exceeding the target.
    """
    magnitude = abs(delta)
    if size_precision == 0 and size_increment == 1.0:
        lots = round(magnitude)
        return Quantity.from_int(lots) if lots > 0 else None
    if size_increment <= 0.0:
        raise DataError(f"instrument size_increment must be > 0, got {size_increment}")
    raw = Decimal(str(magnitude))
    increment = Decimal(str(size_increment))
    steps = (raw / increment).to_integral_value(rounding=ROUND_DOWN)
    normalized = steps * increment
    if normalized <= 0:
        return None
    return Quantity(float(normalized), size_precision)


class VolTargetStrategy(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped (Cython)
    """Base for vol-targeted signal strategies: decide on close of t, fill at open of t+1.

    Subclasses set ``min_history`` (closes needed before the first decision) and implement
    ``_signal() -> int`` over ``self._closes`` / ``self._highs`` / ``self._lows``. Holds its own
    ``net_units`` (updated from fills) so the target→order delta is self-contained + deterministic.
    """

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        min_history: int,
        vol_window: int = 63,
        target_vol: float = 0.15,
        capital: float = 1_000_000.0,
        max_leverage: float = 1.0,
        rebalance_every: int = 21,
        periods_per_year: int = 252,
        allow_short: bool = True,
        size_on_equity: bool = False,
        halt_drawdown: float | None = None,
    ) -> None:
        super().__init__()
        if halt_drawdown is not None and not 0.0 < halt_drawdown < 1.0:
            raise DataError(f"halt_drawdown must be in (0, 1) or None, got {halt_drawdown}")
        self._iid = instrument_id
        self._bar_type = bar_type
        self._vol_window = vol_window
        self._target_vol = target_vol
        self._capital = capital
        self._max_leverage = max_leverage
        self._rebalance_every = rebalance_every
        self._periods_per_year = periods_per_year
        self._allow_short = allow_short  # spec §7: equities long-flat (False), crypto/FX long-short
        # risk controls (both opt-in; defaults preserve the fixed-capital, no-halt behavior):
        # size_on_equity re-bases the vol-target notional on CURRENT net-liq each rebalance, so
        # exposure de-levers in drawdowns instead of silently gearing up; halt_drawdown is a
        # kill-switch - once net-liq breaches peak*(1-halt_drawdown) the book goes flat for good.
        self._size_on_equity = size_on_equity
        self._halt_drawdown = halt_drawdown
        self._peak_equity = capital
        self.halted = False
        self._min_history = max(min_history, vol_window + 1)
        self._closes: list[float] = []
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._history_ts: list[datetime] = []
        self._eligible_bars = 0  # bars seen once history suffices; drives the rebalance cadence
        self._target_units: float | None = None
        self.net_units = 0.0
        self.fills = 0
        self.rejections = 0  # orders denied (risk/buying-power) or rejected by the venue
        self._event_sink: ExecutionEventSink | None = None
        self._paper_risk: PaperRiskLimits | None = None
        self._paper_reconciled = False
        self._paper_session_date: date | None = None
        self._paper_session_equity: float | None = None
        self._paper_intents: set[str] = set()
        self._decision_trace: list[DecisionTrace] = []
        self._indicator_trace: list[IndicatorTrace] = []
        self._chart_annotations: list[ChartAnnotationTrace] = []

    @property
    def history_size(self) -> int:
        """Number of bars currently held by the strategy (including paper warmup)."""
        return len(self._closes)

    @property
    def eligible_bars(self) -> int:
        """Number of post-warmup bars counted by the rebalance cadence."""
        return self._eligible_bars

    @property
    def pending_target(self) -> float | None:
        """The next-open target, exposed read-only for paper safety checks."""
        return self._target_units

    @property
    def decision_trace(self) -> tuple[DecisionTrace, ...]:
        """Observed close-time decisions; indicators/patterns are intentionally not inferred."""
        return tuple(self._decision_trace)

    @property
    def indicator_trace(self) -> tuple[IndicatorTrace, ...]:
        """Causal indicator values captured by the strategy at each decision."""
        return tuple(self._indicator_trace)

    @property
    def chart_annotations(self) -> tuple[ChartAnnotationTrace, ...]:
        """Deterministic vector annotations captured from the same trailing decision prefix."""
        return tuple(self._chart_annotations)

    def _indicator_snapshot(self) -> Mapping[str, tuple[float, str]]:
        """Named values visible at the current decision; subclasses add strategy indicators."""
        return {"close": (self._closes[-1], "price")}

    def _annotation_snapshot(self, decision_ts: datetime) -> Sequence[ChartAnnotationTrace]:
        """Vector evidence for the current decision; most strategies need no annotation."""
        del decision_ts
        return ()

    def _record_decision(
        self,
        bar: NautilusBar,
        *,
        signal: int | None,
        target_quantity: float,
        reason: str,
    ) -> None:
        decision_ts = datetime.fromtimestamp(int(bar.ts_event) / 1_000_000_000, tz=UTC)
        self._decision_trace.append(
            DecisionTrace(
                ts=decision_ts,
                instrument_id=str(self._iid),
                signal=signal,
                target_quantity=target_quantity,
                reason=reason,
            )
        )
        for name, (value, unit) in sorted(self._indicator_snapshot().items()):
            self._indicator_trace.append(
                IndicatorTrace(
                    ts=decision_ts,
                    instrument_id=str(self._iid),
                    name=name,
                    value=value,
                    unit=unit,
                )
            )
        self._chart_annotations.extend(self._annotation_snapshot(decision_ts))

    def set_execution_event_sink(self, sink: ExecutionEventSink | None) -> None:
        """Attach the operational paper journal; deterministic backtests leave this unset."""
        self._event_sink = sink

    def configure_paper_risk(self, limits: PaperRiskLimits, *, reconciled: bool = False) -> None:
        """Enable broker-paper controls without changing deterministic backtest defaults."""
        if self._event_sink is None:
            raise DataError("paper risk requires a durable execution event sink")
        self._paper_risk = limits
        self._paper_reconciled = reconciled

    def mark_paper_reconciled(self) -> None:
        """Release paper order authority only after exact broker-state reconciliation."""
        risk = self._paper_risk
        if risk is None:
            raise DataError("paper risk is not configured")
        self.net_units = risk.expected_position_units
        self._paper_reconciled = True

    def release_paper_intent(self, *, intent_id: str, target_quantity: float) -> None:
        """Stage the exact CLI-approved target for release on the next fresh quote."""
        risk = self._paper_risk
        if risk is None:
            raise DataError("paper risk is not configured")
        if intent_id != risk.intent_id:
            raise DataError("released paper intent does not match the approved risk boundary")
        if not math.isfinite(target_quantity):
            raise DataError("released paper target quantity must be finite")
        self._target_units = target_quantity

    def _emit(
        self,
        event_type: str,
        payload: Mapping[str, str | int | float | bool | None],
        *,
        ts_event_ns: int | None = None,
    ) -> None:
        if self._event_sink is not None:
            self._event_sink.emit(event_type, payload, ts_event_ns=ts_event_ns)

    def _append_history(self, ts: datetime, close: float, high: float, low: float) -> bool:
        """Append one bar and advance cadence; return whether this bar may rebalance."""
        self._closes.append(close)
        self._highs.append(high)
        self._lows.append(low)
        self._history_ts.append(ts)
        if len(self._closes) < self._min_history:
            return False
        rebalance_due = self._eligible_bars % self._rebalance_every == 0
        self._eligible_bars += 1
        return rebalance_due

    def prime_history(self, bars: Sequence[Bar]) -> None:
        """Warm indicators and cadence from PIT bars without creating targets or orders.

        The caller must first enforce the snapshot's provenance and knowledge cutoff.  This method
        additionally requires strictly increasing timestamps and intentionally performs only the
        history/cadence portion of :meth:`on_bar`; historical decisions cannot leak into the live
        session as a pending order.
        """
        previous = None
        for bar in bars:
            if previous is not None and bar.ts <= previous:
                raise ValueError("paper warmup bars must have strictly increasing timestamps")
            self._append_history(bar.ts, bar.close, bar.high, bar.low)
            previous = bar.ts
        self._target_units = None

    def _net_liq(self) -> float:
        """Current net-liquidation equity (same formula as the engine's recorder)."""
        venue = self._iid.venue
        return (
            self._capital
            + _sum_money(self.portfolio.realized_pnls(venue))
            + _sum_money(self.portfolio.unrealized_pnls(venue))
        )

    def _signal(self) -> int:
        """Return the {-1, 0, 1} signal from the accumulated history. Implemented by subclasses."""
        raise NotImplementedError

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)
        self.subscribe_quote_ticks(self._iid)
        risk = self._paper_risk
        if risk is None or self._paper_reconciled:
            return
        if risk.account_id is None:
            self.halted = True
            self._emit("reconciliation", {"state": "mismatch", "reason": "missing_account"})
            return
        account_id = AccountId(risk.account_id)
        account = self.cache.account_for_venue(self._iid.venue, account_id=account_id)
        open_orders = self.cache.orders_open(account_id=account_id)
        open_positions = self.cache.positions_open(account_id=account_id)
        instrument_positions = self.cache.positions_open(
            instrument_id=self._iid,
            account_id=account_id,
        )
        actual_units = sum(float(position.signed_qty) for position in instrument_positions)
        unexpected_positions = len(open_positions) - len(instrument_positions)
        self._emit(
            "account_snapshot",
            {
                "account_present": account is not None,
                "open_orders": len(open_orders),
                "open_positions": len(open_positions),
                "unexpected_positions": unexpected_positions,
                "expected_units": risk.expected_position_units,
                "actual_units": actual_units,
            },
        )
        if (
            account is None
            or open_orders
            or unexpected_positions
            or not math.isclose(actual_units, risk.expected_position_units, abs_tol=1e-9)
        ):
            self.halted = True
            self._emit(
                "reconciliation",
                {
                    "state": "mismatch",
                    "account_present": account is not None,
                    "open_orders": len(open_orders),
                    "open_positions": len(open_positions),
                    "unexpected_positions": unexpected_positions,
                    "expected_units": risk.expected_position_units,
                    "actual_units": actual_units,
                },
            )
            return
        self.mark_paper_reconciled()
        self._emit(
            "reconciliation",
            {
                "state": "matched",
                "account_present": True,
                "open_orders": len(open_orders),
                "open_positions": len(open_positions),
                "expected_units": risk.expected_position_units,
                "actual_units": actual_units,
            },
        )

    def on_bar(self, bar: NautilusBar) -> None:
        # Decide on the close of t; the order is placed at the next open (see on_quote_tick).
        decision_ts = datetime.fromtimestamp(int(bar.ts_event) / 1_000_000_000, tz=UTC)
        rebalance_due = self._append_history(
            decision_ts, float(bar.close), float(bar.high), float(bar.low)
        )
        if self._paper_risk is not None:
            equity = self._net_liq()
            if self._paper_session_date != decision_ts.date():
                self._paper_session_date = decision_ts.date()
                self._paper_session_equity = equity
            session_equity = self._paper_session_equity
            if session_equity is not None and equity <= session_equity * (
                1.0 - self._paper_risk.daily_loss_fraction
            ):
                self.halted = True
                self._target_units = 0.0
                self._emit(
                    "risk_check",
                    {"check": "daily_loss", "passed": False, "equity": equity},
                    ts_event_ns=int(bar.ts_event),
                )
                self._record_decision(
                    bar, signal=None, target_quantity=0.0, reason="daily_loss_halt"
                )
                return
        if not rebalance_due:
            return
        capital = self._capital
        if self._size_on_equity or self._halt_drawdown is not None:
            equity = self._net_liq()
            self._peak_equity = max(self._peak_equity, equity)
            if self._halt_drawdown is not None and (
                self.halted or equity <= self._peak_equity * (1.0 - self._halt_drawdown)
            ):
                self.halted = True  # kill-switch: flatten at the next open, never re-enter
                self._target_units = 0.0
                self._record_decision(bar, signal=None, target_quantity=0.0, reason="drawdown_halt")
                return
            if self._size_on_equity:
                if equity <= 0.0:
                    self._target_units = 0.0  # blown-up book cannot be vol-sized; stay flat
                    self._record_decision(
                        bar, signal=None, target_quantity=0.0, reason="nonpositive_equity"
                    )
                    return
                capital = equity
        signal = self._signal()
        if signal == 0 or (signal < 0 and not self._allow_short):
            self._target_units = 0.0  # flat: no signal, or a short we are not permitted to take
            reason = "flat_signal" if signal == 0 else "short_disallowed"
            self._record_decision(bar, signal=signal, target_quantity=0.0, reason=reason)
            return
        annualized_vol = realized_volatility(
            self._closes[-(self._vol_window + 1) :], periods_per_year=self._periods_per_year
        )
        if annualized_vol <= 0.0:
            self._target_units = 0.0  # no realized volatility to target this window -> hold flat
            self._record_decision(bar, signal=signal, target_quantity=0.0, reason="zero_volatility")
            return
        self._target_units = vol_target_size(
            signal,
            self._closes[-1],
            annualized_vol,
            target_vol=self._target_vol,
            capital=capital,
            max_leverage=self._max_leverage,
        )
        if self._paper_risk is not None:
            max_units = self._paper_risk.max_position_notional / self._closes[-1]
            self._target_units = max(-max_units, min(max_units, self._target_units))
        self._record_decision(
            bar, signal=signal, target_quantity=self._target_units, reason="target"
        )

    def on_quote_tick(self, quote: QuoteTick) -> None:
        # execute the pending target at the session open (t+1)
        if self._target_units is None:
            return
        target = self._target_units
        self._target_units = None
        delta = target - self.net_units
        risk = self._paper_risk
        if risk is not None:
            if not self._paper_reconciled:
                self.halted = True
                self._emit(
                    "risk_check",
                    {"check": "reconciliation", "passed": False},
                    ts_event_ns=int(quote.ts_event),
                )
                return
            now = self.clock.utc_now()
            if risk.order_cutoff is not None and now >= risk.order_cutoff:
                self._emit(
                    "expired",
                    {"reason": "order_cutoff", "cutoff": risk.order_cutoff.isoformat()},
                    ts_event_ns=int(quote.ts_event),
                )
                return
            quote_time = datetime.fromtimestamp(int(quote.ts_event) / 1_000_000_000, tz=UTC)
            quote_age = (now - quote_time).total_seconds()
            if quote_age > risk.max_quote_age_seconds or quote_age < -1.0:
                self.halted = True
                self._emit(
                    "risk_check",
                    {"check": "quote_freshness", "passed": False, "age_seconds": quote_age},
                    ts_event_ns=int(quote.ts_event),
                )
                return
            open_orders = self.cache.orders_open(account_id=None)
            if len(open_orders) >= risk.max_open_orders:
                self.halted = True
                self._emit(
                    "risk_check",
                    {"check": "open_orders", "passed": False, "count": len(open_orders)},
                    ts_event_ns=int(quote.ts_event),
                )
                return
        instrument = self.cache.instrument(self._iid)
        if instrument is None:
            self.rejections += 1
            self._emit(
                "reconciliation_warning",
                {
                    "instrument_id": str(self._iid),
                    "detail": "instrument missing from strategy cache; order suppressed",
                },
                ts_event_ns=int(quote.ts_event),
            )
            return
        side = OrderSide.BUY if delta > 0.0 else OrderSide.SELL
        if risk is not None:
            reference_price = float(quote.ask_price if side == OrderSide.BUY else quote.bid_price)
            if not math.isfinite(reference_price) or reference_price <= 0.0:
                self.halted = True
                self._emit(
                    "risk_check",
                    {"check": "quote_price", "passed": False},
                    ts_event_ns=int(quote.ts_event),
                )
                return
            max_delta = risk.max_order_notional / reference_price
            delta = max(-max_delta, min(max_delta, delta))
        quantity = normalize_order_quantity(
            delta,
            size_precision=int(instrument.size_precision),
            size_increment=float(instrument.size_increment),
        )
        if quantity is None:
            return
        intent_id = None
        if risk is not None:
            intent_id = risk.intent_id
            if intent_id in self._paper_intents:
                self.halted = True
                self._emit(
                    "risk_check",
                    {"check": "duplicate_intent", "passed": False, "intent_id": intent_id},
                    ts_event_ns=int(quote.ts_event),
                )
                return
            # Journal authority before submission. Any storage failure propagates and no order is
            # sent; the content hash becomes the Nautilus/IB idempotency reference.
            self._emit(
                "intent",
                {
                    "intent_id": intent_id,
                    "instrument_id": str(self._iid),
                    "side": str(side),
                    "quantity": float(quantity),
                    "risk_profile": "ibkr-equity-paper-v1",
                },
                ts_event_ns=int(quote.ts_event),
            )
            self._paper_intents.add(intent_id)
        order = self.order_factory.market(
            instrument_id=self._iid,
            order_side=side,
            quantity=quantity,
            time_in_force=TimeInForce.DAY if risk is not None else TimeInForce.GTC,
            client_order_id=ClientOrderId(intent_id) if intent_id is not None else None,
        )
        self.submit_order(order)
        self._emit(
            "order",
            {
                "instrument_id": str(self._iid),
                "client_order_id": str(order.client_order_id),
                "side": str(side),
                "quantity": float(quantity),
                "intent_id": intent_id,
            },
            ts_event_ns=int(quote.ts_event),
        )

    def on_stop(self) -> None:
        """Cancel this strategy's open orders; safe stop intentionally never flattens positions."""
        self.cancel_all_orders(self._iid)

    def on_order_filled(self, event: OrderFilled) -> None:
        self.fills += 1
        qty = float(event.last_qty)
        self.net_units += qty if event.order_side == OrderSide.BUY else -qty
        ts_event_ns = int(event.ts_event)
        self._emit(
            "fill",
            {
                "instrument_id": str(self._iid),
                "client_order_id": str(event.client_order_id),
                "side": str(event.order_side),
                "quantity": qty,
                "price": float(event.last_px),
            },
            ts_event_ns=ts_event_ns,
        )
        self._emit(
            "position",
            {"instrument_id": str(self._iid), "net_units": self.net_units},
            ts_event_ns=ts_event_ns,
        )

    def on_order_canceled(self, event: OrderCanceled) -> None:
        self._emit_order_terminal(event, "cancel")

    def on_order_expired(self, event: OrderExpired) -> None:
        self._emit_order_terminal(event, "expired")

    def _emit_order_terminal(self, event: object, event_type: str) -> None:
        ts_event = getattr(event, "ts_event", None)
        self._emit(
            event_type,
            {
                "instrument_id": str(getattr(event, "instrument_id", self._iid)),
                "client_order_id": str(getattr(event, "client_order_id", "")),
                "venue_order_id": str(getattr(event, "venue_order_id", "")),
            },
            ts_event_ns=int(ts_event) if ts_event is not None else None,
        )

    def on_order_denied(self, event: object) -> None:
        # pre-trade risk denial (e.g. notional exceeds CASH buying power) — count, never swallow
        self.rejections += 1
        self._emit_rejection(event, "denied")

    def on_order_rejected(self, event: object) -> None:
        self.rejections += 1
        self._emit_rejection(event, "rejected")

    def _emit_rejection(self, event: object, outcome: str) -> None:
        if self._paper_risk is not None:
            self.halted = True
        reason = getattr(event, "reason", None)
        ts_event = getattr(event, "ts_event", None)
        self._emit(
            "rejection",
            {
                "instrument_id": str(self._iid),
                "outcome": outcome,
                "reason": str(reason) if reason is not None else None,
            },
            ts_event_ns=int(ts_event) if ts_event is not None else None,
        )
