"""Paper-trading scaffold (Phase 4) — the sandbox execution venue + backtest↔paper parity.

The spec's paper-trading promise is that the *same* ``Strategy`` class runs in backtest and paper.
This module wires the execution side ALPHA controls — a nautilus ``SandboxExecutionClient`` that
fills orders with the *same* convention as the backtest (``bar_execution=False``: decide on close,
fill on the next quote) — and reuses the strategy registry so paper runs the identical strategy a
backtest does. Config assembly is fully offline-constructible (and tested); the only piece that
needs network + credentials is a live market-data adapter, which the caller supplies as
``data_clients`` (e.g. a nautilus Binance/Bybit testnet config). ``run_paper`` fails loud with
guidance until that is provided, so nothing here silently pretends to be live.

Lives in ``alpha_cli`` (the composition layer) like ``_portfolio``/``_optim``; nautilus imports are
lazy so importing the CLI stays cheap and the architecture DAG is unaffected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alpha_core import AlphaError

if TYPE_CHECKING:
    from alpha_cli._runner import RunSpec


def build_sandbox_exec_config(
    *, venue: str, account_type: str, starting_cash: float, currency: str
) -> Any:
    """A ``SandboxExecutionClientConfig`` with backtest-parity fills (quotes fill, bars decide)."""
    from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig

    return SandboxExecutionClientConfig(
        venue=venue,
        starting_balances=[f"{starting_cash:.2f} {currency}"],
        base_currency=currency,
        account_type=account_type,  # "CASH" (long-flat) | "MARGIN" (long-short)
        oms_type="NETTING",
        bar_execution=False,  # parity with alpha_backtest: decide on close, fill on the next quote
    )


def build_paper_node_config(
    *, trader_id: str, exec_config: Any, data_clients: dict[str, Any] | None = None
) -> Any:
    """Assemble a ``TradingNodeConfig`` with the sandbox exec client + any live data clients."""
    from nautilus_trader.live.config import TradingNodeConfig

    return TradingNodeConfig(
        trader_id=trader_id,
        exec_clients={str(exec_config.venue): exec_config},
        data_clients=data_clients or {},
    )


def run_paper(
    spec: RunSpec,
    *,
    venue: str = "SANDBOX",
    currency: str = "USD",
    data_clients: dict[str, Any] | None = None,
    trader_id: str = "PAPER-001",
) -> None:
    """Run ``spec``'s strategy on a live paper node (sandbox fills + a live data feed).

    Builds the node config up front (verified offline). The live run requires a market-data client
    + credentials + network: pass ``data_clients`` with a nautilus live adapter config. Until then
    this fails loud (``AlphaError``) rather than silently doing nothing — paper trading's live feed
    is the one piece the spec defers post-v1 (see README 'Paper trading').
    """
    exec_config = build_sandbox_exec_config(
        venue=venue,
        account_type=spec.account_type,
        starting_cash=spec.starting_cash,
        currency=currency,
    )
    node_config = build_paper_node_config(
        trader_id=trader_id, exec_config=exec_config, data_clients=data_clients
    )
    if not data_clients:
        raise AlphaError(
            "paper trading is wired to the SandboxExecutionClient (backtest-parity fills) but "
            "needs a live market-data client to run: pass `data_clients` with a nautilus live "
            "adapter config (e.g. Binance/Bybit testnet) + credentials, on a host with network. "
            "See README 'Paper trading'."
        )
    # Network/credential-bound and not exercised offline / in CI (the spec defers Phase 4 live).
    from nautilus_trader.live.node import TradingNode

    node = TradingNode(config=node_config)
    node.build()
    try:
        node.run()
    finally:
        node.dispose()
