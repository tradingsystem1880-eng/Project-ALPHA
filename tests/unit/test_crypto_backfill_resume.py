from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._crypto_backfill import BackfillWindow, Ledger, run_backfill, split_window
from alpha_core import DataError

NOW = datetime(2026, 9, 10, tzinfo=UTC)
WINDOW = BackfillWindow("2024-01-01T00:00:00Z", "2024-03-01T00:00:00Z", None)


def _ledger(path: Path) -> Ledger:
    return Ledger.open(path, provider="bybit", family="funding", category="linear", frequency="1h")


def _run(path: Path, acquire: Any, **kwargs: Any) -> dict[str, object]:
    return run_backfill(
        provider="bybit",
        family="funding",
        symbols=["BTCUSDT", "ETHUSDT"],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 3, 1),
        ledger_path=path,
        acquire=acquire,
        now=NOW,
        pause_seconds=0,
        **kwargs,
    )


def test_done_without_verifier_stops_before_any_new_acquire(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    _ledger(path).record(f"ETHUSDT|{WINDOW.key}", {"state": "done", "manifest_id": "old"})
    before = path.read_bytes()
    with pytest.raises(DataError, match="verif"):
        _run(path, lambda *a, **k: pytest.fail("must preflight later completed entries first"))
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "body",
    [
        "{}",
        "[]",
        '{"schema_version":2,"windows":{}}',
        '{"schema_version":1,"windows":{"BTCUSDT|2024-01-01T00:00:00Z|2024-03-01T00:00:00Z|None":null}}',
        '{"schema_version":1,"windows":{"BTCUSDT|2024-01-01T00:00:00Z|2024-03-01T00:00:00Z|None":{"state":"unknown"}}}',
    ],
)
def test_unavailable_progress_is_never_reinterpreted_as_unused_work(
    tmp_path: Path, body: str
) -> None:
    path = tmp_path / "progress.json"
    path.write_text(body)
    with pytest.raises(DataError):
        _run(path, lambda *a, **k: pytest.fail("no progress reset"))
    assert path.read_text() == body


def test_all_done_outputs_verify_before_unfinished_windows_retry(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    _ledger(path).record(f"ETHUSDT|{WINDOW.key}", {"state": "done", "manifest_id": "old"})
    events: list[str] = []

    def verify(symbol: str, window: BackfillWindow, entry: dict[str, object]) -> None:
        assert window == WINDOW and entry["manifest_id"] == "old"
        events.append("verify:" + symbol)

    def acquire(*args: Any, **kwargs: Any) -> dict[str, object]:
        events.append("acquire:" + args[2])
        return {"normalized_manifest_id": "new", "state": "qualified"}

    result = _run(path, acquire, verify_completed=verify)
    assert events == ["verify:ETHUSDT", "acquire:BTCUSDT"]
    assert result["done"] == result["skipped"] == result["verified_completed"] == 1


def test_failed_verification_preserves_all_progress_and_never_reacquires(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    _ledger(path).record(f"ETHUSDT|{WINDOW.key}", {"state": "done", "manifest_id": "lost"})
    before = path.read_bytes()

    def verify(*args: Any) -> None:
        raise DataError("external artifact integrity failure")

    with pytest.raises(DataError, match="integrity"):
        _run(path, lambda *a, **k: pytest.fail("no automatic replacement"), verify_completed=verify)
    assert path.read_bytes() == before


def test_interrupted_split_resumes_only_unfinished_child(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    calls: list[str] = []
    halves = split_window(WINDOW)
    assert halves is not None

    def acquire(*args: Any, **kwargs: Any) -> dict[str, object]:
        calls.append(str(kwargs["start"]))
        if kwargs["end"] == WINDOW.end and kwargs["start"] == WINDOW.start:
            raise DataError("Bybit bounded window fills one provider page; narrow the range")
        if kwargs["start"] == halves[1].start:
            raise KeyboardInterrupt
        return {"normalized_manifest_id": "left", "state": "qualified"}

    with pytest.raises(KeyboardInterrupt):
        _run(path, acquire)
    retained = json.loads(path.read_text())["windows"]
    assert retained[f"BTCUSDT|{WINDOW.key}"]["state"] == "split"
    left = retained[f"BTCUSDT|{halves[0].key}"]
    calls.clear()
    verified: list[str] = []

    def retry(*args: Any, **kwargs: Any) -> dict[str, object]:
        assert (
            kwargs["start"] != WINDOW.start or kwargs["end"] != WINDOW.end or args[2] == "ETHUSDT"
        )
        calls.append(args[2] + ":" + str(kwargs["start"]))
        return {"normalized_manifest_id": "remaining", "state": "qualified"}

    result = _run(
        path,
        retry,
        verify_completed=lambda symbol, window, entry: verified.append(entry["manifest_id"]),
    )
    assert verified == ["left"]
    assert calls == ["BTCUSDT:" + str(halves[1].start), "ETHUSDT:" + str(WINDOW.start)]
    assert result["done"] == 2 and result["skipped"] == 1
    assert json.loads(path.read_text())["windows"][f"BTCUSDT|{halves[0].key}"] == left


def test_dry_run_has_no_evidence_probe_or_progress_write(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    _ledger(path).record(f"ETHUSDT|{WINDOW.key}", {"state": "done", "manifest_id": "old"})
    before = path.read_bytes()

    def fail(*args: Any, **kwargs: Any) -> None:
        pytest.fail("dry-run must not perform effects")

    result = _run(path, fail, verify_completed=fail, dry_run=True)
    assert path.read_bytes() == before
    assert result["verified_completed"] == 0
    assert result["resume_verification"] == "not_run_dry_run"
    missing = tmp_path / "missing" / "progress.json"
    _run(missing, fail, dry_run=True)
    assert not missing.parent.exists()


def test_cancel_during_preflight_has_no_progress_or_provider_effect(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    _ledger(path).record(f"ETHUSDT|{WINDOW.key}", {"state": "done", "manifest_id": "old"})
    before = path.read_bytes()

    def cancel(*args: Any) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _run(path, lambda *a, **k: pytest.fail("cancelled"), verify_completed=cancel)
    assert path.read_bytes() == before


@pytest.mark.parametrize("parent_failed", [False, True])
def test_legacy_orphaned_child_is_not_reinterpreted_as_unused_work(
    tmp_path: Path, parent_failed: bool
) -> None:
    path = tmp_path / "progress.json"
    ledger = _ledger(path)
    halves = split_window(WINDOW)
    assert halves is not None
    ledger.record(f"ETHUSDT|{halves[0].key}", {"state": "done", "manifest_id": "corrupt"})
    if parent_failed:
        ledger.record(f"ETHUSDT|{WINDOW.key}", {"state": "failed", "error": "old failure"})
    before = path.read_bytes()
    with pytest.raises(DataError, match="topology"):
        _run(path, lambda *a, **k: pytest.fail("do not repeat retained work"))
    assert path.read_bytes() == before


@pytest.mark.bias_guard
def test_future_unrequested_progress_cannot_change_requested_resume(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    ledger = _ledger(path)
    ledger.record(f"BTCUSDT|{WINDOW.key}", {"state": "done", "manifest_id": "historical"})
    ledger.record(
        "BTCUSDT|2030-01-01T00:00:00Z|2030-03-01T00:00:00Z|None",
        {"state": "done", "manifest_id": "future"},
    )
    seen: list[str] = []
    _run(
        path,
        lambda *a, **k: {"normalized_manifest_id": "new", "state": "qualified"},
        verify_completed=lambda s, w, e: seen.append(e["manifest_id"]),
    )
    assert seen == ["historical"]
    # Deliberately leaky control: scanning all retained progress instead of this request fails.
    with pytest.raises(AssertionError):
        assert [e["manifest_id"] for e in ledger.body["windows"].values()] == seen
