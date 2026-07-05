"""Time-series momentum as a nautilus ``Strategy`` (spec §7).

Decides on the close of bar ``t`` and executes at the open of ``t+1`` — the look-ahead-free
execution convention enforced by ``alpha_backtest.feed.to_execution_feed`` + a venue configured
``bar_execution=False``. The quant core (signal, realized vol, vol-target sizing) lives in the pure
``signals``/``sizing`` modules; the shared nautilus lifecycle (rebalance cadence, t+1 fills, risk
controls) lives in ``VolTargetStrategy`` — this class only binds the momentum signal. (It predated
the base as a standalone implementation; the two had already begun to drift, so the duplication was
retired during the 2026-07 audit.)
"""

from __future__ import annotations

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.signals import ts_momentum_signal


class TimeSeriesMomentum(VolTargetStrategy):
    """Vol-targeted time-series momentum: decide on close of t, fill at open of t+1."""

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
        size_on_equity: bool = False,
        halt_drawdown: float | None = None,
    ) -> None:
        super().__init__(
            instrument_id=instrument_id,
            bar_type=bar_type,
            min_history=skip + lookback + 1,
            vol_window=vol_window,
            target_vol=target_vol,
            capital=capital,
            max_leverage=max_leverage,
            rebalance_every=rebalance_every,
            periods_per_year=periods_per_year,
            allow_short=allow_short,
            size_on_equity=size_on_equity,
            halt_drawdown=halt_drawdown,
        )
        self._lookback = lookback
        self._skip = skip

    def _signal(self) -> int:
        return ts_momentum_signal(self._closes, self._lookback, self._skip)
