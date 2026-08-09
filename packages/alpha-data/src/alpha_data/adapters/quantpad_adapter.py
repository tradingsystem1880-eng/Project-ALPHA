"""QuantPad research-only bulk adapter sub-slice (ADR-0018, ADR-0023).

Daily bars via the official ``https://api.quantpad.ai`` REST API only — never scraping,
never nonpublic endpoints. Output is **research scratch** with a content-bound receipt:
it can be registered as a ``research_only`` dataset ref, and it can NEVER enter the
canonical store, a validation snapshot, a strategy evidence claim, or paper readiness
until the full qualification suite exists. The wire schema is pinned; any provider
drift fails loud with an explicit qualification message instead of guessing.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

import polars as pl

from alpha_core import DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt, FetchResult

QUANTPAD_BASE_URL: Final = "https://api.quantpad.ai"
_EXPECTED_SCHEMA_VERSION: Final = 1
_BAR_FIELDS: Final = ("t", "o", "h", "l", "c", "v")


def _drift(detail: str) -> DataError:
    return DataError(
        "QuantPad wire schema drift: "
        + detail
        + " — qualify the adapter against the current official API before using its output"
    )


def parse_quantpad_bars(payload: bytes, symbol: str) -> FetchResult:
    """Pure parser for the pinned QuantPad daily-bar wire schema (UTC, ordered, unique)."""
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _drift("response is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise _drift("response is not a JSON object")
    if decoded.get("schema_version") != _EXPECTED_SCHEMA_VERSION:
        raise _drift(
            f"schema_version {decoded.get('schema_version')!r} != {_EXPECTED_SCHEMA_VERSION}"
        )
    if decoded.get("interval") != "1d":
        raise _drift(f"interval {decoded.get('interval')!r}; this sub-slice is daily-only")
    rows = decoded.get("bars")
    if not isinstance(rows, list):
        raise _drift("bars is not a list")
    if not rows:
        raise DataError(f"QuantPad returned no bars for {symbol!r} in the requested range")
    timestamps: list[datetime] = []
    records: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict) or any(field not in row for field in _BAR_FIELDS):
            raise _drift(f"bar rows must carry exactly the {_BAR_FIELDS} fields")
        try:
            stamp = datetime.fromisoformat(str(row["t"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise _drift(f"bar timestamp {row['t']!r} is not ISO-8601") from exc
        if stamp.tzinfo is None or stamp.utcoffset() != UTC.utcoffset(None):
            raise _drift(f"bar timestamp {row['t']!r} is not UTC")
        values = {}
        for source, target in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close")):
            value = row[source]
            if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
                raise _drift(f"bar field {source!r} is not a positive number")
            values[target] = float(value)
        volume = row["v"]
        if isinstance(volume, bool) or not isinstance(volume, int | float) or volume < 0:
            raise _drift("bar field 'v' is not a non-negative number")
        timestamps.append(stamp)
        records.append({"ts": stamp, **values, "volume": float(volume)})
    for previous, current in zip(timestamps, timestamps[1:], strict=False):
        if current <= previous:
            raise DataError(
                f"QuantPad bars for {symbol!r} are not strictly ordered unique timestamps"
            )
    identity = DatasetIdentity(
        symbol=symbol,
        provider="quantpad",
        provider_symbol=str(decoded.get("symbol", symbol)),
        venue="QUANTPAD",
        asset_class="stock",
        timeframe="1D",
        calendar="XNYS",
        currency="USD",
        price_basis="raw",
    )
    frame = pl.DataFrame(records).sort("ts")
    return FetchResult(symbol=symbol, bars=frame, actions=[], identity=identity)


class QuantPadAdapter:
    """Official-REST daily-bar adapter; research authority only, never canonical."""

    name = "quantpad"
    version = "1"
    parser_version = "1"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        api_key = os.environ.get("QUANTPAD_API_KEY", "")
        if not api_key:
            raise DataError(
                "QuantPad fetch requires QUANTPAD_API_KEY (macOS keychain service "
                "'project-alpha-quantpad'); the adapter never embeds credentials"
            )
        url = (
            f"{QUANTPAD_BASE_URL}/v1/bars?symbol={urllib.parse.quote(symbol)}"
            f"&interval=1d&start={start.isoformat()}&end={end.isoformat()}"
        )
        request = urllib.request.Request(  # noqa: S310 - pinned https host per ADR-0018
            url, headers={"Authorization": f"Bearer {api_key}"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                raw = response.read()
                rate_limit = {
                    name.lower(): value
                    for name, value in response.headers.items()
                    if name.lower().startswith("x-ratelimit")
                }
        except OSError as exc:
            raise DataError(f"QuantPad request failed for {symbol!r}: {exc}") from exc
        result = parse_quantpad_bars(raw, symbol)
        if result.identity is None:  # pragma: no cover - parser always sets identity
            raise DataError("QuantPad parser returned no dataset identity")
        receipt = FetchReceipt.create(
            identity=result.identity,
            requested_start=start,
            requested_end=end,
            fetched_at=datetime.now(tz=UTC),
            adapter_version=self.version,
            parser_version=self.parser_version,
            response_sha256=hashlib.sha256(raw).hexdigest(),
            response_bytes=len(raw),
            row_count=result.bars.height,
            action_count=0,
            request_metadata={"endpoint": "/v1/bars", "interval": "1d", **rate_limit},
        )
        return FetchResult(
            symbol=symbol,
            bars=result.bars,
            actions=[],
            identity=result.identity,
            receipt=receipt,
            raw_response=raw,
        )


def persist_research_fetch(result: FetchResult, root: Path) -> dict[str, Path]:
    """Write receipted research scratch output (bars + receipt) for dataset registration."""
    if result.receipt is None or result.identity is None:
        raise DataError("research persistence requires a receipted, identified fetch result")
    target = Path(root) / result.receipt.receipt_id
    target.mkdir(parents=True, exist_ok=True)
    bars_path = target / "bars.parquet"
    result.bars.write_parquet(bars_path)
    receipt_path = target / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                **result.receipt.to_dict(),
                "dataset": result.identity.to_dict(),
                "symbol": result.symbol,
                "research_only": True,
            },
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    return {"bars_path": bars_path, "receipt_path": receipt_path}


__all__ = [
    "QUANTPAD_BASE_URL",
    "QuantPadAdapter",
    "parse_quantpad_bars",
    "persist_research_fetch",
]
