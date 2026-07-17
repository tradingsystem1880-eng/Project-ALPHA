"""``alpha research`` — quick multi-strategy comparison (the AI Research desk's engine).

Backtests each registered strategy on a symbol with default parameters and ranks them — the
"analyst lanes" the Workstation's AI Research panel renders. Composes ``_runner.run_full_backtest``
(the same engine path as ``alpha backtest``). The conversational path stays the MCP server.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings

research_app = typer.Typer(help="AI-desk research flows over the CLI (multi-strategy comparison).")


def _spec(name: str) -> Any:
    from alpha_cli import _runner

    return _runner.RunSpec(
        lookback=252,
        skip=21,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=21,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=1_000_000.0,
        account_type="MARGIN",  # avoid CASH order-rejection so the comparison reflects the signal
        train_size=504,
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=name,
    )


@research_app.command()
def compare(
    symbol: str,
    strategies: str = typer.Option("", help="comma-separated; default = all engine strategies"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Backtest each strategy on SYMBOL and rank them by total return."""
    from alpha_cli import _runner, _strategies

    names = [s.strip() for s in strategies.split(",") if s.strip()] or [
        n for n in _strategies.known_strategies() if n != "kronos_forecast"
    ]
    settings = AlphaSettings()
    try:
        bars, _ = _runner.load_bars(symbol, data_dir=settings.data_dir)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    rows: list[dict[str, Any]] = []
    for name in names:
        try:
            result = _runner.run_full_backtest(bars, _spec(name))
            total = result.final_equity / result.starting_equity - 1.0
            rows.append(
                {
                    "strategy": name,
                    "total_return": total,
                    "final_equity": result.final_equity,
                    "n_trades": len(result.trades),
                    "error": None,
                }
            )
        except DataError as exc:  # e.g. warmup exceeds the available bars — report, keep comparing
            rows.append({"strategy": name, "total_return": None, "error": str(exc)})

    rows.sort(
        key=lambda r: (r["total_return"] is not None, r.get("total_return") or 0.0), reverse=True
    )
    payload = {"symbol": symbol, "n_bars": len(bars), "ranked": rows}
    if json_out:
        typer.echo(json.dumps(payload))
        return
    for r in rows:
        if r["error"]:
            typer.echo(f"{r['strategy']:>16}: (skipped — {r['error']})")
        else:
            typer.echo(
                f"{r['strategy']:>16}: return={r['total_return']:+.4f} trades={r['n_trades']}"
            )
