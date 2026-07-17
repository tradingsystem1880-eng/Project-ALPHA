"""``alpha options`` — Black-Scholes pricing, greeks, implied vol (JSON projections for the UI).

These are point-in-time calculators (no market data, no look-ahead surface, no run artifacts) —
just the `alpha_options` primitives exposed as `--json` for the Workstation's Options panel.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import typer

from alpha_core import DataError
from alpha_options import bs_greeks, implied_vol

options_app = typer.Typer(help="Options & derivatives analytics (Black-Scholes).")


def _greeks_row(
    spot: float, strike: float, rate: float, vol: float, days: float, kind: str
) -> dict[str, Any]:
    greeks = bs_greeks(spot, strike, rate, vol, days / 365.0, kind)
    return {
        "spot": spot,
        "strike": strike,
        "rate": rate,
        "vol": vol,
        "days": days,
        "kind": kind,
        **dataclasses.asdict(greeks),
    }


@options_app.command()
def greeks(
    spot: float,
    strike: float,
    vol: float = typer.Option(..., help="annualized volatility (e.g. 0.2)"),
    days: float = typer.Option(30.0, help="calendar days to expiry"),
    rate: float = typer.Option(0.05, help="risk-free rate"),
    kind: str = typer.Option("call", help="call|put"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Price + delta/gamma/vega/theta/rho for one European option."""
    try:
        row = _greeks_row(spot, strike, rate, vol, days, kind)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(row))
        return
    for key in ("price", "delta", "gamma", "vega", "theta", "rho"):
        typer.echo(f"{key:>6}: {row[key]:.6f}")


@options_app.command()
def iv(
    spot: float,
    strike: float,
    price: float = typer.Option(..., help="observed option price"),
    days: float = typer.Option(30.0),
    rate: float = typer.Option(0.05),
    kind: str = typer.Option("call", help="call|put"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """The volatility that reprices the option to the observed price (+ greeks at that vol)."""
    try:
        vol = implied_vol(price, spot, strike, rate, days / 365.0, kind)
        row = _greeks_row(spot, strike, rate, vol, days, kind)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    row["implied_vol"] = vol
    row["market_price"] = price
    if json_out:
        typer.echo(json.dumps(row))
        return
    typer.echo(f"implied_vol: {vol:.6f}")


@options_app.command()
def curve(
    strike: float,
    vol: float = typer.Option(..., help="annualized volatility"),
    days: float = typer.Option(30.0),
    rate: float = typer.Option(0.05),
    kind: str = typer.Option("call", help="call|put"),
    width: float = typer.Option(0.5, help="spot range = strike*(1±width)"),
    points: int = typer.Option(41, help="samples across the range"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Price + greeks across a range of spot prices (for the greeks-vs-spot chart)."""
    if points < 2:
        raise typer.BadParameter("points must be >= 2")
    lo = max(strike * (1.0 - width), strike * 0.01)  # keep every sampled spot strictly positive
    hi = strike * (1.0 + width)
    step = (hi - lo) / (points - 1)
    rows: list[dict[str, Any]] = []
    try:
        for i in range(points):
            spot = lo + i * step
            greeks = bs_greeks(spot, strike, rate, vol, days / 365.0, kind)
            rows.append(
                {
                    "spot": spot,
                    "price": greeks.price,
                    "delta": greeks.delta,
                    "gamma": greeks.gamma,
                    "vega": greeks.vega,
                    "theta": greeks.theta,
                }
            )
    except DataError as exc:  # bad vol/days/rate/kind — surface it, don't emit a partial curve
        raise typer.BadParameter(str(exc)) from exc
    payload = {
        "strike": strike,
        "vol": vol,
        "days": days,
        "rate": rate,
        "kind": kind,
        "points": rows,
    }
    if json_out:
        typer.echo(json.dumps(payload))
        return
    typer.echo(f"{len(rows)} points across [{lo:.2f}, {hi:.2f}]")
