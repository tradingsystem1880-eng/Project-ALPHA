"""Kronos-forecast strategy: a ``VolTargetStrategy`` driven by an injected ``BarForecaster``.

The forecaster is dependency-injected (constructor arg) so this package never imports
torch-land: ``alpha_forecast.KronosForecaster`` satisfies the ``alpha_core.BarForecaster``
protocol and is composed in by ``alpha_cli`` (the only layer allowed to). The mapping from
forecast to ``{-1, 0, 1}`` lives in the pure ``signals.forecast_signal``.

Weight-level look-ahead caveat: a pretrained forecaster's weights may embed knowledge of
the backtest window (Kronos trained on data up to ~2025-08). This class enforces
accessor-level discipline (the forecaster sees only trailing bars); the weight-level
caveat is surfaced by the CLI as a loud warning + manifest field.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from alpha_core import Bar, BarForecaster
from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.signals import forecast_signal


class KronosForecast(VolTargetStrategy):
    """Long/short/flat from a bar forecaster's horizon-end expected return.

    On each rebalance bar the trailing ``context`` bars are handed to the forecaster; the
    predicted closes map to a signal via ``forecast_signal`` (deadband in bps), which the
    base then sizes vol-targeted (decide close of t, fill open of t+1).
    """

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        forecaster: BarForecaster,
        context: int,
        horizon: int = 30,
        deadband_bps: float = 25.0,
        vol_window: int = 63,
        target_vol: float = 0.15,
        capital: float = 1_000_000.0,
        max_leverage: float = 1.0,
        rebalance_every: int = 21,
        periods_per_year: int = 252,
        allow_short: bool = True,
    ) -> None:
        super().__init__(
            instrument_id=instrument_id,
            bar_type=bar_type,
            min_history=context,
            vol_window=vol_window,
            target_vol=target_vol,
            capital=capital,
            max_leverage=max_leverage,
            rebalance_every=rebalance_every,
            periods_per_year=periods_per_year,
            allow_short=allow_short,
        )
        self._forecaster = forecaster
        self._context = context
        self._horizon = horizon
        self._deadband_bps = deadband_bps
        self._bars: list[Bar] = []  # full OHLCV+ts history (base keeps only closes/highs/lows)

    def on_bar(self, bar: NautilusBar) -> None:
        self._bars.append(
            Bar(
                symbol=str(self._iid.symbol),
                ts=datetime.fromtimestamp(bar.ts_event / 1e9, tz=UTC),
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=float(bar.volume),
            )
        )
        super().on_bar(bar)  # base gates warmup + cadence and calls _signal on rebalance bars

    def _signal(self) -> int:
        window = self._bars[-self._context :]
        forecast = self._forecaster.forecast(window, self._horizon)
        return forecast_signal(self._closes[-1], [b.close for b in forecast], self._deadband_bps)
