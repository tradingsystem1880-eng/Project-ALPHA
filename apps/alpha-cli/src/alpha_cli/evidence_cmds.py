"""``alpha evidence`` — append-only, point-in-time research evidence projections."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

import typer

from alpha_cli.control_store import (
    AuthorKind,
    ControlStore,
    EvidenceStatus,
    parse_timestamp,
)
from alpha_core import DataError
from alpha_core.config import AlphaSettings

evidence_app = typer.Typer(help="Append-only cited findings and negative-result memory.")


def _store() -> ControlStore:
    return ControlStore(AlphaSettings().data_dir)


def _object(raw: str, label: str) -> Mapping[str, object]:
    try:
        value: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{label} must be a valid JSON object") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise typer.BadParameter(f"{label} must be a valid JSON object")
    return cast(dict[str, object], value)


def _emit(value: object, *, json_out: bool, fallback: str) -> None:
    if json_out:
        typer.echo(json.dumps(value, sort_keys=True, allow_nan=False))
    else:
        typer.echo(fallback)


@evidence_app.command("add")
def add(
    claim: str,
    assets: str = typer.Option(..., help="comma-separated symbols"),
    frozen_universe: str = typer.Option(..., help="comma-separated frozen research universe"),
    method: str = typer.Option(..., help="method that produced the finding"),
    knowledge_at: str = typer.Option(..., help="UTC timestamp when evidence became knowable"),
    author: str = typer.Option(...),
    author_kind: str = typer.Option(..., help="human|agent"),
    timeframe: str = typer.Option("1d"),
    market_data_cutoff: str | None = typer.Option(None),
    project_id: str | None = typer.Option(None),
    strategy_version_id: str | None = typer.Option(None),
    experiment_id: str | None = typer.Option(None),
    metric_name: str | None = typer.Option(None),
    metric_value: float | None = typer.Option(None),
    metric_unit: str | None = typer.Option(None),
    source_run_id: str = typer.Option(...),
    source_artifact: str = typer.Option(...),
    source_field: str = typer.Option(...),
    row_selector_json: str = typer.Option("{}"),
    counterevidence: list[str] | None = None,
    contradiction_id: list[str] | None = None,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Create a draft evidence record; agent-created findings cannot skip review."""
    symbols = [item.strip() for item in assets.split(",") if item.strip()]
    universe = [item.strip() for item in frozen_universe.split(",") if item.strip()]
    try:
        row = _store().create_evidence(
            claim=claim,
            assets=symbols,
            frozen_universe=universe,
            timeframe=timeframe,
            method=method,
            knowledge_at=parse_timestamp(knowledge_at, "knowledge_at"),
            market_data_cutoff=(
                None
                if market_data_cutoff is None
                else parse_timestamp(market_data_cutoff, "market_data_cutoff")
            ),
            author=author,
            author_kind=cast(AuthorKind, author_kind),
            project_id=project_id,
            strategy_version_id=strategy_version_id,
            experiment_id=experiment_id,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            source_run_id=source_run_id,
            source_artifact=source_artifact,
            source_field=source_field,
            row_selector=_object(row_selector_json, "--row-selector-json"),
            counterevidence=counterevidence or (),
            contradiction_ids=contradiction_id or (),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"draft evidence {row['evidence_id']}")


@evidence_app.command("revise")
def revise(
    evidence_id: str,
    status: str = typer.Option(..., help="draft|corroborated|rejected|superseded"),
    author: str = typer.Option(...),
    author_kind: str = typer.Option(..., help="human|agent"),
    claim: str | None = typer.Option(None),
    counterevidence: list[str] | None = None,
    contradiction_id: list[str] | None = None,
    source_run_id: str | None = typer.Option(None),
    source_artifact: str | None = typer.Option(None),
    source_field: str | None = typer.Option(None),
    row_selector_json: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Append a reviewed evidence revision without mutating its history."""
    try:
        row = _store().revise_evidence(
            evidence_id,
            status=cast(EvidenceStatus, status),
            author=author,
            author_kind=cast(AuthorKind, author_kind),
            claim=claim,
            counterevidence=counterevidence,
            contradiction_ids=contradiction_id,
            source_run_id=source_run_id,
            source_artifact=source_artifact,
            source_field=source_field,
            row_selector=(
                None
                if row_selector_json is None
                else _object(row_selector_json, "--row-selector-json")
            ),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        row,
        json_out=json_out,
        fallback=f"evidence {evidence_id} revision {row['revision']} {row['status']}",
    )


@evidence_app.command("show")
def show(
    evidence_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show current evidence plus immutable revision history."""
    try:
        row = _store().get_evidence(evidence_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"{row['status']} {row['claim']}")


@evidence_app.command("list")
def list_evidence(
    asset: str | None = typer.Option(None),
    project_id: str | None = typer.Option(None),
    status: str | None = typer.Option(None),
    as_of: str | None = typer.Option(None, help="point-in-time UTC knowledge cutoff"),
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List current or point-in-time evidence projections."""
    try:
        rows = _store().list_evidence(
            asset=asset,
            project_id=project_id,
            status=None if status is None else cast(EvidenceStatus, status),
            as_of=None if as_of is None else parse_timestamp(as_of, "as_of"),
            limit=limit,
            offset=offset,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        _emit(rows, json_out=True, fallback="")
        return
    if not rows:
        typer.echo("no evidence")
        return
    for row in rows:
        typer.echo(f"{row['evidence_id']} r{row['revision']} {row['status']} {row['claim']}")


__all__ = ["evidence_app"]
