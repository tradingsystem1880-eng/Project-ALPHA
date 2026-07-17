"""``alpha screener`` — quotes & news via finnhub (opt-in; needs ``ALPHA_FINNHUB_API_KEY``).

The live fetch is network-bound and key-gated; without the key each command fails loud with setup
instructions rather than degrading silently.
"""

from __future__ import annotations

import dataclasses
import json

import typer

from alpha_core import DataError

screener_app = typer.Typer(help="Screener & news via finnhub (opt-in, API-key-gated).")


@screener_app.command()
def quote(symbol: str, json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """A real-time-ish quote for SYMBOL."""
    from alpha_screener.finnhub import fetch_quote

    try:
        q = fetch_quote(symbol)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(dataclasses.asdict(q)))
        return
    typer.echo(f"{q.symbol}: {q.current} ({q.percent_change:+.2f}%)")


@screener_app.command()
def news(
    symbol: str,
    days: int = typer.Option(7, help="trailing window in days"),
    limit: int = typer.Option(20, help="max headlines"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Recent company news for SYMBOL."""
    from alpha_screener.finnhub import fetch_news

    try:
        items = fetch_news(symbol, days=days, limit=limit)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = {"symbol": symbol, "items": [dataclasses.asdict(i) for i in items]}
    if json_out:
        typer.echo(json.dumps(payload))
        return
    for item in items:
        typer.echo(f"- {item.headline} ({item.source})")
