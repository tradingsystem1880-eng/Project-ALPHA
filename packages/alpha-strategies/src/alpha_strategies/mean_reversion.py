"""Z-score mean-reversion as a nautilus ``Strategy`` (vol-targeted short-horizon reversal).

Pure decision logic lives in ``signals.zscore_reversion_signal``; this class is only the nautilus
wiring + position state, inherited from ``VolTargetStrategy`` (decide on close of t, fill at open of
t+1).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

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
        size_on_equity: bool = False,
        halt_drawdown: float | None = None,
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
            size_on_equity=size_on_equity,
            halt_drawdown=halt_drawdown,
        )
        self._window = window
        self._entry_z = entry_z

    def _signal(self) -> int:
        return zscore_reversion_signal(self._closes, self._window, self._entry_z)

    def _indicator_snapshot(self) -> Mapping[str, tuple[float, str]]:
        values = dict(super()._indicator_snapshot())
        sample = self._closes[-self._window :]
        mean = sum(sample) / self._window
        variance = sum((value - mean) ** 2 for value in sample) / (self._window - 1)
        std = math.sqrt(variance)
        zscore = (sample[-1] - mean) / std if std > 0.0 else 0.0
        values.update(
            {
                "rolling_mean": (mean, "price"),
                "upper_entry_band": (mean + self._entry_z * std, "price"),
                "lower_entry_band": (mean - self._entry_z * std, "price"),
                "zscore": (zscore, "standard_deviation"),
                "entry_z": (self._entry_z, "standard_deviation"),
            }
        )
        return values
