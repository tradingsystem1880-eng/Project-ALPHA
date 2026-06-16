# Phase 1b-ii — Timezone/Date Convention + Crypto (ccxt) Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the timezone day-shift hard-gate (daily bars normalized to session-date @ 00:00 UTC, venue-agnostic) and add a second data source — a crypto adapter via ccxt — on the existing `DataAdapter` seam.

**Architecture:** A daily bar is date-keyed. We normalize every daily bar's `ts` to **midnight UTC of its local session date**, so `ts.date()` equals the session calendar date for any venue (US, Tokyo, Sydney) and the corporate-action `ex_date` derives consistently. The 1a firewall is hardened to gate knowledge-time on `when.astimezone(UTC).date()`. The ccxt adapter mirrors the yfinance one: a pure offline parser (`parse_ccxt_ohlcv`: ccxt OHLCV list → `FetchResult`, no corporate actions) + a live `CCXTAdapter` (lazy ccxt import, network-gated smoke). Crypto is UTC-native and slash-symboled (`BTC/USD`) — both already handled by the store/snapshot.

**Tech Stack:** Python 3.12 · ccxt (lazy import in the adapter) · Polars · pydantic · pytest (`network` marker for live smoke).

**Key decision (flagged for review):** daily bars are stored as **session-date @ 00:00 UTC**. Backward-compatible with existing UTC fixtures; fixes positive-UTC-offset venues. Intraday (out of scope) would revisit this.

**Scope:** tz fix + ccxt crypto adapter only. FX (Dukascopy), FRED macro, dividend total-return adjustment, and DuckDB ASOF remain in later plans.

**Branch:** `phase-1b-ii-tz-crypto` off `main`. Do not push (finish step handles it).

---

## File Map

```
packages/alpha-data/src/alpha_data/adapters/
├── yfinance_adapter.py     # MODIFY: _to_utc → _session_ts (date-normalize to 00:00 UTC)
├── ccxt_adapter.py         # CREATE: parse_ccxt_ohlcv (pure) + CCXTAdapter (live)
packages/alpha-data/src/alpha_data/pit.py   # MODIFY: knowledge gate uses when.astimezone(UTC).date()
packages/alpha-data/pyproject.toml          # MODIFY: add ccxt
apps/alpha-cli/src/alpha_cli/data_cmds.py   # MODIFY: register "crypto" in _ADAPTERS
tests/
├── unit/
│   ├── test_session_ts.py          # CREATE: Tokyo/Sydney/US date-normalization
│   ├── test_yfinance_parser.py     # MODIFY: add a non-US (Tokyo) parse test
│   ├── test_ccxt_parser.py         # CREATE: ccxt OHLCV → bars, no actions, UTC
│   └── test_pit_tz.py              # CREATE: firewall consistent with non-UTC `when`
├── integration/
│   ├── test_data_cli.py            # MODIFY: add a crypto fake-adapter path
│   └── test_ccxt_live.py           # CREATE: @pytest.mark.network live ccxt smoke
└── fixtures/
    └── ccxt_fixtures.py            # CREATE: a ccxt-shaped OHLCV list builder
```

---

## Task 0: Branch
- [ ] `cd /Users/hunternovotny/Desktop/Project-ALPHA && git checkout main && git checkout -b phase-1b-ii-tz-crypto`

---

## Task 1: Timezone/date convention fix

**Files:** Modify `adapters/yfinance_adapter.py`, `pit.py`; Create `tests/unit/test_session_ts.py`, `tests/unit/test_pit_tz.py`; Modify `tests/unit/test_yfinance_parser.py`.

- [ ] **Step 1: Write the failing date-normalization test**

Create `tests/unit/test_session_ts.py`:
```python
from datetime import UTC, datetime, timedelta, timezone

import pandas as pd

from alpha_data.adapters.yfinance_adapter import _session_ts

TOKYO = timezone(timedelta(hours=9))
SYDNEY = timezone(timedelta(hours=11))
NY = timezone(timedelta(hours=-4))


def test_session_ts_preserves_local_date_across_offsets() -> None:
    # local midnight in each venue must map to that SAME calendar date at 00:00 UTC
    assert _session_ts(pd.Timestamp("2024-03-15 00:00", tz=TOKYO)) == datetime(2024, 3, 15, tzinfo=UTC)
    assert _session_ts(pd.Timestamp("2024-03-15 00:00", tz=SYDNEY)) == datetime(2024, 3, 15, tzinfo=UTC)
    assert _session_ts(pd.Timestamp("2020-08-31 00:00", tz=NY)) == datetime(2020, 8, 31, tzinfo=UTC)
    assert _session_ts(pd.Timestamp("2024-01-02 00:00", tz=UTC)) == datetime(2024, 1, 2, tzinfo=UTC)


def test_session_ts_handles_naive() -> None:
    assert _session_ts(pd.Timestamp("2024-01-02 00:00")) == datetime(2024, 1, 2, tzinfo=UTC)
```

- [ ] **Step 2: Run, verify fail** — `uv run pytest tests/unit/test_session_ts.py -q` → `ImportError: cannot import name '_session_ts'`.

- [ ] **Step 3: Replace `_to_utc` with `_session_ts` in `yfinance_adapter.py`**

Replace the `_to_utc` function with:
```python
def _session_ts(ts: pd.Timestamp) -> datetime:
    """Daily bar → midnight UTC of the bar's LOCAL session date.

    A daily bar is date-keyed, not instant-keyed. yfinance's daily index is local-midnight;
    taking the local calendar date and stamping it at 00:00 UTC makes `ts.date()` the session
    date for ANY venue (US, Tokyo, Sydney) and keeps the corporate-action ex_date consistent.
    """
    d = ts.to_pydatetime().date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC)
```
In `parse_yfinance_history`, change `ts = _to_utc(pd.Timestamp(idx))  # type: ignore[arg-type]` to `ts = _session_ts(pd.Timestamp(idx))  # type: ignore[arg-type]`. (The `ex: date = ts.date()` line already derives the ex-date from `ts`, so it now uses the session date — no other change needed.)

- [ ] **Step 4: Run, verify pass** — `uv run pytest tests/unit/test_session_ts.py -q` → PASS. Also `uv run pytest tests/unit/test_yfinance_parser.py -q` → still PASS (the existing UTC fixture is unchanged by normalization).

- [ ] **Step 5: Add a non-US yfinance parse test**

Append to `tests/unit/test_yfinance_parser.py`:
```python
def test_parse_non_us_session_date_preserved() -> None:
    from datetime import timedelta, timezone

    tokyo = timezone(timedelta(hours=9))
    df = yf_history(
        [{"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1.0,
          "Dividends": 0.0, "Stock Splits": 2.0}],
        [datetime(2024, 3, 15, tzinfo=tokyo)],
    )
    result = parse_yfinance_history(df, "7203.T")
    assert result.bars["ts"].to_list()[0] == datetime(2024, 3, 15, tzinfo=UTC)  # not 3/14
    assert result.actions[0].ex_date == date(2024, 3, 15)  # split ex-date is the LOCAL session date
```

- [ ] **Step 6: Harden the firewall knowledge gate for non-UTC `when`**

In `packages/alpha-data/src/alpha_data/pit.py`, change the knowledge-gate line from
`known = known_actions(self._actions.get(symbol, []), when.date())`
to
`known = known_actions(self._actions.get(symbol, []), when.astimezone(UTC).date())`
and add `from datetime import UTC` to the imports (keep `datetime`). This makes the action availability gate use the UTC session date regardless of `when`'s tz, matching the bar normalization.

- [ ] **Step 7: Write the firewall-tz test**

Create `tests/unit/test_pit_tz.py`:
```python
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpha_core import ActionType, CorporateAction
from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_knowledge_gate_uses_utc_date_for_non_utc_when(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("X", linear_bars("X", date(2024, 1, 1), 10))
    split = CorporateAction(symbol="X", action_type=ActionType.SPLIT,
                            ex_date=date(2024, 1, 8), announce_date=date(2024, 1, 5), ratio=2.0)
    reader = PointInTimeReader(store, actions={"X": [split]})
    # `when` just after midnight in UTC+14 is still 2024-01-04 in UTC → split NOT yet known
    tz_plus = timezone(timedelta(hours=14))
    out = reader.as_of("X", datetime(2024, 1, 5, 1, 0, tzinfo=tz_plus))  # = 2024-01-04 11:00 UTC
    pre = out.filter(out["ts"] < datetime(2024, 1, 8, tzinfo=UTC))
    assert pre["close"].to_list() == linear_bars("X", date(2024, 1, 1), 4)["close"].to_list()
```

- [ ] **Step 8: Run + commit**

Run: `uv run pytest tests/unit/test_session_ts.py tests/unit/test_yfinance_parser.py tests/unit/test_pit_tz.py -q` → PASS.
```bash
git add packages/alpha-data/src/alpha_data/adapters/yfinance_adapter.py packages/alpha-data/src/alpha_data/pit.py tests/unit/test_session_ts.py tests/unit/test_pit_tz.py tests/unit/test_yfinance_parser.py
git commit -m "fix(data): normalize daily bars to session-date@00:00 UTC; UTC knowledge gate (tz day-shift)"
```

---

## Task 2: ccxt crypto parser (offline)

**Files:** Modify `packages/alpha-data/pyproject.toml`; Create `adapters/ccxt_adapter.py`, `tests/fixtures/ccxt_fixtures.py`, `tests/unit/test_ccxt_parser.py`.

- [ ] **Step 1: Add ccxt dependency** — in `packages/alpha-data/pyproject.toml` deps add `"ccxt>=4.0"`; then `uv sync`.

- [ ] **Step 2: Create the fixture**

Create `tests/fixtures/ccxt_fixtures.py`:
```python
"""Build a ccxt-shaped OHLCV list: [[ms_timestamp, open, high, low, close, volume], ...]."""
from __future__ import annotations


def ccxt_ohlcv() -> list[list[float]]:
    # 2024-01-01, 2024-01-02, 2024-01-03 (UTC midnight in ms)
    return [
        [1704067200000, 42000.0, 43000.0, 41500.0, 42500.0, 1000.0],
        [1704153600000, 42500.0, 44000.0, 42400.0, 43800.0, 1200.0],
        [1704240000000, 43800.0, 44200.0, 43000.0, 43500.0, 900.0],
    ]
```

- [ ] **Step 3: Write failing parser test**

Create `tests/unit/test_ccxt_parser.py`:
```python
from datetime import UTC, datetime

import pytest

from alpha_core import DataError
from alpha_data.adapters.ccxt_adapter import parse_ccxt_ohlcv
from tests.fixtures.ccxt_fixtures import ccxt_ohlcv


def test_parse_ccxt_to_raw_bars_no_actions() -> None:
    result = parse_ccxt_ohlcv(ccxt_ohlcv(), "BTC/USD")
    assert result.symbol == "BTC/USD"
    assert result.actions == []  # crypto has no splits/dividends
    assert result.bars["close"].to_list() == [42500.0, 43800.0, 43500.0]
    assert result.bars["ts"].to_list()[0] == datetime(2024, 1, 1, tzinfo=UTC)


def test_parse_ccxt_fails_loud_on_bad_ohlc() -> None:
    bad = [[1704067200000, 10.0, 5.0, 9.0, 8.0, 1.0]]  # high < open
    with pytest.raises(DataError):
        parse_ccxt_ohlcv(bad, "X/Y")
```

- [ ] **Step 4: Run, verify fail** — `ModuleNotFoundError: alpha_data.adapters.ccxt_adapter`.

- [ ] **Step 5: Implement**

Create `packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py`:
```python
"""ccxt crypto adapter: raw daily OHLCV (UTC-native, no corporate actions)."""
from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
from pydantic import ValidationError

from alpha_core import Bar, DataError
from alpha_data.adapters.base import FetchResult

_VERSION = "1"
PARSER_VERSION = "1"


def parse_ccxt_ohlcv(ohlcv: list[list[float]], symbol: str) -> FetchResult:
    """Convert a ccxt fetch_ohlcv list ([ms, o, h, l, c, v], ...) to a FetchResult.

    Validates each row via Bar (1a invariants) — fails loud on bad data. No corporate actions.
    """
    rows: list[dict[str, object]] = []
    for ms, o, h, low, c, v in ohlcv:
        ts = datetime.fromtimestamp(ms / 1000, tz=UTC)
        try:
            Bar(symbol=symbol, ts=ts, open=float(o), high=float(h), low=float(low),
                close=float(c), volume=float(v))
        except ValidationError as exc:
            raise DataError(f"invalid ccxt bar for {symbol} at {ts}: {exc}") from exc
        rows.append({"ts": ts, "open": float(o), "high": float(h), "low": float(low),
                     "close": float(c), "volume": float(v)})
    bars = pl.DataFrame(rows, schema={"ts": pl.Datetime(time_zone="UTC"), "open": pl.Float64,
                                      "high": pl.Float64, "low": pl.Float64, "close": pl.Float64,
                                      "volume": pl.Float64})
    return FetchResult(symbol=symbol, bars=bars, actions=[])


class CCXTAdapter:
    """Live crypto adapter via ccxt. Defaults to a US-accessible, key-free exchange."""

    name = "ccxt"
    version = _VERSION
    parser_version = PARSER_VERSION

    def __init__(self, exchange: str = "kraken") -> None:
        self._exchange = exchange

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        import ccxt  # noqa: PLC0415 — lazy import keeps module import network-free

        ex = getattr(ccxt, self._exchange)()
        since = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp() * 1000)
        raw = ex.fetch_ohlcv(symbol, timeframe="1d", since=since)
        end_ms = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp() * 1000)
        raw = [r for r in raw if r[0] <= end_ms]
        if not raw:
            raise DataError(f"ccxt returned no data for {symbol} {start}..{end}")
        return parse_ccxt_ohlcv(raw, symbol)
```

- [ ] **Step 6: Run, verify pass** — `uv run pytest tests/unit/test_ccxt_parser.py -q` → PASS.

- [ ] **Step 7: Commit**
```bash
git add packages/alpha-data/pyproject.toml packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py tests/fixtures/ccxt_fixtures.py tests/unit/test_ccxt_parser.py
git commit -m "feat(data): ccxt crypto adapter — pure OHLCV parser + live fetch (UTC, no actions)"
```

---

## Task 3: Register crypto in the CLI + live smoke

**Files:** Modify `apps/alpha-cli/src/alpha_cli/data_cmds.py`, `tests/integration/test_data_cli.py`; Create `tests/integration/test_ccxt_live.py`.

- [ ] **Step 1: Register the adapter**

In `data_cmds.py`, import `CCXTAdapter` and add it to the registry:
```python
from alpha_data.adapters.ccxt_adapter import CCXTAdapter
...
_ADAPTERS: dict[str, type] = {"yfinance": YFinanceAdapter, "ccxt": CCXTAdapter}
```

- [ ] **Step 2: Add an offline CLI test for the crypto path**

Append to `tests/integration/test_data_cli.py`:
```python
class _FakeCrypto:
    name = "ccxt"
    version = "1"
    parser_version = "1"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        from alpha_data.adapters.ccxt_adapter import parse_ccxt_ohlcv
        from tests.fixtures.ccxt_fixtures import ccxt_ohlcv

        return parse_ccxt_ohlcv(ccxt_ohlcv(), symbol)


def test_pull_crypto_slash_symbol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _FakeCrypto})
    r1 = runner.invoke(app, ["data", "pull", "BTC/USD", "--source", "ccxt",
                             "--start", "2024-01-01", "--end", "2024-01-04"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["data", "snapshot", "csnap", "BTC/USD", "--source", "ccxt"])
    assert r2.exit_code == 0, r2.output
    r3 = runner.invoke(app, ["data", "verify", "csnap"])
    assert r3.exit_code == 0, r3.output
```

- [ ] **Step 3: Add the network-gated live smoke**

Create `tests/integration/test_ccxt_live.py`:
```python
"""Live ccxt smoke test — skipped in CI/offline (run locally with -m network)."""
from __future__ import annotations

from datetime import date

import pytest

from alpha_data.adapters.ccxt_adapter import CCXTAdapter

pytestmark = pytest.mark.network


def test_ccxt_live_pull_btc() -> None:
    result = CCXTAdapter().fetch("BTC/USD", date(2024, 1, 1), date(2024, 1, 15))
    assert result.bars.height > 5
    assert result.actions == []
```

- [ ] **Step 4: Run + verify** — `uv run pytest tests/integration/test_data_cli.py -q` → PASS; `uv run alpha data pull --help` works. Report what `uv run pytest -m network -q` does (live ccxt; pass/skip/error all acceptable, must not gate CI).

- [ ] **Step 5: Commit**
```bash
git add apps/alpha-cli/src/alpha_cli/data_cmds.py tests/integration/test_data_cli.py tests/integration/test_ccxt_live.py
git commit -m "feat(cli): register ccxt crypto source; offline crypto CLI test + live smoke"
```

---

## Task 4: Final gate

- [ ] **Step 1: Full gate**
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy packages apps tests && uv run lint-imports && uv run pytest -q -m "not network" && uv run pytest -m bias_guard -q
```
Expected: all green; `lint-imports` 5 kept / 0 broken; bias_guard now 6 (the 5 prior + `test_pit_tz`).
- [ ] **Step 2: Fix anything red, re-run until green.** ccxt has no type stubs → `import ccxt` is lazy inside `fetch`; if mypy flags it, add `# type: ignore[import-untyped]` with the reason `# ccxt has no stubs` (mirrors the yfinance approach).
- [ ] **Step 3: Commit if fixes** — `git add -A && git commit -m "chore(data): phase-1b-ii gate green"`.

---

## Done = Phase 1b-ii complete
- Daily bars normalize to session-date @ 00:00 UTC; a Tokyo +09:00 bar keeps date 2024-03-15 (not 3/14); ex_date is the local session date. Firewall gates knowledge-time on UTC date.
- ccxt crypto adapter pulls raw UTC OHLCV (no actions), fails loud on bad data, parser offline-tested; `alpha data pull BTC/USD --source ccxt` works through store→snapshot→verify (slash-symbol safe).
- Full gate green; CI still `-m "not network"`; a live ccxt smoke exists, excluded from CI.

**Next:** Phase 1b-iii — FX (Dukascopy) + FRED macro adapters; then dividend total-return adjustment + DuckDB ASOF. Then settle the PIT seam before the Phase 2 engine.

## Notes / risks
- **ccxt default exchange `kraken`** is US-accessible and key-free for public OHLCV; `Binance.com` is geo-blocked from US IPs (use `binanceus`/`kraken`/`coinbase`). The live smoke may rate-limit/flake — it's `network`-gated, never gates CI.
- The tz normalization is intentionally **daily-bar specific**. Intraday data (future) needs true instants — revisit `_session_ts` then.
- ccxt is a heavy dependency; it's imported lazily so module import stays network-free and fast.
