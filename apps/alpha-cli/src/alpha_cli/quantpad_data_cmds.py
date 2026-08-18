"""Owner-authorized QuantPad research archive commands."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, time
from typing import Annotated

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto.storage import macos_volume_uuid
from alpha_data.quantpad_archive import (
    QuantPadArchiveRequestV1,
    QuantPadArchiveStore,
    fetch_quantpad_archive,
)

quantpad_data_app = typer.Typer(help="Archive exact QuantPad research data on pinned bulk storage.")


def _epoch_ms(value: str) -> int:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DataError("QuantPad archive dates must use YYYY-MM-DD") from exc
    return int(datetime.combine(parsed, time.min, tzinfo=UTC).timestamp() * 1_000)


def _store(settings: AlphaSettings) -> QuantPadArchiveStore:
    if not settings.bulk_volume_uuid:
        raise DataError("ALPHA_BULK_VOLUME_UUID is required for QuantPad archival")
    if (
        not settings.bulk_data_dir.is_dir()
        or macos_volume_uuid(settings.bulk_data_dir).strip().upper()
        != settings.bulk_volume_uuid.strip().upper()
    ):
        raise DataError("configured bulk volume UUID does not match before QuantPad setup")
    bulk_root = settings.bulk_data_dir.parent / "quantpad-data"
    if not bulk_root.exists():
        bulk_root.mkdir(parents=False)
    return QuantPadArchiveStore(
        bulk_root=bulk_root,
        manifest_root=settings.data_dir / "quantpad" / "manifests",
        expected_volume_uuid=settings.bulk_volume_uuid,
    )


@quantpad_data_app.command("archive")
def archive(
    endpoint: str = typer.Argument(help="bars, ticks, or coverage"),
    symbol: str = typer.Argument(help="exact QuantPad symbol"),
    start: Annotated[str | None, typer.Option("--start")] = None,
    end: Annotated[str | None, typer.Option("--end")] = None,
    timeframe: str | None = typer.Option(None, "--timeframe"),
    schema: str | None = typer.Option(None, "--schema"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Archive one explicit provider response; it remains research-only."""
    response_format = "json" if endpoint == "coverage" else "csv" if endpoint == "bars" else "arrow"
    try:
        request = QuantPadArchiveRequestV1(
            endpoint=endpoint,
            symbol=symbol,
            start_ms=_epoch_ms(start) if start is not None else None,
            end_ms=_epoch_ms(end) if end is not None else None,
            timeframe=timeframe,
            schema=schema,
            response_format=response_format,
        )
        manifest = fetch_quantpad_archive(
            _store(AlphaSettings()),
            request,
            api_key=os.environ.get("QUANTPAD_API_KEY", ""),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        json.dumps(manifest, sort_keys=True, allow_nan=False)
        if json_out
        else f"archived {endpoint} for {symbol}: {manifest['manifest_id']}"
    )


@quantpad_data_app.command("verify")
def verify(manifest_id: str, json_out: bool = typer.Option(False, "--json")) -> None:
    """Re-hash one internal manifest and its external provider bytes."""
    try:
        manifest = _store(AlphaSettings()).verify(manifest_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(manifest, sort_keys=True) if json_out else f"verified {manifest_id}")


__all__ = ["quantpad_data_app"]
