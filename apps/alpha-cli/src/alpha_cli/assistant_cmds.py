"""CLI ownership of advisory assistant sessions and bounded Codex turns."""

from __future__ import annotations

import json

import typer
from pydantic import ValidationError

from alpha_cli.assistant_contracts import AssistantContext, AssistantTurnRequest
from alpha_cli.assistant_runtime import readiness as check_readiness
from alpha_cli.assistant_service import create_session, get_session, run_turn
from alpha_core import DataError
from alpha_core.config import AlphaSettings

assistant_app = typer.Typer(
    help="Advisory assistant; no evidence admission or execution authority."
)


@assistant_app.command("readiness")
def readiness(json_out: bool = typer.Option(False, "--json")) -> None:
    del json_out
    typer.echo(json.dumps(check_readiness()))


@assistant_app.command("create")
def create(
    context: str = typer.Option(..., "--context"), json_out: bool = typer.Option(False, "--json")
) -> None:
    del json_out
    try:
        result = create_session(
            AlphaSettings().data_dir, AssistantContext.model_validate_json(context)
        )
    except (ValueError, OSError, ValidationError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result))


@assistant_app.command("show")
def show(session_id: str, json_out: bool = typer.Option(False, "--json")) -> None:
    del json_out
    try:
        result = get_session(AlphaSettings().data_dir, session_id)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result))


@assistant_app.command("turn")
def turn(
    session_id: str,
    request: str = typer.Option(..., "--request"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    del json_out
    try:
        result = run_turn(
            AlphaSettings().data_dir, session_id, AssistantTurnRequest.model_validate_json(request)
        )
    except (ValueError, OSError, ValidationError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result))
    if result["turns"][-1]["status"] != "completed":
        raise typer.Exit(1)


@assistant_app.command("check")
def check(session_id: str, json_out: bool = typer.Option(False, "--json")) -> None:
    from alpha_cli.assistant_service import check_session

    del json_out
    try:
        result = check_session(AlphaSettings().data_dir, session_id)
    except (ValueError, OSError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result))
