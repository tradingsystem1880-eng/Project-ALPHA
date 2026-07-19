import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from alpha_data.ingest import store_fetch_result
from alpha_data.snapshot import create_snapshot, verify_snapshot
from alpha_data.store import ParquetStore
from tests.fixtures.yf_fixtures import aapl_like

WHEN = datetime(2026, 6, 15, tzinfo=UTC)


def _store(tmp_path: Path) -> ParquetStore:
    store = ParquetStore(tmp_path / "work")
    store_fetch_result(store, parse_yfinance_history(aapl_like(), "AAPL"))
    store.write_provenance("AAPL", source="yfinance", adapter_version="1", parser_version="1")
    return store


def test_snapshot_writes_manifest_with_provenance(tmp_path: Path) -> None:
    store = _store(tmp_path)
    manifest = create_snapshot(
        store,
        tmp_path / "snaps",
        "snap1",
        ["AAPL"],
        source="yfinance",
        adapter_version="1",
        parser_version="1",
        created_at=WHEN,
    )
    assert manifest["source"] == "yfinance"
    assert manifest["adapter_version"] == "1"
    assert manifest["symbols"]["AAPL"]["bars_sha256"]
    assert manifest["symbols"]["AAPL"]["provenance_sha256"]
    assert (tmp_path / "snaps" / "snap1" / "manifest.json").exists()


def test_verify_passes_for_intact_snapshot(tmp_path: Path) -> None:
    store = _store(tmp_path)
    create_snapshot(
        store,
        tmp_path / "snaps",
        "snap1",
        ["AAPL"],
        source="yfinance",
        adapter_version="1",
        parser_version="1",
        created_at=WHEN,
    )
    verify_snapshot(tmp_path / "snaps" / "snap1")  # no raise


def test_verify_detects_tampering(tmp_path: Path) -> None:
    store = _store(tmp_path)
    create_snapshot(
        store,
        tmp_path / "snaps",
        "snap1",
        ["AAPL"],
        source="yfinance",
        adapter_version="1",
        parser_version="1",
        created_at=WHEN,
    )
    bars_file = next((tmp_path / "snaps" / "snap1").glob("bars/*.parquet"))
    bars_file.write_bytes(bars_file.read_bytes() + b"corruption")
    with pytest.raises(DataError):
        verify_snapshot(tmp_path / "snaps" / "snap1")


def test_verify_detects_pull_provenance_tampering(tmp_path: Path) -> None:
    store = _store(tmp_path)
    create_snapshot(
        store,
        tmp_path / "snaps",
        "snap1",
        ["AAPL"],
        source="yfinance",
        adapter_version="1",
        parser_version="1",
        created_at=WHEN,
    )
    provenance = tmp_path / "snaps" / "snap1" / "provenance" / "AAPL.json"
    provenance.write_text('{"source":"ccxt:binance"}', encoding="utf-8")
    with pytest.raises(DataError, match="provenance"):
        verify_snapshot(tmp_path / "snaps" / "snap1")


def test_snapshot_preserves_slash_symbols(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path / "work")
    store_fetch_result(store, parse_yfinance_history(aapl_like(), "BTC/USD"))
    store_fetch_result(store, parse_yfinance_history(aapl_like(), "ETH/USD"))
    create_snapshot(
        store,
        tmp_path / "snaps",
        "s",
        ["BTC/USD", "ETH/USD"],
        source="x",
        adapter_version="1",
        parser_version="1",
        created_at=WHEN,
    )
    assert (tmp_path / "snaps" / "s" / "bars" / "BTC" / "USD.parquet").exists()
    assert (tmp_path / "snaps" / "s" / "bars" / "ETH" / "USD.parquet").exists()
    verify_snapshot(tmp_path / "snaps" / "s")  # both distinct → integrity holds


def test_snapshot_refuses_overwrite(tmp_path: Path) -> None:
    store = _store(tmp_path)
    create_snapshot(
        store,
        tmp_path / "snaps",
        "snap1",
        ["AAPL"],
        source="yfinance",
        adapter_version="1",
        parser_version="1",
        created_at=WHEN,
    )
    with pytest.raises(DataError):
        create_snapshot(
            store,
            tmp_path / "snaps",
            "snap1",
            ["AAPL"],
            source="yfinance",
            adapter_version="1",
            parser_version="1",
            created_at=WHEN,
        )


def test_failed_snapshot_copy_leaves_no_marker_or_staging_directory(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshots = tmp_path / "snaps"

    with pytest.raises(DataError, match="MISSING"):
        create_snapshot(
            store,
            snapshots,
            "snap1",
            ["AAPL", "MISSING"],
            source="yfinance",
            adapter_version="1",
            parser_version="1",
            created_at=WHEN,
        )

    assert not (snapshots / "snap1" / "manifest.json").exists()
    assert list(snapshots.iterdir()) == []


def test_concurrent_snapshot_writers_publish_exactly_one_complete_snapshot(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshots = tmp_path / "snaps"

    def create() -> bool:
        try:
            create_snapshot(
                store,
                snapshots,
                "snap1",
                ["AAPL"],
                source="yfinance",
                adapter_version="1",
                parser_version="1",
                created_at=WHEN,
            )
        except DataError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))

    assert results.count(True) == 1
    verify_snapshot(snapshots / "snap1")
    assert [p for p in snapshots.iterdir() if p.name != "snap1"] == []


def test_snapshot_id_cannot_escape_snapshots_root(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    store = _store(tmp_path)
    for bad in ("../evil", "a/../../b", "", ".hidden", "x/y"):
        with pytest.raises(DataError):
            create_snapshot(
                store,
                tmp_path / "snaps",
                bad,
                ["AAPL"],
                source="yfinance",
                adapter_version="1",
                parser_version="1",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )


def test_corrupt_snapshot_manifest_is_typed(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text("{")
    with pytest.raises(DataError, match="corrupt snapshot manifest"):
        verify_snapshot(snapshot)


@pytest.mark.parametrize(
    "entry",
    [
        None,
        {},
        {"bars_file": "../../outside.parquet", "bars_sha256": "0" * 64},
    ],
)
def test_malformed_symbol_manifest_entries_are_typed(tmp_path: Path, entry: object) -> None:
    store = _store(tmp_path)
    create_snapshot(
        store,
        tmp_path / "snaps",
        "snap1",
        ["AAPL"],
        source="yfinance",
        adapter_version="1",
        parser_version="1",
        created_at=WHEN,
    )
    snapshot = tmp_path / "snaps" / "snap1"
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["symbols"]["AAPL"] = entry
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataError, match="invalid snapshot"):
        verify_snapshot(snapshot)
