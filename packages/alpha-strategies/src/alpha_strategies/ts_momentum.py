"""Time-series momentum as a nautilus ``Strategy`` (spec §7).

Decides on the close of bar ``t`` and executes at the open of ``t+1`` — the look-ahead-free
execution convention enforced by ``alpha_backtest.feed.to_execution_feed`` + a venue configured
``bar_execution=False``. The quant core (signal, realized vol, vol-target sizing) lives in the pure
``signals``/``sizing`` modules; this class is only the nautilus wiring + position state.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType, QuoteTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from alpha_strategies.signals import ts_momentum_signal
from alpha_strategies.sizing import realized_volatility, vol_target_size


class TimeSeriesMomentum(Strategy):  # type: ignore[misc]  # nautilus Strategy is untyped (Cython)
    """Vol-targeted time-series momentum: decide on close of t, fill at open of t+1.

    Holds its own ``net_units`` (updated from fills) so the target→order delta is self-contained
    and deterministic. Fractional sizing is rounded to whole lots; per-asset-class lot handling and
    portfolio-level caps are later refinements.
    """

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        lookback: int = 252,
        skip: int = 21,
        vol_window: int = 63,
        target_vol: float = 0.15,
        capital: float = 1_000_000.0,
        max_leverage: float = 1.0,
        rebalance_every: int = 21,
        periods_per_year: int = 252,
        allow_short: bool = True,
    ) -> None:
        super().__init__()
        self._iid = instrument_id
        self._bar_type = bar_type
        self._lookback = lookback
        self._skip = skip
        self._vol_window = vol_window
        self._target_vol = target_vol
        self._capital = capital
        self._max_leverage = max_leverage
        self._rebalance_every = rebalance_every
        self._periods_per_year = periods_per_year
        self._allow_short = allow_short  # spec §7: equities long-flat (False), crypto/FX long-short
        self._min_history = max(skip + lookback + 1, vol_window + 1)
        self._closes: list[float] = []
        self._eligible_bars = 0  # bars seen once history suffices; drives the rebalance cadence
        self._target_units: float | None = None
        self.net_units = 0.0
        self.fills = 0
        self.rejections = 0  # orders denied (risk/buying-power) or rejected by the venue

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)
        self.subscribe_quote_ticks(self._iid)

    def on_bar(self, bar: NautilusBar) -> None:
        # Decide on the close of t; the order is placed at the next open (see on_quote_tick).
        self._closes.append(float(bar.close))
        if len(self._closes) < self._min_history:
            return  # warming up — not enough history for the signal or the vol estimate
        # Rebalance on the first eligible bar, then every `rebalance_every` bars from there.
        rebalance_due = self._eligible_bars % self._rebalance_every == 0
        self._eligible_bars += 1
        if not rebalance_due:
            return
        signal = ts_momentum_signal(self._closes, self._lookback, self._skip)
        if signal == 0 or (signal < 0 and not self._allow_short):
            self._target_units = 0.0  # flat: no signal, or a short we are not permitted to take
            return
        annualized_vol = realized_volatility(
            self._closes[-(self._vol_window + 1) :], periods_per_year=self._periods_per_year
        )
        if annualized_vol <= 0.0:
            self._target_units = 0.0  # no realized volatility to target this window -> hold flat
            return
        self._target_units = vol_target_size(
            signal,
            self._closes[-1],
            annualized_vol,
            target_vol=self._target_vol,
            capital=self._capital,
            max_leverage=self._max_leverage,
        )

    def on_quote_tick(self, quote: QuoteTick) -> None:
        # execute the pending target at the session open (t+1)
        if self._target_units is None:
            return
        target = self._target_units
        self._target_units = None
        lots = round(abs(target - self.net_units))
        if lots <= 0:
            return
        side = OrderSide.BUY if target > self.net_units else OrderSide.SELL
        self.submit_order(
            self.order_factory.market(
                instrument_id=self._iid, order_side=side, quantity=Quantity.from_int(lots)
            )
        )

    def on_order_filled(self, event: OrderFilled) -> None:
        self.fills += 1
        qty = float(event.last_qty)
        self.net_units += qty if event.order_side == OrderSide.BUY else -qty

    def on_order_denied(self, event: object) -> None:
        # pre-trade risk denial (e.g. notional exceeds CASH buying power) — count, never swallow
        self.rejections += 1

    def on_order_rejected(self, event: object) -> None:
        self.rejections += 1
