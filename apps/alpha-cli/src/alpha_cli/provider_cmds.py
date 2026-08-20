"""Explicit provider verification commands; status reads never probe the network."""

from __future__ import annotations

import json

import typer

from alpha_cli import provider_readiness
from alpha_core import DataError
from alpha_core.config import AlphaSettings

provider_app = typer.Typer(help="Explicit, receipted provider readiness checks.")


@provider_app.command("check")
def check(
    provider_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit the redacted receipt as JSON"),
) -> None:
    """Run one bounded check. Merely listing or refreshing providers never calls this command."""
    try:
        receipt = provider_readiness.run_explicit_check(AlphaSettings().data_dir, provider_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        json.dumps(receipt, sort_keys=True, allow_nan=False)
        if json_out
        else (
            f"{receipt['provider_id']}: {receipt['verification_state']} "
            f"({receipt['checked_at']}); {receipt['recovery_action']}"
        )
    )


__all__ = ["provider_app"]
