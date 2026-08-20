"""Trusted local CLI ceremonies for Workstation owner authentication."""

from __future__ import annotations

import json

import typer

from alpha_cli.owner_auth import issue_enrollment
from alpha_core import DataError
from alpha_core.config import AlphaSettings

owner_auth_app = typer.Typer(help="Enroll or recover the local Touch ID owner credential.")


def _issue(reason: str, *, replace_existing: bool, json_out: bool) -> None:
    try:
        result = issue_enrollment(
            data_dir=AlphaSettings().data_dir,
            reason=reason,
            replace_existing=replace_existing,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(result, sort_keys=True))
        return
    typer.echo("Open this short-lived local URL to enroll Touch ID:")
    typer.echo(str(result["url"]))
    typer.echo(f"Expires at {result['expires_at']}")


@owner_auth_app.command("enroll")
def enroll(
    reason: str = typer.Option(..., help="append-only reason for this enrollment"),
    replace_existing: bool = typer.Option(
        False,
        "--replace-existing",
        help="trusted recovery ceremony that revokes the active credential after enrollment",
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Issue a short-lived localhost registration URL; browser enrollment cannot self-start."""
    _issue(reason, replace_existing=replace_existing, json_out=json_out)


@owner_auth_app.command("recover")
def recover(
    reason: str = typer.Option(..., help="append-only recovery reason"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Begin a trusted credential-replacement ceremony without weakening browser authority."""
    _issue(reason, replace_existing=True, json_out=json_out)


__all__ = ["owner_auth_app"]
