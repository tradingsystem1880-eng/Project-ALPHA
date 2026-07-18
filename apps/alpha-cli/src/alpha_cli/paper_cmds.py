"""``alpha paper`` — Phase-4 paper trading on a nautilus sandbox execution venue.

``preflight`` validates the whole paper setup offline: it builds the sandbox execution config + the
trading-node config and constructs the *same* strategy a backtest would (backtest↔paper parity),
then reports the one remaining step — wiring a live market-data adapter + credentials — which needs
network and is the piece the spec defers post-v1.
"""

from __future__ import annotations

import typer

from alpha_cli import _paper, _runner, _strategies
from alpha_core import DataError
from alpha_core.config import AlphaSettings

paper_app = typer.Typer(
    help="Paper trading (Phase 4): sandbox execution venue with backtest parity."
)


@paper_app.command()
def preflight(
    symbol: str,
    strategy: str = "ts_momentum",
    venue: str = "SANDBOX",
    account_type: str = "CASH",
    starting_cash: float = 1_000_000.0,
    currency: str = "USD",
    param: list[str] | None = None,
) -> None:
    """Validate the paper-trading wiring for SYMBOL and report what's needed to go live.

    Builds the sandbox exec + node configs and the parity strategy (the same class a backtest runs)
    — all offline-verifiable. Fails loud on an unknown strategy or a malformed config.
    """
    _ = AlphaSettings()  # surfaces a bad ALPHA_* env early
    if strategy not in _strategies.known_strategies():
        raise typer.BadParameter(
            f"unknown strategy {strategy!r}; known: {_strategies.known_strategies()}"
        )
    spec = _runner.RunSpec(
        lookback=252,
        skip=21,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=21,
        max_leverage=1.0,
        allow_short=account_type == "MARGIN",
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=starting_cash,
        account_type=account_type,
        train_size=504,
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=strategy,
        strategy_params=_runner.parse_strategy_params(strategy, param),
    )

    try:
        exec_config = _paper.build_sandbox_exec_config(
            venue=venue, account_type=account_type, starting_cash=starting_cash, currency=currency
        )
        node_config = _paper.build_paper_node_config(trader_id="PAPER-001", exec_config=exec_config)
        # parity: construct the SAME strategy a backtest would run (lazy nautilus instrument wiring)
        from alpha_backtest.feed import daily_bar_type
        from alpha_backtest.instruments import equity_instrument

        instrument = equity_instrument(symbol)
        strat = _strategies.build_strategy(spec, instrument.id, daily_bar_type(symbol))
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"paper preflight OK for {symbol} [{strategy}]:\n"
        f"  exec venue: {venue} ({account_type}, {starting_cash:.0f} {currency}), "
        f"backtest-parity fills (bar_execution=False)\n"
        f"  node: trader_id={node_config.trader_id}, "
        f"exec_clients={list(node_config.exec_clients)}\n"
        f"  strategy: {type(strat).__name__} constructed (same class as backtest)\n"
        f"  NEXT (live): supply a nautilus market-data adapter + credentials as data_clients on a "
        f"networked host, then call alpha_cli._paper.run_paper(...). See README 'Paper trading'."
    )
