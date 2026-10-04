"""Closed workstation commands over managed investigation identities."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

import typer
from pydantic import BaseModel

from alpha_cli import investigation_workspace as workspace
from alpha_cli import investigation_workspace_data as comparisons
from alpha_cli.investigation_workspace_contracts import (
    ComparisonAcquireRequest,
    ComparisonDraftRequest,
    InvestigationCreate,
    InvestigationTurnRequest,
)
from alpha_core import DataError
from alpha_core.config import AlphaSettings

app = typer.Typer(help="Managed advisory investigations for recorded runs.", no_args_is_help=True)


def _request[Model: BaseModel](text: str, model: type[Model]) -> Model:
    if len(text.encode()) > 65536:
        raise ValueError("Investigation request exceeds 64 KiB")
    return model.model_validate_json(text)


def _emit(
    operation: Callable[[], Any], *, fail_status: Literal["run", "acquire"] | None = None
) -> None:
    try:
        value = operation()
    except (DataError, ValueError, RuntimeError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if not isinstance(value, BaseModel):
        typer.echo(json.dumps([item.model_dump(mode="json") for item in value]))
        return
    typer.echo(value.model_dump_json())
    if fail_status is not None:
        failed = bool(getattr(value, "error", None))
        if fail_status == "run":
            failed |= getattr(value, "status", None) in {"failed", "interrupted", "blocked"}
        else:
            failed |= getattr(value, "acquisition_status", None) != "succeeded"
            failed |= getattr(value, "comparison_child_id", None) is None
        if failed:
            raise typer.Exit(1)


@app.command("eligibility")
def eligibility(run_id: str) -> None:
    _emit(lambda: workspace.eligibility(AlphaSettings().data_dir, run_id))


@app.command("list")
def list_cases(run_id: str = typer.Option(..., "--run-id")) -> None:
    _emit(lambda: workspace.list_cases(AlphaSettings().data_dir, run_id))


@app.command("create")
def create(request: str = typer.Option(..., "--request")) -> None:
    _emit(
        lambda: workspace.create(AlphaSettings().data_dir, _request(request, InvestigationCreate))
    )


@app.command("show")
def show(identifier: str) -> None:
    _emit(lambda: workspace.show(AlphaSettings().data_dir, identifier))


@app.command("run")
def run(identifier: str, request: str = typer.Option("{}", "--request")) -> None:
    _emit(
        lambda: workspace.run(
            AlphaSettings().data_dir, identifier, _request(request, InvestigationTurnRequest)
        ),
        fail_status="run",
    )


@app.command("draft")
def draft(identifier: str, request: str = typer.Option(..., "--request")) -> None:
    _emit(
        lambda: comparisons.draft(
            AlphaSettings().data_dir, identifier, _request(request, ComparisonDraftRequest)
        )
    )


@app.command("acquire")
def acquire(identifier: str, request: str = typer.Option(..., "--request")) -> None:
    _emit(
        lambda: comparisons.acquire(
            AlphaSettings().data_dir, identifier, _request(request, ComparisonAcquireRequest)
        ),
        fail_status="acquire",
    )
