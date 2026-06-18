"""Engine-neutral order helpers shared by the backtest harness and paper trading.

``order_signature`` reduces a nautilus ``Order`` to the ``(side, quantity)`` pair that must be
identical between a backtest and a sandbox paper run over the same data — the basis of the parity
guarantee. Fill *prices* differ (fees/slippage); the order sequence must not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nautilus_trader.model.orders import Order


def order_signature(order: Order) -> tuple[str, float]:
    """The engine-independent identity of an order: ``(side_name, quantity)``, e.g. ``BUY, 3.0``."""
    return (order.side.name, float(order.quantity))
