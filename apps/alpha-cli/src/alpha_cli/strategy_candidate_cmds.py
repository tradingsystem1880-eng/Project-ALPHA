"""Explicit sandbox-only development-candidate commands."""

from __future__ import annotations

import json

import typer

from alpha_cli.strategy_candidate import hedged_basis_paper_preflight

strategy_candidate_app = typer.Typer(
    help="Sandbox-only multi-leg candidate evaluation; no paper or order authority."
)


@strategy_candidate_app.command("paper-preflight")
def paper_preflight(json_out: bool = typer.Option(False, "--json")) -> None:
    """Report the permanent unsupported multi-venue paper boundary without connecting."""
    result = hedged_basis_paper_preflight()
    if json_out:
        typer.echo(json.dumps(result, sort_keys=True, allow_nan=False))
        return
    typer.echo(
        f"{result['code']}: deterministic sandbox evaluation remains available; "
        "no broker connection or order was attempted."
    )


__all__ = ["strategy_candidate_app"]
