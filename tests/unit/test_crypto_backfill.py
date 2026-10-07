"""Phase B S1: windowed, resumable crypto backfill over the existing bounded acquisition path."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._crypto_backfill import (
    BackfillWindow,
    Ledger,
    plan_windows,
    run_backfill,
    split_symbol,
)
from alpha_core import DataError

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def _span_days(window: BackfillWindow) -> float:
    assert window.start is not None and window.end is not None
    start = datetime.fromisoformat(window.start.replace("Z", "+00:00"))
    end = datetime.fromisoformat(window.end.replace("Z", "+00:00"))
    return (end - start).total_seconds() / 86_400


def test_funding_windows_are_contiguous_under_sixty_days_and_end_at_the_bound() -> None:
    windows = plan_windows(
        "bybit", "funding", "1h", start=date(2024, 1, 1), end=date(2024, 5, 1), now=NOW
    )
    assert len(windows) == 3
    assert windows[0].start == "2024-01-01T00:00:00Z"
    assert windows[-1].end == "2024-05-01T00:00:00Z"
    assert all(_span_days(w) <= 60 for w in windows)
    for earlier, later in zip(windows, windows[1:], strict=False):
        assert later.start == earlier.end
    assert all(w.period is None for w in windows)


@pytest.mark.parametrize(
    ("family", "frequency", "max_days"),
    [
        ("derivative_bars", "1h", 40),
        ("mark_bars", "1h", 40),
        ("derivative_bars", "1d", 900),
        ("derivative_bars", "5m", 3),
        ("open_interest", "1h", 60),
        ("long_short_ratio", "1h", 60),
    ],
)
def test_bybit_window_spans_stay_under_the_page_limit(
    family: str, frequency: str, max_days: int
) -> None:
    windows = plan_windows(
        "bybit", family, frequency, start=date(2022, 1, 1), end=date(2026, 9, 1), now=NOW
    )
    assert windows
    assert all(_span_days(w) <= max_days for w in windows)
    assert windows[-1].end == "2026-09-01T00:00:00Z"


def test_the_end_bound_is_clamped_to_the_acquisition_knowledge_time() -> None:
    windows = plan_windows(
        "bybit", "funding", "1h", start=date(2026, 9, 1), end=date(2026, 12, 31), now=NOW
    )
    assert windows[-1].end == "2026-09-10T11:59:00Z"


def test_binance_market_bars_plan_one_calendar_month_per_window() -> None:
    windows = plan_windows(
        "binance", "market_bars", "1d", start=date(2023, 11, 15), end=date(2024, 2, 1), now=NOW
    )
    assert [w.period for w in windows] == ["2023-11", "2023-12", "2024-01", "2024-02"]
    assert all(w.start is None and w.end is None for w in windows)


def test_unsupported_families_and_orders_fail_loud() -> None:
    with pytest.raises(DataError, match="backfill"):
        plan_windows(
            "bybit", "option_quotes", "1h", start=date(2024, 1, 1), end=date(2024, 2, 1), now=NOW
        )
    with pytest.raises(DataError, match="end"):
        plan_windows(
            "bybit", "funding", "1h", start=date(2024, 2, 1), end=date(2024, 1, 1), now=NOW
        )
    with pytest.raises(DataError, match="frequency"):
        plan_windows(
            "bybit", "derivative_bars", "1m", start=date(2024, 1, 1), end=date(2024, 2, 1), now=NOW
        )


def test_split_symbol_uses_the_exact_quote_suffix() -> None:
    assert split_symbol("1000PEPEUSDT", quote="USDT") == ("1000PEPE", "USDT")
    with pytest.raises(DataError, match="quote"):
        split_symbol("BTCUSD", quote="USDT")


def _fake_acquire(
    calls: list[dict[str, Any]], *, fail_windows: frozenset[str] = frozenset()
) -> Callable[..., dict[str, object]]:
    def acquire(provider: str, family: str, instrument: str, **kwargs: Any) -> dict[str, object]:
        calls.append({"provider": provider, "family": family, "instrument": instrument, **kwargs})
        key = f"{instrument}|{kwargs.get('start')}|{kwargs.get('period')}"
        if key in fail_windows:
            try:
                raise TimeoutError("timed out")
            except TimeoutError as exc:
                raise DataError(
                    "Bybit acquisition returned no observations inside the range"
                ) from exc
        return {"normalized_manifest_id": f"m-{len(calls)}", "state": "qualified"}

    return acquire


def test_run_forwards_exact_kwargs_and_records_every_window(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []
    summary = run_backfill(
        provider="bybit",
        family="funding",
        symbols=["BTCUSDT", "ETHUSDT"],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 4, 1),
        ledger_path=tmp_path / "ledger.json",
        acquire=_fake_acquire(calls),
        now=NOW,
        pause_seconds=0.0,
    )
    # 91 days -> two 60/31-day windows per symbol.
    assert summary["windows_total"] == 4 and summary["done"] == 4 and summary["failed"] == 0
    assert calls[0] == {
        "provider": "bybit",
        "family": "funding",
        "instrument": "BTCUSDT",
        "base": "BTC",
        "quote": "USDT",
        "category": "linear",
        "frequency": "1h",
        "period": None,
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-03-01T00:00:00Z",
    }
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["provider"] == "bybit" and len(ledger["windows"]) == 4
    assert all(entry["state"] == "done" for entry in ledger["windows"].values())
    assert {entry["manifest_id"] for entry in ledger["windows"].values()} == {
        "m-1",
        "m-2",
        "m-3",
        "m-4",
    }


def test_rerun_skips_done_windows_and_retries_failed_ones(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []
    failing = frozenset({"ETHUSDT|2024-01-01T00:00:00Z|None"})
    first = run_backfill(
        provider="bybit",
        family="funding",
        symbols=["BTCUSDT", "ETHUSDT"],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 2, 1),
        ledger_path=tmp_path / "ledger.json",
        acquire=_fake_acquire(calls, fail_windows=failing),
        now=NOW,
        pause_seconds=0.0,
    )
    assert first["done"] == 1 and first["failed"] == 1
    failed_entry = next(
        e
        for e in json.loads((tmp_path / "ledger.json").read_text())["windows"].values()
        if e["state"] == "failed"
    )
    assert "no observations" in failed_entry["error"]
    assert failed_entry["cause"] == "TimeoutError('timed out')"

    calls.clear()
    second = run_backfill(
        provider="bybit",
        family="funding",
        symbols=["BTCUSDT", "ETHUSDT"],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 2, 1),
        ledger_path=tmp_path / "ledger.json",
        acquire=_fake_acquire(calls),
        now=NOW,
        pause_seconds=0.0,
    )
    assert [c["instrument"] for c in calls] == ["ETHUSDT"]
    assert second["done"] == 1 and second["failed"] == 0 and second["skipped"] == 1


def test_ledger_rejects_a_mismatched_scope(tmp_path: Path) -> None:
    ledger = Ledger.open(
        tmp_path / "l.json", provider="bybit", family="funding", category="linear", frequency="1h"
    )
    ledger.save()
    with pytest.raises(DataError, match="scope"):
        Ledger.open(
            tmp_path / "l.json",
            provider="bybit",
            family="open_interest",
            category="linear",
            frequency="1h",
        )


def test_cli_wrapper_makes_every_unused_typer_default_an_explicit_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typer.Option sentinel is not None; the in-process call must never leak one."""
    from alpha_cli import crypto_data_cmds

    seen: dict[str, Any] = {}

    def fake(provider: str, family: str, instrument: str, **kwargs: Any) -> dict[str, object]:
        seen.update(kwargs)
        return {"normalized_manifest_id": "m", "state": "qualified"}

    monkeypatch.setattr(crypto_data_cmds, "_acquire_result", fake)
    crypto_data_cmds._backfill_acquire(
        "bybit",
        "funding",
        "BTCUSDT",
        base="BTC",
        quote="USDT",
        category="linear",
        frequency="1h",
        period=None,
        start="2024-01-01T00:00:00Z",
        end="2024-03-01T00:00:00Z",
    )
    for key in (
        "network",
        "pool_address",
        "metrics",
        "case_id",
        "expected_case_revision",
        "reason",
    ):
        assert key in seen and seen[key] is None


def test_a_window_that_fills_a_page_is_halved_until_it_fits(tmp_path: Path) -> None:
    """Hourly-funding perps overflow the 60-day page: the runner splits, never truncates."""
    calls: list[dict[str, Any]] = []

    def acquire(provider: str, family: str, instrument: str, **kwargs: Any) -> dict[str, object]:
        calls.append(kwargs)
        start = datetime.fromisoformat(kwargs["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(kwargs["end"].replace("Z", "+00:00"))
        if end - start > timedelta(days=15):
            raise DataError("Bybit bounded window fills one provider page; narrow the range")
        return {"normalized_manifest_id": f"m-{len(calls)}", "state": "qualified"}

    summary = run_backfill(
        provider="bybit",
        family="funding",
        symbols=["HOURLYUSDT"],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 3, 1),
        ledger_path=tmp_path / "ledger.json",
        acquire=acquire,
        now=NOW,
        pause_seconds=0.0,
    )
    # 60 -> 30 -> 15: one planned window, three splits, four leaves acquired.
    assert summary["windows_total"] == 1 and summary["split"] == 3
    assert summary["done"] == 4 and summary["failed"] == 0
    leaves = [
        c
        for c in calls
        if c["end"] != "2024-03-01T00:00:00Z" or c["start"] != "2024-01-01T00:00:00Z"
    ]
    assert len(calls) == 7 and len(leaves) == 6
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert sum(e["state"] == "split" for e in ledger["windows"].values()) == 3
    assert sum(e["state"] == "done" for e in ledger["windows"].values()) == 4


def test_a_one_day_window_that_still_overflows_is_recorded_failed(tmp_path: Path) -> None:
    def acquire(provider: str, family: str, instrument: str, **kwargs: Any) -> dict[str, object]:
        raise DataError("Bybit bounded window fills one provider page")

    summary = run_backfill(
        provider="bybit",
        family="derivative_bars",
        symbols=["BTCUSDT"],
        quote="USDT",
        category="linear",
        frequency="5m",
        start=date(2024, 1, 1),
        end=date(2024, 1, 4),
        ledger_path=tmp_path / "ledger.json",
        acquire=acquire,
        now=NOW,
        pause_seconds=0.0,
    )
    assert summary["done"] == 0 and summary["failed"] != 0


def test_cli_wrapper_turns_usage_errors_into_typed_data_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import typer

    from alpha_cli import crypto_data_cmds

    def boom(*args: Any, **kwargs: Any) -> dict[str, object]:
        raise typer.BadParameter("Bybit acquisition returned no observations inside the range")

    monkeypatch.setattr(crypto_data_cmds, "_acquire_result", boom)
    with pytest.raises(DataError, match="no observations"):
        crypto_data_cmds._backfill_acquire(
            "bybit",
            "funding",
            "BTCUSDT",
            base="BTC",
            quote="USDT",
            category="linear",
            frequency="1h",
            period=None,
            start="2024-01-01T00:00:00Z",
            end="2024-02-01T00:00:00Z",
        )
