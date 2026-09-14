"""DefiLlama chain TVL provider (ADR-0036): closed URL, fail-loud parser, availability lag."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_data.crypto.capabilities import project_provider_capabilities
from alpha_data.crypto.contracts import FAMILY_AUTHORITIES
from alpha_data.crypto.providers.defillama import (
    check_chain_tvl,
    defillama_url,
    fetch_defillama,
    parse_chain_tvl,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "defillama" / "ethereum_chain_tvl.json"


def test_family_is_registered_with_defillama_as_its_only_authority() -> None:
    assert FAMILY_AUTHORITIES["defi_tvl"] == "defillama"
    capability = next(c for c in project_provider_capabilities(()) if c.family == "defi_tvl")
    assert capability.provider == "defillama"
    assert capability.frequencies == ("1d",)
    assert capability.authentication == "none"


def test_url_is_closed_to_one_endpoint_and_valid_chain_names() -> None:
    assert defillama_url("chain_tvl", chain="ethereum") == (
        "https://api.llama.fi/v2/historicalChainTvl/ethereum"
    )
    with pytest.raises(DataError, match=r"^DefiLlama endpoint 'protocols' is not registered$"):
        defillama_url("protocols", chain="ethereum")
    for bad in ("", "Ethereum", "eth/../x", "a" * 65):
        with pytest.raises(DataError, match=r"^DefiLlama chain identifier is invalid$"):
            defillama_url("chain_tvl", chain=bad)
    with pytest.raises(DataError, match=r"^DefiLlama request host is invalid$"):
        fetch_defillama("https://evil.example/v2/historicalChainTvl/ethereum")
    with pytest.raises(DataError, match=r"^DefiLlama timeout must be between 1 and 60 seconds$"):
        fetch_defillama(defillama_url("chain_tvl", chain="ethereum"), timeout_seconds=0)


def test_parser_emits_day_rows_with_next_day_availability() -> None:
    frame = parse_chain_tvl(FIXTURE.read_bytes(), chain="ethereum")
    assert frame.columns == ["chain", "observed_at", "tvl_usd", "available_at"]
    assert frame.height == 4 and frame["chain"].unique().to_list() == ["ethereum"]
    first = frame.row(0, named=True)
    assert first["observed_at"] == datetime(2024, 1, 1, tzinfo=UTC)
    assert first["available_at"] == datetime(2024, 1, 2, tzinfo=UTC)
    assert first["tvl_usd"] == pytest.approx(28123456789.5)
    assert (frame["available_at"] - frame["observed_at"]).unique().to_list() == [timedelta(days=1)]
    assert frame["observed_at"].is_sorted()
    summary = check_chain_tvl(FIXTURE.read_bytes(), chain="ethereum")
    assert summary == {
        "chain": "ethereum",
        "rows": 4,
        "last_observed_at": datetime(2024, 1, 4, tzinfo=UTC),
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"not json", r"^DefiLlama payload is not JSON$"),
        (b"[]", r"^DefiLlama chain TVL payload must be a non-empty list$"),
        (
            b'{"date": 1704067200, "tvl": 1.0}',
            r"^DefiLlama chain TVL payload must be a non-empty list$",
        ),
        (b'[{"date": 1704067200}]', r"^DefiLlama chain TVL row must carry exactly date and tvl$"),
        (
            b'[{"date": 1704067200, "tvl": 1.0, "x": 1}]',
            r"^DefiLlama chain TVL row must carry exactly date and tvl$",
        ),
        (b'[{"date": "x", "tvl": 1.0}]', r"^DefiLlama TVL date is invalid$"),
        (b'[{"date": 1704067200.5, "tvl": 1.0}]', r"^DefiLlama TVL date must be whole seconds$"),
        (
            b'[{"date": 1704067260, "tvl": 1.0}]',
            r"^DefiLlama TVL date must fall on a UTC day boundary$",
        ),
        (
            b'[{"date": 1704067200000, "tvl": 1.0}]',
            r"^DefiLlama TVL date is outside the supported range$",
        ),
        (b'[{"date": 1704067200, "tvl": "1.0"}]', r"^DefiLlama TVL value is invalid$"),
        (b'[{"date": 1704067200, "tvl": -1.0}]', r"^DefiLlama TVL value is negative$"),
        (
            b'[{"date": 1704153600, "tvl": 1.0}, {"date": 1704067200, "tvl": 2.0}]',
            r"^DefiLlama chain TVL rows must be strictly increasing by day$",
        ),
        (
            b'[{"date": 1704067200, "tvl": 1.0}, {"date": 1704067200, "tvl": 2.0}]',
            r"^DefiLlama chain TVL rows must be strictly increasing by day$",
        ),
    ],
)
def test_parser_fails_loud_on_malformed_payloads(payload: bytes, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_chain_tvl(payload, chain="ethereum")
    with pytest.raises(DataError, match=r"^DefiLlama chain identifier is invalid$"):
        parse_chain_tvl(FIXTURE.read_bytes(), chain="Ethereum")


def test_fixture_is_the_documented_wire_shape() -> None:
    rows = json.loads(FIXTURE.read_text())
    assert all(set(row) == {"date", "tvl"} for row in rows)
    assert all(row["date"] % 86_400 == 0 for row in rows)
