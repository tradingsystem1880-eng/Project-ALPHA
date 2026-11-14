"""Bar-frequency inference and deterministic single-store routing."""

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_cli.spine.stores import periods_per_year, resolve_asset
from alpha_core import DataError
from alpha_data.store import ParquetStore


def _days() -> list[datetime]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [start + timedelta(days=i) for i in range(3653)]


def test_periods_per_year_exchange_sessions() -> None:
    weekdays = [stamp for stamp in _days() if stamp.weekday() < 5]
    holidays = {
        stamp
        for year in range(2020, 2031)
        for stamp in [day for day in weekdays if day.year == year][:9]
    }
    assert periods_per_year([stamp for stamp in weekdays if stamp not in holidays]) == 252


def test_periods_per_year_weekdays() -> None:
    assert periods_per_year([stamp for stamp in _days() if stamp.weekday() < 5]) == 261


def test_periods_per_year_calendar_days() -> None:
    assert periods_per_year(_days()) == 365


def test_periods_per_year_hourly_crypto() -> None:
    stamps = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(hours=i) for i in range(87660)]
    assert periods_per_year(stamps) == 8766  # 365.25 days, per the specified formula


@pytest.mark.parametrize("count", [0, 1, 29])
def test_periods_per_year_too_short(count: int) -> None:
    with pytest.raises(ValueError, match="30"):
        periods_per_year(_days()[:count])


def test_periods_per_year_disordered() -> None:
    with pytest.raises(ValueError, match="increasing"):
        periods_per_year(list(reversed(_days()[:30])))


def _provenance(root: Path, symbol: str, source: str = "vendor") -> Path:
    return ParquetStore(root / "store").write_provenance(
        symbol, source=source, adapter_version="1", parser_version="1"
    )


def _registry(home: Path) -> Path:
    second = home.parent / f"{home.name}-second"
    (home / "stores.toml").write_text(f'alpaca = "../{second.name}"\n')
    return second


def test_resolve_asset_home_without_registry(tmp_path: Path) -> None:
    _provenance(tmp_path, "SPY")
    result = resolve_asset("SPY", data_dir=tmp_path)
    assert (result.symbol, result.store_name, result.data_dir, result.source, result.defaulted) == (
        "SPY",
        "home",
        tmp_path,
        "vendor",
        False,
    )
    with pytest.raises(FrozenInstanceError):
        result.symbol = "QQQ"  # type: ignore[misc]


def test_resolve_asset_explicit_and_implicit_duplicate(tmp_path: Path) -> None:
    second = _registry(tmp_path)
    _provenance(tmp_path, "SPY", "home-source")
    _provenance(second, "SPY", "alpaca")
    implicit = resolve_asset("SPY", data_dir=tmp_path)
    assert implicit.store_name == "home"
    assert implicit.defaulted
    explicit = resolve_asset("SPY@alpaca", data_dir=tmp_path)
    assert (explicit.store_name, explicit.data_dir, explicit.source, explicit.defaulted) == (
        "alpaca",
        second,
        "alpaca",
        False,
    )
    assert not resolve_asset("SPY@home", data_dir=tmp_path).defaulted


def test_resolve_asset_second_store_slash_pair(tmp_path: Path) -> None:
    second = _registry(tmp_path)
    path = _provenance(second, "BTC/USDT")
    path.write_text(json.dumps({"dataset": {"provider": "binance"}}))
    result = resolve_asset("BTC/USDT", data_dir=tmp_path)
    assert (result.symbol, result.store_name, result.source, result.defaulted) == (
        "BTC/USDT",
        "alpaca",
        "binance",
        False,
    )


def test_resolve_asset_file_order(tmp_path: Path) -> None:
    second = _registry(tmp_path)
    third = tmp_path / "third"
    with (tmp_path / "stores.toml").open("a") as stream:
        stream.write('zulu = "third"\n')
    _provenance(second, "SPY")
    _provenance(third, "SPY")
    result = resolve_asset("SPY", data_dir=tmp_path)
    assert result.store_name == "alpaca"
    assert result.defaulted


def test_resolve_asset_unknown_and_missing(tmp_path: Path) -> None:
    _registry(tmp_path)
    with pytest.raises(DataError, match="unknown.*home.*alpaca"):
        resolve_asset("SPY@missing", data_dir=tmp_path)
    with pytest.raises(DataError, match="SPY.*home.*alpaca"):
        resolve_asset("SPY", data_dir=tmp_path)
    _provenance(tmp_path, "SPY")
    with pytest.raises(DataError, match="SPY.*alpaca"):
        resolve_asset("SPY@alpaca", data_dir=tmp_path)


@pytest.mark.parametrize("payload", ['{"source": ""}', "[]", "{broken"])
def test_resolve_asset_invalid_provenance(tmp_path: Path, payload: str) -> None:
    _provenance(tmp_path, "SPY").write_text(payload)
    with pytest.raises(DataError, match="provenance"):
        resolve_asset("SPY", data_dir=tmp_path)


@pytest.mark.parametrize("registry", ['home = "elsewhere"', "alpaca = 42"])
def test_resolve_asset_invalid_registry(tmp_path: Path, registry: str) -> None:
    (tmp_path / "stores.toml").write_text(registry)
    with pytest.raises(DataError, match="store"):
        resolve_asset("SPY", data_dir=tmp_path)
