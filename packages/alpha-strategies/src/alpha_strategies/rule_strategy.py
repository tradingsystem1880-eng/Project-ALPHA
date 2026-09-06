"""The owner's rule set as a nautilus ``Strategy`` (spec 2026-09-01 §4.2, Phase 5 S4).

Decision logic is ``rules.rule_signal`` over exactly ``spec.history`` trailing bars; this class is
only the vol-target wiring inherited from ``VolTargetStrategy`` (decide on close of ``t``, fill at
open of ``t+1``). The indicator snapshot records every operand's value on the decision bar so the
causal trace shows *why* the rule held.
"""

from __future__ import annotations

from collections.abc import Mapping

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from alpha_patterns import OHLCV
from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.rules import RuleSpec, evaluate_rules, operand_series, trailing_ohlcv


class RuleStrategy(VolTargetStrategy):
    """Be long while every ``long_when`` holds, short while every ``short_when`` holds."""

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        spec: RuleSpec,
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
            min_history=spec.history,
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
        self._spec = spec

    def _window(self) -> OHLCV:
        return trailing_ohlcv(
            self._highs,
            self._lows,
            self._closes,
            history=self._spec.history,
            symbol=str(self._iid),
        )

    def _signal(self) -> int:
        return evaluate_rules(self._spec, self._window())

    def _indicator_snapshot(self) -> Mapping[str, tuple[float, str]]:
        values = dict(super()._indicator_snapshot())
        window = self._window()
        for operand in self._spec.operands:
            if operand.kind == "indicator":
                unit = "index" if operand.indicator == "rsi" else "price"
                values[operand.label] = (float(operand_series(window, operand)[-1]), unit)
        return values
