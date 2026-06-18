"""Project ALPHA shared execution primitives (instruments, fee models, run-result schema)."""

from __future__ import annotations

from alpha_execution.frictions import BpsFeeModel
from alpha_execution.instruments import crypto_instrument, equity_instrument
from alpha_execution.orders import order_signature
from alpha_execution.results import BacktestResult, RunResult, Trade

__version__ = "0.0.0"

__all__ = [
    "BacktestResult",
    "BpsFeeModel",
    "RunResult",
    "Trade",
    "crypto_instrument",
    "equity_instrument",
    "order_signature",
    "__version__",
]
