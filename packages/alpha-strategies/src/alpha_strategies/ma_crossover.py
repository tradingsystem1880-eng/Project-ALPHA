"""Moving-average crossover as a nautilus ``Strategy`` (vol-targeted trend filter).

Pure decision logic lives in ``signals.ma_crossover_signal``; this class is only the nautilus wiring
+ position state, inherited from ``VolTargetStrategy`` (decide on close of t, fill at open of t+1).
"""

from __future__ import annotations

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.signals import ma_crossover_signal


class MovingAverageCrossover(VolTargetStrategy):
    """Long when the fast SMA is above the slow SMA, (short/)flat when below."""

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        fast: int = 21,
        slow: int = 100,
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
            min_history=slow,
            vol_window=vol_window,
            target_vol=target_vol,
            capital=capital,
            max_leverage=max_leverage,
            rebalance_every=rebalance_every,
            periods_per_year=periods_per_year,
            allow_short=allow_short,
        )
        self._fast = fast
        self._slow = slow

    def _signal(self) -> int:
        return ma_crossover_signal(self._closes, self._fast, self._slow)
