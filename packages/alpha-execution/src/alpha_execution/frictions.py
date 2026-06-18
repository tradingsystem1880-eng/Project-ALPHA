"""Execution frictions: a per-notional (bps) fee model (spec §7).

Shared by the backtest venue and the paper sandbox venue so both charge commissions identically.
Slippage is modeled separately as a side-aware bid/ask spread on the execution quote — see
``alpha_backtest.feed``'s ``slippage_bps``.
"""

from __future__ import annotations

from nautilus_trader.backtest.models import FeeModel
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Money, Price, Quantity


class BpsFeeModel(FeeModel):  # type: ignore[misc]  # nautilus FeeModel is untyped (Cython)
    """Commission = notional × (``fee_bps`` / 10_000), in the instrument's quote currency."""

    def __init__(self, fee_bps: float) -> None:
        super().__init__()
        self._rate = fee_bps / 10_000.0

    def get_commission(
        self, order: object, fill_qty: Quantity, fill_px: Price, instrument: Instrument
    ) -> Money:
        notional = float(fill_qty) * float(fill_px)
        return Money(notional * self._rate, instrument.quote_currency)
