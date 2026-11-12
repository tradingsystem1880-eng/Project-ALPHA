"""Windowed, resumable crypto backfill over the existing bounded acquisition path (Phase B S1).

`alpha crypto-data acquire` fetches one instrument and one bounded provider page per call, and a
window that fills a page raises loudly. A multi-year, multi-symbol history is therefore thousands
of governed calls. This module plans windows that stay strictly under each provider page limit,
records progress in an atomic JSON ledger, and calls the *unchanged* acquisition function per
window, so every manifest, receipt, and quality report is exactly what a hand-typed `acquire`
would have produced. The ledger is operational state; the manifests remain the only evidence.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_cli._crypto_backfill_accounting import (
    FixtureAccountingBlocked,
    FixtureBackfillAccounting,
)
from alpha_cli._crypto_http_accounting import FixtureHttpAccounting
from alpha_cli._crypto_http_replay import FixtureBoundHttpAccounting
from alpha_core import DataError
from alpha_data.crypto.providers._wire import CompleteHttpResponse

# Initial windows are conservative guesses, not historical cadence/coverage guarantees.
# Funding intervals can change; a full page triggers finite window splitting below.
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


class BackfillInspectionLimit(DataError):
    """An explicitly supplied read/inspection bound was reached; no progress mutation."""


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
    max_windows: int | None = None,
) -> tuple[BackfillWindow, ...]:
    """Plan contiguous windows covering [start, end); the end is clamped below ``now``."""
    if max_windows is not None and (type(max_windows) is not int or max_windows < 1):
        raise DataError("backfill inspection window limit must be positive")
    if end <= start:
        raise DataError("backfill end must be later than start")
    if provider == "binance":
        if family not in _BINANCE_MONTHLY_FAMILIES:
            raise DataError(f"backfill supports Binance market_bars monthly archives, not {family}")
        periods: list[BackfillWindow] = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            if max_windows is not None and len(periods) >= max_windows:
                raise BackfillInspectionLimit("backfill inspection window limit reached")
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
        if max_windows is not None and len(windows) >= max_windows:
            raise BackfillInspectionLimit("backfill inspection window limit reached")
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

    def __init__(self, path: Path, body: dict[str, Any], baseline: bytes | None) -> None:
        self.path = path
        self.body = body
        self._baseline = baseline
        self._scope = {key: body[key] for key in ("provider", "family", "category", "frequency")}
        self._owner: tuple[int, int, int] | None = None

    @staticmethod
    def _read_raw(path: Path, *, max_bytes: int | None = None) -> bytes | None:
        """Read one regular unaliased progress file, never a symlink/FIFO."""
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        except FileNotFoundError:
            return None
        except OSError:
            raise DataError("backfill progress cannot be opened safely") from None
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise DataError("backfill progress must be a regular non-hardlinked file")
            if max_bytes is not None and before.st_size > max_bytes:
                raise BackfillInspectionLimit("backfill inspection ledger byte limit reached")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read() if max_bytes is None else stream.read(max_bytes)
            after, named = os.fstat(fd), path.stat(follow_symlinks=False)
            if (
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (after.st_dev, after.st_ino) != (named.st_dev, named.st_ino)
                or after.st_nlink != 1
                or len(raw) != before.st_size
            ):
                raise DataError("backfill progress changed during read")
            return raw
        except OSError:
            raise DataError("backfill progress is unavailable during read") from None
        finally:
            os.close(fd)

    def _check_owner(self) -> None:
        if self._owner is None or self._owner[1:] != (os.getpid(), threading.get_ident()):
            raise DataError("backfill progress ownership is not transferable")
        fd = self._owner[0]
        held = os.fstat(fd)
        try:
            named = self.path.with_name(self.path.name + ".lock").stat(follow_symlinks=False)
        except OSError:
            raise DataError("backfill progress lock identity is unavailable") from None
        if (
            not stat.S_ISREG(named.st_mode)
            or held.st_nlink != 1
            or named.st_nlink != 1
            or (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise DataError("backfill progress lock identity changed")

    @contextmanager
    def exclusive(self, *, refresh: bool = False) -> Iterator[None]:
        """Nonblocking cooperative ownership; never delete the persistent sidecar.

        A run reloads under ownership. Standalone mutators refuse stale snapshots.
        No SQLite transaction may surround this context. Ownership is PID/thread-
        bound; inherited descriptors confer no mutation authority on forked code.
        """
        if self._owner is not None:
            self._check_owner()
            yield
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        try:
            fd = os.open(
                lock_path,
                os.O_RDWR | os.O_CREAT | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
            )
        except OSError:
            raise DataError("backfill progress lock cannot be opened safely") from None
        pid = os.getpid()
        acquired = False
        token: tuple[int, int, int] | None = None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise DataError("backfill progress lock must be regular and non-hardlinked")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                raise DataError(
                    "backfill progress already owned; retry after owner exits"
                ) from None
            token = (fd, pid, threading.get_ident())
            self._owner = token
            self._check_owner()
            latest = type(self).open(self.path, **self._scope)
            if refresh:
                self.body, self._baseline = latest.body, latest._baseline
            elif latest._baseline != self._baseline:
                raise DataError("backfill progress snapshot is stale; reopen before mutation")
            yield
        finally:
            if token is not None and self._owner is token:
                self._owner = None
            # Never explicitly unlock an inherited open-file description in a child.
            try:
                if acquired and os.getpid() == pid:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        provider: str,
        family: str,
        category: str,
        frequency: str,
        max_bytes: int | None = None,
    ) -> Ledger:
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 1):
            raise DataError("backfill inspection ledger byte limit must be positive")
        path = path.parent.resolve() / path.name
        scope = {
            "provider": provider,
            "family": family,
            "category": category,
            "frequency": frequency,
        }
        raw = cls._read_raw(path, max_bytes=max_bytes)
        if raw is not None:
            try:
                body = json.loads(raw.decode("utf-8"))
            except (OSError, ValueError) as exc:
                raise DataError("backfill progress is unavailable or corrupt") from exc
            if (
                not isinstance(body, dict)
                or body.get("schema_version") != 1
                or not isinstance(body.get("windows"), dict)
            ):
                raise DataError("backfill progress requires a complete version-1 window ledger")
            existing = {key: body.get(key) for key in scope}
            if existing != scope:
                raise DataError(
                    f"ledger {path} has scope {existing}, not {scope}; use a different ledger name"
                )
            return cls(path, body, raw)
        return cls(path, {"schema_version": 1, **scope, "windows": {}}, None)

    @property
    def source_sha256(self) -> str | None:
        """Hash of actually read progress bytes; missing progress stays unknown."""
        return None if self._baseline is None else hashlib.sha256(self._baseline).hexdigest()

    def requested_leaves(
        self, symbol: str, window: BackfillWindow, *, visit: Callable[[], None] | None = None
    ) -> list[BackfillWindow]:
        """Pure requested split topology, shared by execution and read-only inspection."""
        if visit is not None:
            visit()
        key = f"{symbol}|{window.key}"
        state = self.state(key)
        if state != "split":
            if state != "done" and window.start is not None and window.end is not None:
                prefix = f"{symbol}|"
                for retained_key in self.body["windows"]:
                    if retained_key == key or not retained_key.startswith(prefix):
                        continue
                    parts = retained_key[len(prefix) :].split("|")
                    if (
                        len(parts) == 3
                        and parts[2] == "None"
                        and window.start <= parts[0] < parts[1] <= window.end
                    ):
                        raise DataError(
                            "retained backfill child progress has no split parent; "
                            "reconcile retained topology before resume"
                        )
            return [window]
        halves = split_window(window)
        if halves is None:
            raise DataError("retained backfill split cannot be reopened")
        return [
            leaf for half in halves for leaf in self.requested_leaves(symbol, half, visit=visit)
        ]

    def state(self, key: str) -> str | None:
        entry = self.entry(key)
        return None if entry is None else str(entry["state"])

    def entry(self, key: str) -> dict[str, Any] | None:
        if key not in self.body["windows"]:
            return None
        entry = self.body["windows"][key]
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("state"), str)
            or entry["state"] not in {"done", "failed", "split"}
        ):
            raise DataError("retained backfill window state is invalid")
        return entry

    def record(self, key: str, entry: dict[str, Any]) -> None:
        with self.exclusive():
            self.body["windows"][key] = entry
            self.save()

    def save(self) -> None:
        with self.exclusive():
            self._check_owner()
            if self._read_raw(self.path) != self._baseline:
                raise DataError("backfill progress snapshot is stale; reopen before mutation")
            encoded = (json.dumps(self.body, indent=2, sort_keys=True) + "\n").encode("utf-8")
            tmp: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=self.path.name + ".",
                    suffix=".tmp",
                    dir=self.path.parent,
                    delete=False,
                ) as stream:
                    tmp = Path(stream.name)
                    stream.write(encoded)
                self._check_owner()
                if self._read_raw(self.path) != self._baseline:
                    raise DataError("backfill progress changed before replacement")
                os.replace(tmp, self.path)
                self._baseline = encoded
            finally:
                if tmp is not None:
                    tmp.unlink(missing_ok=True)


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
    verify_completed: Callable[[str, BackfillWindow, Mapping[str, object]], None] | None = None,
    fixture_accounting: FixtureBackfillAccounting | None = None,
    fixture_http_accounting: FixtureHttpAccounting | None = None,
    fixture_http_response_evidence: Callable[[CompleteHttpResponse], None] | None = None,
) -> dict[str, object]:
    """Run every (symbol, window) not already done; failures are recorded and do not abort."""
    if fixture_http_response_evidence is not None and (
        fixture_http_accounting is None
        or not callable(fixture_http_response_evidence)
        or isinstance(fixture_http_accounting, FixtureBoundHttpAccounting)
    ):
        raise FixtureAccountingBlocked("EXPLICIT_HTTP_ACCOUNTING_REQUIRED_FOR_RESPONSE_EVIDENCE")
    if fixture_http_accounting is not None:
        if (
            type(fixture_http_accounting) not in (FixtureHttpAccounting, FixtureBoundHttpAccounting)
            or provider != "bybit"
            or fixture_accounting is not None
        ):
            raise FixtureAccountingBlocked("EXPLICIT_BYBIT_HTTP_ACCOUNTING_REQUIRED")
        fixture_http_accounting.check_idle_owner()
    if fixture_accounting is not None and type(fixture_accounting) is not FixtureBackfillAccounting:
        raise FixtureAccountingBlocked("EXPLICIT_FIXTURE_ACCOUNTING_REQUIRED")
    if fixture_accounting is not None:
        fixture_accounting.check_idle_owner()
    windows = plan_windows(provider, family, frequency, start=start, end=end, now=now)
    ledger = Ledger.open(
        ledger_path, provider=provider, family=family, category=category, frequency=frequency
    )
    # All current executing writers own the whole progress resource before reload,
    # preflight, deduplication, acquisition and replacement. Dry-run is read-only.
    with ledger.exclusive(refresh=True) if not dry_run else nullcontext():
        counts = {"windows_total": 0, "done": 0, "failed": 0, "skipped": 0, "split": 0}
        failures: list[dict[str, str]] = []
        identities = [(symbol, *split_symbol(symbol, quote=quote)) for symbol in symbols]
        verified: set[str] = set()

        def leaves(symbol: str, window: BackfillWindow) -> list[BackfillWindow]:
            return ledger.requested_leaves(symbol, window)

        def verify(symbol: str, window: BackfillWindow) -> None:
            key = f"{symbol}|{window.key}"
            if key in verified:
                return
            if verify_completed is None:
                raise DataError(
                    "completed backfill windows require evidence verification before resume"
                )
            entry = ledger.entry(key)
            assert entry is not None
            ledger._check_owner()
            verify_completed(symbol, window, entry)
            if fixture_http_accounting is not None:
                fixture_http_accounting.verify_window(
                    ledger,
                    (provider, family, symbol),
                    {
                        "base": split_symbol(symbol, quote=quote)[0],
                        "quote": quote,
                        "category": category,
                        "frequency": frequency,
                        "period": window.period,
                        "start": window.start,
                        "end": window.end,
                    },
                    entry,
                )
            if fixture_accounting is not None:
                fixture_accounting.verify_done(
                    ledger,
                    (provider, family, symbol),
                    {
                        "base": split_symbol(symbol, quote=quote)[0],
                        "quote": quote,
                        "category": category,
                        "frequency": frequency,
                        "period": window.period,
                        "start": window.start,
                        "end": window.end,
                    },
                )
            verified.add(key)

        # Verify every requested completed leaf BEFORE any new acquisition, including
        # children below retained splits. Unrelated symbols/ranges are not this request.
        for symbol, _base, _quote in identities:
            for window in windows:
                for leaf in leaves(symbol, window):
                    if ledger.state(f"{symbol}|{leaf.key}") == "done" and not dry_run:
                        verify(symbol, leaf)

        def _acquire_window(
            symbol: str, base: str, quote_asset: str, window: BackfillWindow
        ) -> None:
            key = f"{symbol}|{window.key}"
            if ledger.state(key) == "done":
                if not dry_run:
                    verify(symbol, window)
                counts["skipped"] += 1
                return
            if ledger.state(key) == "split":
                halves = split_window(window)
                assert halves is not None  # validated by the all-window preflight
                for half in halves:
                    _acquire_window(symbol, base, quote_asset, half)
                return
            if dry_run:
                return
            try:
                ledger._check_owner()
                args = (provider, family, symbol)
                parameters: dict[str, object] = {
                    "base": base,
                    "quote": quote_asset,
                    "category": category,
                    "frequency": frequency,
                    "period": window.period,
                    "start": window.start,
                    "end": window.end,
                }
                if fixture_http_response_evidence is not None:
                    parameters["http_response_evidence"] = fixture_http_response_evidence
                if fixture_http_accounting is not None:
                    result = fixture_http_accounting.dispatch_window(
                        ledger, acquire, args, parameters
                    )
                elif fixture_accounting is not None:
                    result = fixture_accounting.dispatch(ledger, acquire, args, parameters)
                else:
                    result = acquire(*args, **parameters)
            except FixtureAccountingBlocked:
                # Fatal accounting uncertainty/refusal must never split, log raw callback
                # exceptions, or continue into another potentially effectful window.
                raise
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
                entry: dict[str, Any] = {"state": "failed", "error": str(exc), "at": _iso(now)}
                if exc.__cause__ is not None:
                    entry["cause"] = repr(
                        exc.__cause__
                    )  # the wire layer chains the transport error
                ledger.record(key, entry)
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
                        **(
                            fixture_http_accounting.completion_fields(result)
                            if fixture_http_accounting is not None
                            else {}
                        ),
                    },
                )
                if log is not None:
                    log(f"done {key}: {result.get('normalized_manifest_id')}")
            if pause_seconds > 0:
                time.sleep(pause_seconds)

        for symbol, base, quote_asset in identities:
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
            "verified_completed": len(verified),
            "resume_verification": "not_run_dry_run"
            if dry_run
            else "verified"
            if verified
            else "not_needed",
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
