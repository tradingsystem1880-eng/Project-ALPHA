"""Workflow 1, data: bars in (offline) -> snapshot -> verify -> read bars back as of a date."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.smoke._harness import alpha
from tests.smoke.conftest import SNAPSHOT

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]


def test_snapshot_verifies_and_reads_back_as_of_a_date(data_home: Path) -> None:
    listed = alpha(data_home, "data", "snapshots", "--json").json()
    (snapshot,) = [s for s in listed["snapshots"] if s["snapshot_id"] == SNAPSHOT]
    assert snapshot["symbols"] == ["SPY"]
    assert len(snapshot["manifest_sha256"]) == 64

    assert "integrity OK" in alpha(data_home, "data", "verify", SNAPSHOT).stdout

    full = alpha(data_home, "data", "candles", "SPY", "--snapshot", SNAPSHOT, "--json").json()
    as_of = alpha(
        data_home, "data", "candles", "SPY", "--end", "2020-06-30", "--snapshot", SNAPSHOT, "--json"
    ).json()
    assert as_of["snapshot_id"] == SNAPSHOT
    assert as_of["provenance"]["knowledge_cutoff"].startswith("2020-06-30")
    last = datetime.fromtimestamp(as_of["bars"][-1]["t"], tz=UTC)
    assert last.date().isoformat() == "2020-06-30"  # the as-of day itself, nothing later
    assert 0 < len(as_of["bars"]) < len(full["bars"]) == 400
    assert as_of["bars"] == full["bars"][: len(as_of["bars"])]


def test_data_pull_offline() -> None:
    pytest.skip(
        "no public offline price source: every `alpha data pull --source` (yfinance, stooq, "
        "tiingo, ccxt) needs the network and none accepts a recorded response, so the smoke "
        "seeds the store with tests.fixtures.cli_fixtures.seed_store instead"
    )
