"""Replay a precomputed signal sequence by bar index — the kronos engine strategy.

The foundation model never runs inside the engine (strategies are rebuilt from pickled
specs in spawn workers): the CLI precomputes signals at exactly the rebalance-schedule
indices (``alpha_cli._forecast_cache``) and this strategy replays them. Querying an index
the cache does not cover is a ``DataError`` — a schedule mismatch must abort the run, not
silently trade flat.
"""

from __future__ import annotations

from collections.abc import Sequence

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from alpha_core import DataError
from alpha_strategies.base import VolTargetStrategy


class SignalReplay(VolTargetStrategy):
    """Vol-targeted strategy whose signal at bar ``i`` is the precomputed ``signals[i]``."""

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        signals: Sequence[int | None],
        min_history: int,
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
            min_history=min_history,
            vol_window=vol_window,
            target_vol=target_vol,
            capital=capital,
            max_leverage=max_leverage,
            rebalance_every=rebalance_every,
            periods_per_year=periods_per_year,
            allow_short=allow_short,
        )
        self._signals = list(signals)

    def _signal(self) -> int:
        index = len(self._closes) - 1
        value = self._signals[index] if index < len(self._signals) else None
        if value is None:
            raise DataError(
                f"forecast signal cache does not cover bar {index} — schedule mismatch "
                "(cadence/warmup changed since the precompute?); re-run through the alpha CLI"
            )
        return int(value)
