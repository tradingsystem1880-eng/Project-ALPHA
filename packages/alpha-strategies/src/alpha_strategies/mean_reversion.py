"""Z-score mean-reversion as a nautilus ``Strategy`` (vol-targeted short-horizon reversal).

Pure decision logic lives in ``signals.zscore_reversion_signal``; this class is only the nautilus
wiring + position state, inherited from ``VolTargetStrategy`` (decide on close of t, fill at open of
t+1).
"""

from __future__ import annotations

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.signals import zscore_reversion_signal


class MeanReversion(VolTargetStrategy):
    """Fade deviations beyond ``entry_z`` rolling std: short when overbought, long when oversold."""

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        window: int = 20,
        entry_z: float = 1.5,
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
            min_history=window,
            vol_window=vol_window,
            target_vol=target_vol,
            capital=capital,
            max_leverage=max_leverage,
            rebalance_every=rebalance_every,
            periods_per_year=periods_per_year,
            allow_short=allow_short,
        )
        self._window = window
        self._entry_z = entry_z

    def _signal(self) -> int:
        return zscore_reversion_signal(self._closes, self._window, self._entry_z)
