"""ADR-0043: the free-space reserve is an owner-set value with a hard floor; default unchanged."""

from __future__ import annotations

import json
from collections import namedtuple
from pathlib import Path

import gate
import pytest

from alpha_cli.crypto_bulk_store import (
    RESERVE_FLOOR_BYTES,
    ConfiguredCryptoBulkStore,
    OwnerStorageReserveV1,
    configured_crypto_bulk_store,
)
from alpha_cli.crypto_data_cmds import _storage_blocker
from alpha_core import DataError
from alpha_data.crypto.storage import Capacity

UUID = "11111111-2222-3333-4444-555555555555"
GB = 1_000_000_000
TOTAL = 114 * GB


def _reserve(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "OwnerStorageReserveV1",
        "minimum_free_bytes": 10 * GB,
        "advisory_free_bytes": 20 * GB,
        "decided_by": "owner",
        "decided_on": "2026-11-14",
        "decision_record": "ADR-0043",
    }
    value.update(changes)
    return value


def _store(
    root: Path, *, reserve: dict[str, object] | None, free: int
) -> ConfiguredCryptoBulkStore:
    bulk = root / "bulk"
    bulk.mkdir(parents=True, exist_ok=True)
    config: dict[str, object] = {
        "schema": "CryptoBulkStorageConfigV1",
        "backend": "macos_volume_uuid",
        "bulk_root": str(bulk),
        "volume_uuid": UUID,
    }
    if reserve is not None:
        config["free_space_reserve"] = reserve
    path = root / "crypto" / "storage-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config))
    store = configured_crypto_bulk_store(root)
    # Inject the identity and the free-space reading; never depend on the real disk.
    store._volume_uuid = lambda _: UUID
    store._capacity = lambda _: Capacity(total_bytes=TOTAL, free_bytes=free)
    return store


def test_default_reserve_is_unchanged_without_an_owner_setting(tmp_path: Path) -> None:
    store = _store(tmp_path, reserve=None, free=200 * GB)
    assert (store.reserve_fraction, store.minimum_free_bytes) == (0.15, 100 * GB)
    assert store.owner_reserve is None
    assert store.reserve_bytes(Capacity(total_bytes=2_000 * GB, free_bytes=0)) == 300 * GB
    assert store.reserve_bytes(Capacity(total_bytes=TOTAL, free_bytes=0)) == 100 * GB
    assert store.low_space_advisory(Capacity(total_bytes=TOTAL, free_bytes=1)) is None
    store.verify_ready(required_bytes=0)
    small = _store(tmp_path / "small", reserve=None, free=48 * GB)
    with pytest.raises(DataError, match="free-space reserve.*default reserve"):
        small.verify_ready(required_bytes=0)


def test_explicit_lower_owner_reserve_is_accepted(tmp_path: Path) -> None:
    store = _store(tmp_path, reserve=_reserve(), free=48 * GB)
    assert (store.reserve_fraction, store.minimum_free_bytes) == (0.0, 10 * GB)
    assert store.owner_reserve == OwnerStorageReserveV1.from_dict(_reserve())
    assert store.verify_ready(required_bytes=30 * GB).free_bytes == 48 * GB
    assert "decided by owner on 2026-11-14 (ADR-0043)" in store.reserve_source()


@pytest.mark.parametrize(
    "changes",
    [
        {"minimum_free_bytes": RESERVE_FLOOR_BYTES - 1},
        {"minimum_free_bytes": 0},
        {"minimum_free_bytes": -GB},
        {"minimum_free_bytes": 10.5 * GB},
        {"minimum_free_bytes": True},
        {"advisory_free_bytes": RESERVE_FLOOR_BYTES - 1},
        {"minimum_free_bytes": 30 * GB, "advisory_free_bytes": 20 * GB},
        {"decided_by": ""},
        {"decided_on": "yesterday"},
        {"decision_record": " "},
        {"schema": "OwnerStorageReserveV0"},
        {"approved": True},
    ],
)
def test_reserve_below_floor_or_unattributed_is_rejected(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    with pytest.raises(DataError, match="configuration owner reserve") as error:
        _store(tmp_path, reserve=_reserve(**changes), free=48 * GB)
    assert _storage_blocker(str(error.value)) == "bulk_storage_configuration_invalid"


def test_free_space_below_the_configured_reserve_is_refused_loudly(tmp_path: Path) -> None:
    store = _store(tmp_path, reserve=_reserve(), free=12 * GB)
    with pytest.raises(DataError, match="free-space reserve") as error:
        store.verify_ready(required_bytes=3 * GB)
    message = str(error.value)
    assert "12.0 GB free" in message and "10.0 GB must stay free" in message
    assert "owner-set reserve 10.0 GB" in message and "Refused before writing" in message
    assert _storage_blocker(message) == "bulk_storage_reserve_blocked"
    assert not any((tmp_path / "bulk").iterdir())  # no write probe or partial bytes


def test_low_space_advisory_is_emitted_below_the_threshold_only(tmp_path: Path) -> None:
    store = _store(tmp_path, reserve=_reserve(), free=15 * GB)
    advisory = store.low_space_advisory(Capacity(total_bytes=TOTAL, free_bytes=15 * GB))
    assert advisory is not None and advisory.startswith("LOW DISK SPACE: 15.0 GB free")
    assert store.low_space_advisory(Capacity(total_bytes=TOTAL, free_bytes=25 * GB)) is None
    store.verify_ready(required_bytes=0)  # advisory never refuses on its own


def test_retained_reserve_survives_explicit_environment_identity(tmp_path: Path) -> None:
    from alpha_core.config import AlphaSettings

    _store(tmp_path, reserve=_reserve(), free=48 * GB)
    settings = AlphaSettings(
        _env_file=None,  # never read a .env file in tests
        data_dir=tmp_path,
        bulk_data_dir=tmp_path / "bulk",
        bulk_volume_uuid=UUID,
    )
    store = configured_crypto_bulk_store(settings)
    assert store.minimum_free_bytes == 10 * GB


Usage = namedtuple("Usage", "total used free")


def _doctor_root(tmp_path: Path, reserve: dict[str, object] | None) -> Path:
    data = tmp_path / "data"
    (data / "crypto").mkdir(parents=True)
    config: dict[str, object] = {"bulk_root": str(data)}
    if reserve is not None:
        config["free_space_reserve"] = reserve
    (data / "crypto" / "storage-config.json").write_text(json.dumps(config))
    return tmp_path


@pytest.mark.parametrize(
    ("reserve", "free", "expected"),
    [
        (_reserve(), 25 * GB, None),
        (_reserve(), 15 * GB, "LOW DISK SPACE: below the owner's advisory threshold"),
        (_reserve(), 5 * GB, "LOW DISK SPACE: below the reserve"),
        (None, 150 * GB, None),
        (None, 48 * GB, "LOW DISK SPACE: below the reserve"),
    ],
)
def test_doctor_reports_storage_advisory_from_injected_reading(
    tmp_path: Path, reserve: dict[str, object] | None, free: int, expected: str | None
) -> None:
    root = _doctor_root(tmp_path, reserve)
    ok, detail = gate.storage_advisory(
        root, environ={}, usage=lambda _: Usage(TOTAL, TOTAL - free, free)
    )
    assert ok  # advisory: never fails the harness doctor
    if expected is None:
        assert "LOW DISK SPACE" not in detail
    else:
        assert detail.startswith(expected)


def test_documented_dell_example_is_a_valid_owner_reserve() -> None:
    example = Path(__file__).parents[2] / "docs/operations/dell-storage-settings.example.json"
    reserve = OwnerStorageReserveV1.from_dict(json.loads(example.read_text())["free_space_reserve"])
    assert (reserve.minimum_free_bytes, reserve.advisory_free_bytes) == (10 * GB, 20 * GB)
