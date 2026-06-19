"""Donchian channel breakout as a nautilus ``Strategy`` (vol-targeted turtle-style trend).

Pure decision logic lives in ``signals.breakout_signal``; this class is only the nautilus wiring +
position state, inherited from ``VolTargetStrategy`` (decide on close of t, fill at open of t+1).
"""

from __future__ import annotations

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.signals import breakout_signal


class DonchianBreakout(VolTargetStrategy):
    """Go with the trend on a new ``window``-bar high (long) or low (short/flat)."""

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        window: int = 55,
        vol_window: int = 63,
        target_vol: float = 0.15,
        capital: float = 1_000_000.0,
        max_leverage: float = 1.0,
        rebalance_every: int = 1,
        periods_per_year: int = 252,
        allow_short: bool = True,
    ) -> None:
        super().__init__(
            instrument_id=instrument_id,
            bar_type=bar_type,
            min_history=window + 1,
            vol_window=vol_window,
            target_vol=target_vol,
            capital=capital,
            max_leverage=max_leverage,
            rebalance_every=rebalance_every,
            periods_per_year=periods_per_year,
            allow_short=allow_short,
        )
        self._window = window

    def _signal(self) -> int:
        return breakout_signal(self._highs, self._lows, self._closes, self._window)
