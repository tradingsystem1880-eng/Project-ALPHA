"""Shared nautilus wiring for vol-targeted long/flat/short strategies (spec §7).

``VolTargetStrategy`` factors out the execution lifecycle every signal-based strategy in ALPHA
shares: accumulate OHLC history, rebalance on a fixed cadence, turn a ``{-1,0,1}`` signal into a
vol-targeted position, decide on the close of bar ``t`` and fill at the open of ``t+1`` (the
look-ahead-free convention enforced by ``alpha_backtest.feed`` + ``bar_execution=False``). Concrete
strategies implement only the pure ``_signal`` hook. (``TimeSeriesMomentum`` predates this base and
remains the standalone reference implementation; this base is the template for the rest.)
"""

from __future__ import annotations

from typing import Any

from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType, QuoteTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from alpha_core import DataError
from alpha_strategies.sizing import realized_volatility, vol_target_size


def _sum_money(pnls: Any) -> float:
    """Sum a nautilus per-currency PnL dict to a float (single base currency in v1)."""
    return float(sum(money.as_double() for money in pnls.values()))


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
        self._eligible_bars = 0  # bars seen once history suffices; drives the rebalance cadence
        self._target_units: float | None = None
        self.net_units = 0.0
        self.fills = 0
        self.rejections = 0  # orders denied (risk/buying-power) or rejected by the venue

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

    def on_bar(self, bar: NautilusBar) -> None:
        # Decide on the close of t; the order is placed at the next open (see on_quote_tick).
        self._closes.append(float(bar.close))
        self._highs.append(float(bar.high))
        self._lows.append(float(bar.low))
        if len(self._closes) < self._min_history:
            return  # warming up — not enough history for the signal or the vol estimate
        rebalance_due = self._eligible_bars % self._rebalance_every == 0
        self._eligible_bars += 1
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
                return
            if self._size_on_equity:
                if equity <= 0.0:
                    self._target_units = 0.0  # blown-up book cannot be vol-sized; stay flat
                    return
                capital = equity
        signal = self._signal()
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
            capital=capital,
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
