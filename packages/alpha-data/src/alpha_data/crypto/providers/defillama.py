"""DefiLlama chain TVL ingestion (ADR-0036): the keyless `defi_tvl` family.

One bounded request per chain returns every end-of-day total-value-locked point as
``[{"date": <unix seconds>, "tvl": <usd>}, ...]``. A day's TVL is complete only after that UTC day
closes, so ``available_at`` is the next UTC day boundary — the parser owns that lag so no caller
can read a same-day value. Attribution: DefiLlama (https://defillama.com), free for
non-commercial use with attribution; raw bytes stay in the owner's private local store.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Final

import polars as pl

from alpha_core import DataError

from ._wire import epoch_ms_to_utc, fetch_bounded, finite_float

PROVIDER_ID: Final = "defillama"
ATTRIBUTION_NOTE: Final = (
    "Data: DefiLlama (https://defillama.com), free for non-commercial use with attribution"
)
RETENTION_NOTE: Final = (
    "raw bytes retained locally for the owner's private research only; "
    "never redistributed or hosted"
)
_HOST: Final = "https://api.llama.fi/"
_CHAIN: Final = re.compile(r"^[a-z0-9-]{1,64}$")
_ENDPOINTS: Final = {"chain_tvl": "/v2/historicalChainTvl/{chain}"}


def defillama_url(endpoint: str, *, chain: str) -> str:
    """The single closed endpoint URL for one chain; anything else fails loud."""
    if endpoint not in _ENDPOINTS:
        raise DataError(f"DefiLlama endpoint {endpoint!r} is not registered")
    if not _CHAIN.match(chain):
        raise DataError("DefiLlama chain identifier is invalid")
    return _HOST.rstrip("/") + _ENDPOINTS[endpoint].format(chain=chain)


def fetch_defillama(url: str, *, timeout_seconds: int = 30) -> bytes:
    """Fetch one bounded JSON response from the keyless DefiLlama host."""
    if not 1 <= timeout_seconds <= 60:
        raise DataError("DefiLlama timeout must be between 1 and 60 seconds")
    if not url.startswith(_HOST):
        raise DataError("DefiLlama request host is invalid")
    return fetch_bounded(
        url,
        provider="DefiLlama",
        host_prefix=_HOST,
        content_types=frozenset({"application/json", "text/json"}),
        max_bytes=8 * 1024 * 1024,
        timeout_seconds=timeout_seconds,
    )


def parse_chain_tvl(payload: bytes, *, chain: str) -> pl.DataFrame:
    """Rows ``chain, observed_at, tvl_usd, available_at`` sorted by day; fails loud on disorder."""
    if not _CHAIN.match(chain):
        raise DataError("DefiLlama chain identifier is invalid")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, ValueError) as exc:
        raise DataError("DefiLlama payload is not JSON") from exc
    if not isinstance(decoded, list) or not decoded:
        raise DataError("DefiLlama chain TVL payload must be a non-empty list")
    observed: list[datetime] = []
    values: list[float] = []
    for record in decoded:
        if not isinstance(record, dict) or set(record) != {"date", "tvl"}:
            raise DataError("DefiLlama chain TVL row must carry exactly date and tvl")
        seconds = finite_float(record["date"], "DefiLlama TVL date")
        if not seconds.is_integer():
            raise DataError("DefiLlama TVL date must be whole seconds")
        instant = epoch_ms_to_utc(int(seconds) * 1_000, "DefiLlama TVL date", enforce_window=True)
        if instant != instant.replace(hour=0, minute=0, second=0, microsecond=0):
            raise DataError("DefiLlama TVL date must fall on a UTC day boundary")
        tvl = finite_float(record["tvl"], "DefiLlama TVL value", allow_text=False)
        if tvl < 0.0:
            raise DataError("DefiLlama TVL value is negative")
        observed.append(instant)
        values.append(tvl)
    if any(later <= earlier for earlier, later in zip(observed[:-1], observed[1:], strict=True)):
        raise DataError("DefiLlama chain TVL rows must be strictly increasing by day")
    return pl.DataFrame(
        {
            "chain": [chain] * len(observed),
            "observed_at": observed,
            "tvl_usd": values,
            "available_at": [day + timedelta(days=1) for day in observed],
        },
        schema={
            "chain": pl.String(),
            "observed_at": pl.Datetime("us", "UTC"),
            "tvl_usd": pl.Float64(),
            "available_at": pl.Datetime("us", "UTC"),
        },
    )


def check_chain_tvl(payload: bytes, *, chain: str) -> dict[str, object]:
    """Readiness-check summary of one live response: row count and the last observed day."""
    frame = parse_chain_tvl(payload, chain=chain)
    last = frame["observed_at"][-1]
    assert isinstance(last, datetime)  # schema pins the dtype; narrows for typing
    return {"chain": chain, "rows": frame.height, "last_observed_at": last.astimezone(UTC)}


__all__ = [
    "ATTRIBUTION_NOTE",
    "PROVIDER_ID",
    "RETENTION_NOTE",
    "check_chain_tvl",
    "defillama_url",
    "fetch_defillama",
    "parse_chain_tvl",
]
