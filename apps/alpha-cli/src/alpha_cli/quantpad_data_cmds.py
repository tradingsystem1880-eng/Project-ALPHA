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


def _bounds(
    start: str | None, end: str | None, start_ms: int | None, end_ms: int | None
) -> tuple[int | None, int | None]:
    has_dates = start is not None or end is not None
    has_epoch = start_ms is not None or end_ms is not None
    if has_dates and has_epoch:
        raise DataError("use either --start/--end or --start-ms/--end-ms, not both")
    if not has_dates and not has_epoch:
        return None, None
    if has_dates:
        if start is None or end is None:
            raise DataError("QuantPad archive requires both --start and --end")
        return _epoch_ms(start), _epoch_ms(end)
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        raise DataError("QuantPad archive requires ordered --start-ms and --end-ms")
    return start_ms, end_ms


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
    start_ms: int | None = typer.Option(None, "--start-ms"),
    end_ms: int | None = typer.Option(None, "--end-ms"),
    timeframe: str | None = typer.Option(None, "--timeframe"),
    schema: str | None = typer.Option(None, "--schema"),
    response_format: str | None = typer.Option(None, "--format"),
    compression: str = typer.Option("none", "--compression"),
    roll_adjust: str = typer.Option("none", "--roll-adjust"),
    asset_class: str | None = typer.Option(None, "--asset-class"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Archive one explicit provider response; it remains research-only."""
    selected_format = response_format or (
        "json" if endpoint in {"coverage", "universe"} else "csv" if endpoint == "bars" else "arrow"
    )
    try:
        requested_start_ms, requested_end_ms = _bounds(start, end, start_ms, end_ms)
        request = QuantPadArchiveRequestV1(
            endpoint=endpoint,
            symbol=symbol,
            start_ms=requested_start_ms,
            end_ms=requested_end_ms,
            timeframe=timeframe,
            schema=schema,
            response_format=selected_format,
            compression=compression,
            roll_adjust=roll_adjust,
            asset_class=asset_class,
            limit=50 if endpoint == "universe" else None,
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
