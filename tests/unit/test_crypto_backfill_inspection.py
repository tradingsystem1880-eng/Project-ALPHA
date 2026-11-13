from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._crypto_backfill import Ledger
from alpha_cli._crypto_backfill_inspection import inspect_backfill

NOW = datetime(2026, 9, 10, tzinfo=UTC)


def _inspect(path: Path, **extra: Any) -> dict[str, Any]:
    args: dict[str, Any] = dict(
        provider="bybit",
        family="funding",
        symbols=["BTCUSDT"],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 3, 1),
        ledger_path=path,
        now=NOW,
        max_ledger_bytes=10000,
        max_windows=20,
        max_verify_artifact_bytes=10000,
        load_store=lambda: pytest.fail("unfinished/missing status must not load storage"),
    )
    args.update(extra)
    return inspect_backfill(**args)


def test_missing_ledger_is_unknown_without_initialization(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    result = _inspect(root / "ledger.json")
    assert result["reason"] == "LEDGER_MISSING"
    assert result["historical_quota_usage"] is None
    assert result["execution_authority"] is False
    assert not root.exists()


def test_valid_ledger_pending_and_failed_are_advisory_only(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger = Ledger.open(
        path, provider="bybit", family="funding", category="linear", frequency="1h"
    )
    ledger.record(
        "BTCUSDT|2024-01-01T00:00:00Z|2024-03-01T00:00:00Z|None",
        {"state": "failed", "error": "SECRET_CANARY", "cause": "SECRET_CANARY"},
    )
    before = path.read_bytes(), path.stat().st_mtime_ns
    result = _inspect(path, symbols=["BTCUSDT", "ETHUSDT"])
    assert [r["status"] for r in result["windows"]] == ["recorded_failure", "pending_unrecorded"]
    assert "SECRET_CANARY" not in json.dumps(result)
    assert result["inspection_provider_calls"] == 0
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def _ledger(path: Path) -> Ledger:
    return Ledger.open(path, provider="bybit", family="funding", category="linear", frequency="1h")


@pytest.mark.parametrize(
    "body", ["{}", "not JSON SECRET_CANARY", "[]", '{"schema_version":2,"windows":{}}']
)
def test_invalid_progress_is_reported_without_reset(tmp_path: Path, body: str) -> None:
    path = tmp_path / "ledger.json"
    path.write_text(body)
    result = _inspect(path)
    assert result["reason"] == "LEDGER_UNREADABLE_OR_INVALID"
    assert result["counts"] is None
    assert "SECRET_CANARY" not in json.dumps(result)
    assert path.read_text() == body
    assert list(tmp_path.iterdir()) == [path]


def test_exact_ledger_byte_cap_and_owner_does_not_block_readonly_status(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger = _ledger(path)
    ledger.save()
    before = path.read_bytes(), path.stat().st_mtime_ns
    with ledger.exclusive():
        exact = _inspect(path, max_ledger_bytes=len(before[0]))
        assert exact["inspection_state"] == "complete"
        failed = _inspect(path, max_ledger_bytes=len(before[0]) - 1)
        assert failed["reason"] == "LEDGER_BYTE_LIMIT"
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_split_topology_is_shared_and_visits_bounded(tmp_path: Path) -> None:
    from alpha_cli._crypto_backfill import BackfillWindow, split_window

    path = tmp_path / "ledger.json"
    ledger = _ledger(path)
    window = BackfillWindow("2024-01-01T00:00:00Z", "2024-03-01T00:00:00Z", None)
    halves = split_window(window)
    assert halves is not None
    ledger.record(f"BTCUSDT|{window.key}", {"state": "split"})
    ledger.record(f"BTCUSDT|{halves[0].key}", {"state": "failed"})
    report = _inspect(path, max_windows=3)
    assert [r["status"] for r in report["windows"]] == ["recorded_failure", "pending_unrecorded"]
    assert report["window_visits"] == 3
    limited = _inspect(path, max_windows=2)
    assert limited["reason"] == "WINDOW_LIMIT" and limited["truncated"]
    assert limited["windows"] == [] and limited["counts"] is None


def test_orphaned_child_stops_inspection_like_resume(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _ledger(path).record(
        "BTCUSDT|2024-01-01T00:00:00Z|2024-01-15T00:00:00Z|None", {"state": "failed"}
    )
    before = path.read_bytes()
    result = _inspect(path)
    assert result["reason"] == "TOPOLOGY_OR_ENTRY_INVALID"
    assert path.read_bytes() == before


def test_plan_limit_is_applied_before_progress_or_storage_read(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_bytes(b"SECRET_CANARY")
    result = _inspect(path, end=date(2030, 1, 1), max_windows=1)
    assert result["reason"] == "WINDOW_LIMIT"
    assert result["ledger_sha256"] is None and result["windows"] == []


@pytest.mark.parametrize("name", ["max_ledger_bytes", "max_windows", "max_verify_artifact_bytes"])
def test_nonpositive_limits_do_not_create_state(tmp_path: Path, name: str) -> None:
    from alpha_core import DataError

    with pytest.raises(DataError, match="positive"):
        _inspect(tmp_path / "absent" / "ledger.json", **{name: 0})
    assert list(tmp_path.iterdir()) == []


def test_progress_change_during_verification_requires_new_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alpha_cli._crypto_backfill_inspection as inspection

    path = tmp_path / "ledger.json"
    _ledger(path).record(
        "BTCUSDT|2024-01-01T00:00:00Z|2024-03-01T00:00:00Z|None",
        {"state": "done", "manifest_id": "a" * 64, "quality_state": "warning"},
    )

    def verify(*args: Any, **kwargs: Any) -> None:
        _ledger(path).record("OTHER|future", {"state": "failed"})

    monkeypatch.setattr(inspection, "verify_completed_window", verify)
    result = _inspect(path, load_store=lambda: object())
    assert result["reason"] == "LEDGER_CHANGED_DURING_INSPECTION"
    assert result["resume_evidence"] == "stale"


def test_cancellation_propagates_without_creating_a_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alpha_cli._crypto_backfill_inspection as inspection

    path = tmp_path / "ledger.json"
    _ledger(path).record(
        "BTCUSDT|2024-01-01T00:00:00Z|2024-03-01T00:00:00Z|None", {"state": "done"}
    )
    path.with_name(path.name + ".lock").unlink()  # setup only; no writer is active
    before = path.read_bytes()

    def cancel(*args: Any, **kwargs: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(inspection, "verify_completed_window", cancel)
    with pytest.raises(KeyboardInterrupt):
        _inspect(path, load_store=lambda: object())
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.bias_guard
def test_future_unrequested_progress_does_not_change_requested_status(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _ledger(path).save()
    before = _inspect(path)["windows"]
    _ledger(path).record(
        "BTCUSDT|2030-01-01T00:00:00Z|2030-03-01T00:00:00Z|None", {"state": "failed"}
    )
    after = _inspect(path)["windows"]
    assert after == before
    assert not any(row["start"].startswith("2030") for row in after)


@pytest.mark.parametrize("state", [[], {}])
def test_unhashable_corrupt_entry_state_reports_sanitized_failure(
    tmp_path: Path, state: Any
) -> None:
    path = tmp_path / "ledger.json"
    _ledger(path).save()
    body = json.loads(path.read_bytes())
    body["windows"]["BTCUSDT|2024-01-01T00:00:00Z|2024-03-01T00:00:00Z|None"] = {"state": state}
    path.write_text(json.dumps(body))
    before = path.read_bytes(), path.stat().st_mtime_ns
    result = _inspect(path)
    assert result["reason"] == "TOPOLOGY_OR_ENTRY_INVALID"
    assert result["windows"] == []
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
