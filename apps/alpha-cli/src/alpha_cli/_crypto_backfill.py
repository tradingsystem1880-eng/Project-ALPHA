"""Windowed, resumable crypto backfill over the existing bounded acquisition path (Phase B S1).

`alpha crypto-data acquire` fetches one instrument and one bounded provider page per call, and a
window that fills a page raises loudly. A multi-year, multi-symbol history is therefore thousands
of governed calls. This module plans windows that stay strictly under each provider page limit,
records progress in an atomic JSON ledger, and calls the *unchanged* acquisition function per
window, so every manifest, receipt, and quality report is exactly what a hand-typed `acquire`
would have produced. The ledger is operational state; the manifests remain the only evidence.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_core import DataError

# Windows are sized well under the provider page (Bybit funding 200 rows at 8h = 66 days;
# klines 1000 rows; open interest / ratio 200 rows per page with a cursor).
_BYBIT_SPAN_DAYS: Mapping[str, Mapping[str, int]] = {
    "funding": {"*": 60},
    "open_interest": {"*": 60},
    "long_short_ratio": {"*": 60},
    "derivative_bars": {"1h": 40, "1d": 900, "5m": 3},
    "mark_bars": {"1h": 40, "1d": 900, "5m": 3},
    "index_bars": {"1h": 40, "1d": 900, "5m": 3},
    "premium_bars": {"1h": 40, "1d": 900, "5m": 3},
}
_BINANCE_MONTHLY_FAMILIES = frozenset({"market_bars"})


@dataclass(frozen=True)
class BackfillWindow:
    """One bounded acquisition: an ISO range for Bybit, or a calendar period for Binance."""

    start: str | None
    end: str | None
    period: str | None

    @property
    def key(self) -> str:
        return f"{self.start}|{self.end}|{self.period}"


def _iso(instant: datetime) -> str:
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def plan_windows(
    provider: str,
    family: str,
    frequency: str,
    *,
    start: date,
    end: date,
    now: datetime,
) -> tuple[BackfillWindow, ...]:
    """Plan contiguous windows covering [start, end); the end is clamped below ``now``."""
    if end <= start:
        raise DataError("backfill end must be later than start")
    if provider == "binance":
        if family not in _BINANCE_MONTHLY_FAMILIES:
            raise DataError(f"backfill supports Binance market_bars monthly archives, not {family}")
        periods: list[BackfillWindow] = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            periods.append(BackfillWindow(start=None, end=None, period=f"{year:04d}-{month:02d}"))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return tuple(periods)
    if provider != "bybit":
        raise DataError(f"backfill supports bybit and binance, not {provider}")
    spans = _BYBIT_SPAN_DAYS.get(family)
    if spans is None:
        raise DataError(
            f"backfill supports Bybit {', '.join(sorted(_BYBIT_SPAN_DAYS))}, not {family}"
        )
    span_days = spans.get("*", spans.get(frequency))
    if span_days is None:
        raise DataError(
            f"backfill frequency for Bybit {family} must be one of {', '.join(sorted(spans))}"
        )
    knowledge_bound = now.astimezone(UTC).replace(second=0, microsecond=0) - timedelta(minutes=1)
    cursor = datetime(start.year, start.month, start.day, tzinfo=UTC)
    final = min(datetime(end.year, end.month, end.day, tzinfo=UTC), knowledge_bound)
    if final <= cursor:
        raise DataError("backfill start is not before the acquisition knowledge time")
    windows: list[BackfillWindow] = []
    while cursor < final:
        window_end = min(cursor + timedelta(days=span_days), final)
        windows.append(BackfillWindow(start=_iso(cursor), end=_iso(window_end), period=None))
        cursor = window_end
    return tuple(windows)


def split_symbol(symbol: str, *, quote: str) -> tuple[str, str]:
    """``BTCUSDT`` with quote ``USDT`` -> (``BTC``, ``USDT``); never guesses another quote."""
    if not symbol.endswith(quote) or len(symbol) <= len(quote):
        raise DataError(f"symbol {symbol!r} does not end with the exact quote {quote!r}")
    return symbol[: -len(quote)], quote


class Ledger:
    """Atomic JSON progress ledger keyed by ``symbol|window``; scope-checked on open."""

    def __init__(self, path: Path, body: dict[str, Any]) -> None:
        self.path = path
        self.body = body

    @classmethod
    def open(
        cls, path: Path, *, provider: str, family: str, category: str, frequency: str
    ) -> Ledger:
        scope = {
            "provider": provider,
            "family": family,
            "category": category,
            "frequency": frequency,
        }
        if path.exists():
            body = json.loads(path.read_text(encoding="utf-8"))
            existing = {key: body.get(key) for key in scope}
            if existing != scope:
                raise DataError(
                    f"ledger {path} has scope {existing}, not {scope}; use a different ledger name"
                )
            body.setdefault("windows", {})
            return cls(path, body)
        return cls(path, {"schema_version": 1, **scope, "windows": {}})

    def state(self, key: str) -> str | None:
        entry = self.body["windows"].get(key)
        return None if entry is None else str(entry["state"])

    def record(self, key: str, entry: dict[str, Any]) -> None:
        self.body["windows"][key] = entry
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)


def run_backfill(
    *,
    provider: str,
    family: str,
    symbols: Sequence[str],
    quote: str,
    category: str,
    frequency: str,
    start: date,
    end: date,
    ledger_path: Path,
    acquire: Callable[..., Mapping[str, object]],
    now: datetime,
    pause_seconds: float = 0.25,
    dry_run: bool = False,
    log: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Run every (symbol, window) not already done; failures are recorded and do not abort."""
    windows = plan_windows(provider, family, frequency, start=start, end=end, now=now)
    ledger = Ledger.open(
        ledger_path, provider=provider, family=family, category=category, frequency=frequency
    )
    counts = {"windows_total": 0, "done": 0, "failed": 0, "skipped": 0, "split": 0}
    failures: list[dict[str, str]] = []

    def _acquire_window(symbol: str, base: str, quote_asset: str, window: BackfillWindow) -> None:
        key = f"{symbol}|{window.key}"
        if ledger.state(key) == "done":
            counts["skipped"] += 1
            return
        if dry_run:
            return
        try:
            result = acquire(
                provider,
                family,
                symbol,
                base=base,
                quote=quote_asset,
                category=category,
                frequency=frequency,
                period=window.period,
                start=window.start,
                end=window.end,
            )
        except DataError as exc:
            halves = split_window(window) if _fills_a_page(exc) else None
            if halves is not None:
                # A denser-than-planned series (e.g. hourly funding): halve and retry both.
                counts["split"] += 1
                ledger.record(key, {"state": "split", "error": str(exc), "at": _iso(now)})
                if log is not None:
                    log(f"split {key}: {exc}")
                for half in halves:
                    _acquire_window(symbol, base, quote_asset, half)
                return
            counts["failed"] += 1
            failures.append({"key": key, "error": str(exc)})
            ledger.record(key, {"state": "failed", "error": str(exc), "at": _iso(now)})
            if log is not None:
                log(f"FAILED {key}: {exc}")
        else:
            counts["done"] += 1
            ledger.record(
                key,
                {
                    "state": "done",
                    "manifest_id": str(result.get("normalized_manifest_id")),
                    "quality_state": str(result.get("state")),
                    "at": _iso(now),
                },
            )
            if log is not None:
                log(f"done {key}: {result.get('normalized_manifest_id')}")
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    for symbol in symbols:
        base, quote_asset = split_symbol(symbol, quote=quote)
        for window in windows:
            counts["windows_total"] += 1
            _acquire_window(symbol, base, quote_asset, window)
    return {
        **counts,
        "dry_run": dry_run,
        "ledger": str(ledger_path),
        "failures": failures,
        "windows": [window.key for window in windows],
        "execution_authority": False,
    }


def _fills_a_page(exc: DataError) -> bool:
    return "fills one provider page" in str(exc)


def split_window(window: BackfillWindow) -> tuple[BackfillWindow, BackfillWindow] | None:
    """Halve an ISO-range window; None when it is a calendar period or already <= 1 day."""
    if window.start is None or window.end is None:
        return None
    start = datetime.fromisoformat(window.start.replace("Z", "+00:00"))
    end = datetime.fromisoformat(window.end.replace("Z", "+00:00"))
    if end - start <= timedelta(days=1):
        return None
    middle = start + (end - start) / 2
    middle = middle.replace(minute=0, second=0, microsecond=0)
    if middle <= start or middle >= end:
        return None
    return (
        BackfillWindow(start=_iso(start), end=_iso(middle), period=None),
        BackfillWindow(start=_iso(middle), end=_iso(end), period=None),
    )
