# Phase 1b-i — Ingestion Framework + yfinance Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the first real data source end-to-end — a `DataAdapter` interface, corporate-action storage, a yfinance equities adapter (raw OHLC + splits/dividends), immutable provenance-tracked snapshots, and an `alpha data` CLI — so we can pull real equity history (with real splits) through the 1a point-in-time firewall.

**Architecture:** Adapters live in `alpha_data.adapters` and return a `FetchResult(symbol, bars: pl.DataFrame, actions: list[CorporateAction])`. The yfinance adapter's pure *parse* function (pandas → `FetchResult`) is offline-unit-tested with constructed fixtures (incl. a split + dividend); the *live* fetch is a network-gated smoke test skipped in CI. `ParquetStore` gains corporate-action storage (JSON, exact pydantic round-trip). Snapshots freeze raw bars + actions into a content-hashed directory with a `manifest.json` recording provenance (source, adapter & parser version, params, per-file sha256). `alpha data pull|snapshot|verify` ties it together. Ingestion fails loud on broken vendor data (each row must form a valid `Bar`).

**Tech Stack:** Python 3.12 · yfinance (pulls pandas, used only at the adapter edge) · Polars · pydantic · pytest (+ a `network` marker for the gated smoke test).

**Scope decisions (explicit):**
- **yfinance only** in 1b-i (other sources → 1b-ii). yfinance pulled with `auto_adjust=False`, `actions=True` to get RAW OHLCV + `Dividends`/`Stock Splits`.
- **Announce dates aren't available from yfinance** → `CorporateAction.announce_date=None` (conservative `knowledge_time = ex_date`, `knowledge_is_estimated=True`), exactly the 1a fallback.
- **Dividend total-return *adjustment* stays deferred to 1b-iii** — but dividends are *captured & stored* now (as `DIVIDEND` actions) so the data is complete.
- **Fail loud on bad data:** the pull pipeline validates each row by constructing a `Bar` (reusing 1a invariants); a NaN/inconsistent row raises `DataError` rather than being stored silently.

**Branch:** all work on `phase-1b-i-ingestion` (off `main`). Do not push (the remote exists now; pushing happens via the finish step if chosen).

---

## File Map

```
packages/alpha-data/src/alpha_data/
├── store.py                    # MODIFY: add write_actions/read_actions (JSON)
├── adapters/
│   ├── __init__.py             # CREATE
│   ├── base.py                 # CREATE: FetchResult + DataAdapter protocol
│   └── yfinance_adapter.py     # CREATE: parse_yfinance_history (pure) + YFinanceAdapter (live)
├── ingest.py                   # CREATE: validate-and-store pipeline (fail-loud)
├── snapshot.py                 # CREATE: snapshot + manifest + verify
packages/alpha-data/pyproject.toml   # MODIFY: add yfinance
apps/alpha-cli/src/alpha_cli/
├── main.py                     # MODIFY: register the `data` sub-app
└── data_cmds.py                # CREATE: pull / snapshot / verify commands
pyproject.toml                  # MODIFY: register `network` pytest marker
tests/
├── unit/
│   ├── test_actions_store.py       # CREATE: corp-action JSON round-trip
│   ├── test_yfinance_parser.py     # CREATE: offline parse (split+dividend → raw bars+actions)
│   ├── test_ingest.py              # CREATE: fail-loud on bad rows
│   └── test_snapshot.py            # CREATE: snapshot + manifest + verify (+ tamper detection)
├── integration/
│   ├── test_data_cli.py            # CREATE: CLI via a fake offline adapter
│   └── test_yfinance_live.py       # CREATE: @pytest.mark.network live smoke (skipped in CI)
└── fixtures/
    └── yf_fixtures.py              # CREATE: a yfinance-shaped pandas DataFrame builder
```

---

## Task 0: Branch

- [ ] **Step 1:** `cd /Users/hunternovotny/Desktop/Project-ALPHA && git checkout main && git checkout -b phase-1b-i-ingestion`
  Expected: `Switched to a new branch 'phase-1b-i-ingestion'`.

---

## Task 1: Corporate-action storage in `ParquetStore`

**Files:** Modify `packages/alpha-data/src/alpha_data/store.py`; Test `tests/unit/test_actions_store.py`.

- [ ] **Step 1: Write failing round-trip test**

Create `tests/unit/test_actions_store.py`:
```python
from datetime import date
from pathlib import Path

import pytest

from alpha_core import ActionType, CorporateAction, DataError
from alpha_data.store import ParquetStore


def _actions() -> list[CorporateAction]:
    return [
        CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT,
                        ex_date=date(2020, 8, 31), ratio=4.0),
        CorporateAction(symbol="AAPL", action_type=ActionType.DIVIDEND,
                        ex_date=date(2020, 8, 7), amount=0.82),
    ]


def test_actions_round_trip(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_actions("AAPL", _actions())
    out = store.read_actions("AAPL")
    assert out == _actions()  # exact pydantic equality


def test_read_actions_missing_returns_empty(tmp_path: Path) -> None:
    # absence of actions is normal (e.g. crypto) — return [], not an error
    assert ParquetStore(tmp_path).read_actions("NONE") == []


def test_actions_symbol_sanitized(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    with pytest.raises(DataError):
        store.write_actions("../x", [])
```

- [ ] **Step 2: Run, verify fail**

Run: `cd /Users/hunternovotny/Desktop/Project-ALPHA && uv run pytest tests/unit/test_actions_store.py -q`
Expected: FAIL — `AttributeError: 'ParquetStore' object has no attribute 'write_actions'`.

- [ ] **Step 3: Implement action storage (JSON)**

In `packages/alpha-data/src/alpha_data/store.py`, add `import json`, `from alpha_core import CorporateAction` to the imports, and these methods to `ParquetStore` (reuse the existing `_bars_path` sanitization by factoring a helper):
```python
    def _actions_path(self, symbol: str) -> Path:
        if not symbol or ".." in symbol or "\\" in symbol or symbol.startswith("/"):
            raise DataError(f"invalid symbol for storage: {symbol!r}")
        return self.root / "actions" / f"{symbol}.json"

    def write_actions(self, symbol: str, actions: list[CorporateAction]) -> Path:
        path = self._actions_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [a.model_dump(mode="json") for a in actions]
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path

    def read_actions(self, symbol: str) -> list[CorporateAction]:
        path = self._actions_path(symbol)
        if not path.exists():
            return []
        raw = json.loads(path.read_text())
        return [CorporateAction.model_validate(d) for d in raw]
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest tests/unit/test_actions_store.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add packages/alpha-data/src/alpha_data/store.py tests/unit/test_actions_store.py
git commit -m "feat(data): corporate-action JSON storage in ParquetStore"
```

---

## Task 2: `DataAdapter` interface + `FetchResult`

**Files:** Create `packages/alpha-data/src/alpha_data/adapters/__init__.py`, `.../adapters/base.py`.

- [ ] **Step 1: Create the adapters package**

Create `packages/alpha-data/src/alpha_data/adapters/__init__.py`:
```python
"""Data source adapters."""
from __future__ import annotations
```

- [ ] **Step 2: Create the interface**

Create `packages/alpha-data/src/alpha_data/adapters/base.py`:
```python
"""The adapter seam: every data source returns raw bars + corporate actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import polars as pl

from alpha_core import CorporateAction


@dataclass(frozen=True)
class FetchResult:
    """Raw (unadjusted) bars plus the corporate actions for one symbol."""

    symbol: str
    bars: pl.DataFrame  # schema: ts, open, high, low, close, volume
    actions: list[CorporateAction]


class DataAdapter(Protocol):
    """A source of raw market data. `name`/`version` feed snapshot provenance."""

    name: str
    version: str

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult: ...
```

- [ ] **Step 3: Verify it imports + types**

Run: `uv run python -c "from alpha_data.adapters.base import FetchResult, DataAdapter; print('ok')"` then `uv run mypy packages apps tests`
Expected: prints `ok`; mypy clean.

- [ ] **Step 4: Commit**
```bash
git add packages/alpha-data/src/alpha_data/adapters/__init__.py packages/alpha-data/src/alpha_data/adapters/base.py
git commit -m "feat(data): DataAdapter protocol + FetchResult"
```

---

## Task 3: yfinance parser (offline, pure)

**Files:** Modify `packages/alpha-data/pyproject.toml`; Create `.../adapters/yfinance_adapter.py`, `tests/fixtures/yf_fixtures.py`, `tests/unit/test_yfinance_parser.py`.

- [ ] **Step 1: Add yfinance dependency**

In `packages/alpha-data/pyproject.toml`, change deps to:
```toml
dependencies = ["alpha-core", "polars>=1.0", "yfinance>=0.2.40"]
```
Then `uv sync`.

- [ ] **Step 2: Create the fixture builder**

Create `tests/fixtures/yf_fixtures.py`:
```python
"""Build a pandas DataFrame shaped like yfinance Ticker.history(auto_adjust=False)."""
from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd


def yf_history(rows: list[dict[str, float]], dates: list[datetime]) -> pd.DataFrame:
    """rows: dicts with Open/High/Low/Close/Volume/Dividends/Stock Splits."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates], name="Date")
    return pd.DataFrame(rows, index=idx)


def aapl_like() -> pd.DataFrame:
    """3 daily bars; a 4:1 split on day 3 and a 0.82 dividend on day 2. Raw (unadjusted) prices."""
    dates = [datetime(2020, 8, 28, tzinfo=UTC), datetime(2020, 8, 31, tzinfo=UTC),
             datetime(2020, 9, 1, tzinfo=UTC)]
    rows = [
        {"Open": 500.0, "High": 505.0, "Low": 498.0, "Close": 500.0, "Volume": 1e6,
         "Dividends": 0.0, "Stock Splits": 0.0},
        {"Open": 127.0, "High": 131.0, "Low": 126.0, "Close": 129.0, "Volume": 2e6,
         "Dividends": 0.82, "Stock Splits": 4.0},  # split ex-day: price already post-split
        {"Open": 132.0, "High": 134.0, "Low": 130.0, "Close": 133.0, "Volume": 1.5e6,
         "Dividends": 0.0, "Stock Splits": 0.0},
    ]
    return yf_history(rows, dates)
```

- [ ] **Step 3: Write failing parser tests**

Create `tests/unit/test_yfinance_parser.py`:
```python
from datetime import UTC, date, datetime

import pytest

from alpha_core import ActionType, DataError
from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from tests.fixtures.yf_fixtures import aapl_like, yf_history


def test_parse_extracts_raw_bars_and_actions() -> None:
    result = parse_yfinance_history(aapl_like(), "AAPL")
    assert result.symbol == "AAPL"
    # RAW prices preserved (the pre-split 500 is NOT adjusted down)
    assert result.bars["close"].to_list() == [500.0, 129.0, 133.0]
    assert result.bars["volume"].to_list() == [1e6, 2e6, 1.5e6]
    kinds = {(a.action_type, a.ex_date): a for a in result.actions}
    split = kinds[(ActionType.SPLIT, date(2020, 8, 31))]
    assert split.ratio == 4.0 and split.announce_date is None and split.knowledge_is_estimated
    div = kinds[(ActionType.DIVIDEND, date(2020, 8, 31))]  # fixture puts the 0.82 div on the 8/31 row
    assert div.amount == pytest.approx(0.82)


def test_parse_fails_loud_on_inconsistent_ohlc() -> None:
    bad = yf_history(
        [{"Open": 10.0, "High": 5.0, "Low": 9.0, "Close": 8.0, "Volume": 1.0,
          "Dividends": 0.0, "Stock Splits": 0.0}],
        [datetime(2024, 1, 2, tzinfo=UTC)],
    )
    with pytest.raises(DataError):
        parse_yfinance_history(bad, "X")  # high < open → invalid Bar
```

- [ ] **Step 4: Run, verify fail**

Run: `uv run pytest tests/unit/test_yfinance_parser.py -q`
Expected: FAIL — `ModuleNotFoundError: alpha_data.adapters.yfinance_adapter`.

- [ ] **Step 5: Implement the parser + adapter**

Create `packages/alpha-data/src/alpha_data/adapters/yfinance_adapter.py`:
```python
"""yfinance adapter: raw OHLCV + splits/dividends. Parse is pure/offline; fetch is live."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
import polars as pl

from alpha_core import ActionType, Bar, CorporateAction, DataError
from alpha_data.adapters.base import FetchResult

_VERSION = "1"
_OHLCV = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}


def _to_utc(ts: pd.Timestamp) -> datetime:
    py = ts.to_pydatetime()
    return py.replace(tzinfo=UTC) if py.tzinfo is None else py.astimezone(UTC)


def parse_yfinance_history(df: pd.DataFrame, symbol: str) -> FetchResult:
    """Convert a yfinance history frame (auto_adjust=False, actions=True) to a FetchResult.

    Validates each row by constructing a Bar (1a invariants) — fails loud on bad vendor data.
    """
    missing = [c for c in (*_OHLCV, "Dividends", "Stock Splits") if c not in df.columns]
    if missing:
        raise DataError(f"yfinance frame for {symbol} missing columns: {missing}")

    bars_rows: list[dict[str, object]] = []
    actions: list[CorporateAction] = []
    for idx, row in df.iterrows():
        ts = _to_utc(pd.Timestamp(idx))  # type: ignore[arg-type]
        # fail-loud validation via the canonical Bar invariants
        Bar(symbol=symbol, ts=ts, open=float(row["Open"]), high=float(row["High"]),
            low=float(row["Low"]), close=float(row["Close"]), volume=float(row["Volume"]))
        bars_rows.append({"ts": ts, "open": float(row["Open"]), "high": float(row["High"]),
                          "low": float(row["Low"]), "close": float(row["Close"]),
                          "volume": float(row["Volume"])})
        ex: date = ts.date()
        if float(row["Stock Splits"]) != 0.0:
            actions.append(CorporateAction(symbol=symbol, action_type=ActionType.SPLIT,
                                           ex_date=ex, ratio=float(row["Stock Splits"])))
        if float(row["Dividends"]) != 0.0:
            actions.append(CorporateAction(symbol=symbol, action_type=ActionType.DIVIDEND,
                                           ex_date=ex, amount=float(row["Dividends"])))
    bars = pl.DataFrame(bars_rows, schema={"ts": pl.Datetime(time_zone="UTC"), "open": pl.Float64,
                                           "high": pl.Float64, "low": pl.Float64,
                                           "close": pl.Float64, "volume": pl.Float64})
    return FetchResult(symbol=symbol, bars=bars, actions=actions)


class YFinanceAdapter:
    """Live yfinance adapter. Network call isolated to `fetch`; logic lives in the parser."""

    name = "yfinance"
    version = _VERSION

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        import yfinance as yf

        df = yf.Ticker(symbol).history(start=start.isoformat(), end=end.isoformat(),
                                       auto_adjust=False, actions=True)
        if df.empty:
            raise DataError(f"yfinance returned no data for {symbol} {start}..{end}")
        return parse_yfinance_history(df, symbol)
```

- [ ] **Step 6: Run, verify pass**

Run: `uv run pytest tests/unit/test_yfinance_parser.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**
```bash
git add packages/alpha-data/pyproject.toml packages/alpha-data/src/alpha_data/adapters/yfinance_adapter.py tests/fixtures/yf_fixtures.py tests/unit/test_yfinance_parser.py
git commit -m "feat(data): yfinance adapter — pure parser (raw bars + splits/dividends) + live fetch"
```

---

## Task 4: Ingest pipeline (validate + store)

**Files:** Create `packages/alpha-data/src/alpha_data/ingest.py`, `tests/unit/test_ingest.py`.

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_ingest.py`:
```python
from datetime import date
from pathlib import Path

from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from alpha_data.ingest import store_fetch_result
from alpha_data.store import ParquetStore
from tests.fixtures.yf_fixtures import aapl_like


def test_store_fetch_result_writes_bars_and_actions(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    result = parse_yfinance_history(aapl_like(), "AAPL")
    store_fetch_result(store, result)
    assert store.read_bars("AAPL")["close"].to_list() == [500.0, 129.0, 133.0]
    assert len(store.read_actions("AAPL")) == 2  # one split + one dividend
```

- [ ] **Step 2: Run, verify fail** — `uv run pytest tests/unit/test_ingest.py -q` → `ModuleNotFoundError: alpha_data.ingest`.

- [ ] **Step 3: Implement**

Create `packages/alpha-data/src/alpha_data/ingest.py`:
```python
"""Persist a FetchResult to the store (bars + actions)."""
from __future__ import annotations

from alpha_data.adapters.base import FetchResult
from alpha_data.store import ParquetStore


def store_fetch_result(store: ParquetStore, result: FetchResult) -> None:
    store.write_bars(result.symbol, result.bars)
    store.write_actions(result.symbol, result.actions)
```

- [ ] **Step 4: Run, verify pass** — `uv run pytest tests/unit/test_ingest.py -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add packages/alpha-data/src/alpha_data/ingest.py tests/unit/test_ingest.py
git commit -m "feat(data): ingest pipeline (store bars + actions from a FetchResult)"
```

---

## Task 5: Snapshots + manifest + verify

**Files:** Create `packages/alpha-data/src/alpha_data/snapshot.py`, `tests/unit/test_snapshot.py`.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_snapshot.py`:
```python
from datetime import UTC, date, datetime
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
    return store


def test_snapshot_writes_manifest_with_provenance(tmp_path: Path) -> None:
    store = _store(tmp_path)
    manifest = create_snapshot(store, tmp_path / "snaps", "snap1", ["AAPL"],
                               source="yfinance", adapter_version="1", parser_version="1",
                               created_at=WHEN)
    assert manifest["source"] == "yfinance"
    assert manifest["adapter_version"] == "1"
    assert manifest["symbols"]["AAPL"]["bars_sha256"]
    assert (tmp_path / "snaps" / "snap1" / "manifest.json").exists()


def test_verify_passes_for_intact_snapshot(tmp_path: Path) -> None:
    store = _store(tmp_path)
    create_snapshot(store, tmp_path / "snaps", "snap1", ["AAPL"], source="yfinance",
                    adapter_version="1", parser_version="1", created_at=WHEN)
    verify_snapshot(tmp_path / "snaps" / "snap1")  # no raise


def test_verify_detects_tampering(tmp_path: Path) -> None:
    store = _store(tmp_path)
    create_snapshot(store, tmp_path / "snaps", "snap1", ["AAPL"], source="yfinance",
                    adapter_version="1", parser_version="1", created_at=WHEN)
    bars_file = next((tmp_path / "snaps" / "snap1").glob("bars/*.parquet"))
    bars_file.write_bytes(bars_file.read_bytes() + b"corruption")
    with pytest.raises(DataError):
        verify_snapshot(tmp_path / "snaps" / "snap1")
```

- [ ] **Step 2: Run, verify fail** — `uv run pytest tests/unit/test_snapshot.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `packages/alpha-data/src/alpha_data/snapshot.py`:
```python
"""Immutable, content-hashed data snapshots with a provenance manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from alpha_core import DataError
from alpha_data.store import ParquetStore


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_snapshot(store: ParquetStore, snaps_root: Path, snapshot_id: str, symbols: list[str],
                    *, source: str, adapter_version: str, parser_version: str,
                    created_at: datetime) -> dict[str, Any]:
    """Freeze bars + actions for `symbols` into snaps_root/snapshot_id/ with a manifest."""
    dest = snaps_root / snapshot_id
    if dest.exists():
        raise DataError(f"snapshot {snapshot_id!r} already exists at {dest}")
    (dest / "bars").mkdir(parents=True)
    (dest / "actions").mkdir(parents=True)

    sym_manifest: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        bars_src = store._bars_path(sym)  # noqa: SLF001 — snapshot is a peer of the store
        if not bars_src.exists():
            raise DataError(f"cannot snapshot {sym!r}: no bars in store")
        bars_dst = dest / "bars" / bars_src.name
        bars_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bars_src, bars_dst)
        entry: dict[str, Any] = {"bars_sha256": _sha256(bars_dst), "bars_file": f"bars/{bars_src.name}"}
        actions_src = store._actions_path(sym)  # noqa: SLF001
        if actions_src.exists():
            actions_dst = dest / "actions" / actions_src.name
            actions_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actions_src, actions_dst)
            entry["actions_sha256"] = _sha256(actions_dst)
            entry["actions_file"] = f"actions/{actions_src.name}"
        sym_manifest[sym] = entry

    manifest: dict[str, Any] = {
        "snapshot_id": snapshot_id, "created_at": created_at.isoformat(), "source": source,
        "adapter_version": adapter_version, "parser_version": parser_version,
        "symbols": sym_manifest,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def verify_snapshot(snapshot_dir: Path) -> None:
    """Re-hash every file and compare to the manifest. Raises DataError on any mismatch."""
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        raise DataError(f"no manifest in {snapshot_dir}")
    manifest = json.loads(manifest_path.read_text())
    for sym, entry in manifest["symbols"].items():
        bars_file = snapshot_dir / entry["bars_file"]
        if not bars_file.exists() or _sha256(bars_file) != entry["bars_sha256"]:
            raise DataError(f"snapshot integrity failure for {sym} bars ({bars_file})")
        if "actions_sha256" in entry:
            af = snapshot_dir / entry["actions_file"]
            if not af.exists() or _sha256(af) != entry["actions_sha256"]:
                raise DataError(f"snapshot integrity failure for {sym} actions ({af})")
```

- [ ] **Step 4: Run, verify pass** — `uv run pytest tests/unit/test_snapshot.py -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add packages/alpha-data/src/alpha_data/snapshot.py tests/unit/test_snapshot.py
git commit -m "feat(data): immutable content-hashed snapshots with provenance manifest + verify"
```

---

## Task 6: `alpha data` CLI + network marker

**Files:** Modify `pyproject.toml` (marker), `apps/alpha-cli/src/alpha_cli/main.py`; Create `apps/alpha-cli/src/alpha_cli/data_cmds.py`, `tests/integration/test_data_cli.py`, `tests/integration/test_yfinance_live.py`.

- [ ] **Step 1: Register the `network` marker**

In `pyproject.toml` `[tool.pytest.ini_options] markers`, add a second entry:
```toml
    "network: tests that hit the live network (skipped in CI / offline runs)",
```

- [ ] **Step 2: Write failing CLI test (offline, via a fake adapter)**

Create `tests/integration/test_data_cli.py`:
```python
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.adapters.base import FetchResult
from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from tests.fixtures.yf_fixtures import aapl_like

runner = CliRunner()


class _FakeAdapter:
    name = "fake"
    version = "1"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        return parse_yfinance_history(aapl_like(), symbol)


def test_pull_then_snapshot_then_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    # inject the fake adapter so the CLI does no network
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"fake": _FakeAdapter})
    r1 = runner.invoke(app, ["data", "pull", "AAPL", "--source", "fake",
                             "--start", "2020-08-28", "--end", "2020-09-02"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["data", "snapshot", "snap1", "AAPL", "--source", "fake"])
    assert r2.exit_code == 0, r2.output
    r3 = runner.invoke(app, ["data", "verify", "snap1"])
    assert r3.exit_code == 0, r3.output
    assert "ok" in r3.output.lower()
```

- [ ] **Step 3: Run, verify fail** — `uv run pytest tests/integration/test_data_cli.py -q` → fails (no `data` command).

- [ ] **Step 4: Implement the data commands**

Create `apps/alpha-cli/src/alpha_cli/data_cmds.py`:
```python
"""`alpha data` subcommands: pull, snapshot, verify."""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import typer

from alpha_core import AlphaSettings
from alpha_data.adapters.yfinance_adapter import YFinanceAdapter
from alpha_data.ingest import store_fetch_result
from alpha_data.snapshot import create_snapshot, verify_snapshot
from alpha_data.store import ParquetStore

data_app = typer.Typer(help="Data ingestion, snapshots, and integrity.")

# adapter registry — tests monkeypatch this to inject offline fakes
_ADAPTERS: dict[str, type] = {"yfinance": YFinanceAdapter}


def _store() -> ParquetStore:
    return ParquetStore(AlphaSettings().data_dir / "store")


def _snaps_root() -> Path:
    return AlphaSettings().data_dir / "snapshots"


@data_app.command()
def pull(symbol: str, source: str = "yfinance",
         start: str = typer.Option(...), end: str = typer.Option(...)) -> None:
    """Pull raw bars + corporate actions for SYMBOL and store them."""
    adapter_cls = _ADAPTERS.get(source)
    if adapter_cls is None:
        raise typer.BadParameter(f"unknown source {source!r}; known: {sorted(_ADAPTERS)}")
    result = adapter_cls().fetch(symbol, date.fromisoformat(start), date.fromisoformat(end))
    store_fetch_result(_store(), result)
    typer.echo(f"pulled {symbol} from {source}: {result.bars.height} bars, {len(result.actions)} actions")


@data_app.command()
def snapshot(snapshot_id: str, symbols: list[str], source: str = "yfinance") -> None:
    """Freeze the current store for SYMBOLS into an immutable, hashed snapshot."""
    adapter_cls = _ADAPTERS.get(source)
    if adapter_cls is None:
        raise typer.BadParameter(f"unknown source {source!r}; known: {sorted(_ADAPTERS)}")
    adapter = adapter_cls()
    create_snapshot(_store(), _snaps_root(), snapshot_id, symbols, source=adapter.name,
                    adapter_version=adapter.version, parser_version=adapter.version,
                    created_at=datetime.now(UTC))
    typer.echo(f"snapshot {snapshot_id} created for {symbols}")


@data_app.command()
def verify(snapshot_id: str) -> None:
    """Re-hash a snapshot and confirm it matches its manifest."""
    verify_snapshot(_snaps_root() / snapshot_id)
    typer.echo(f"snapshot {snapshot_id}: integrity OK")
```

In `apps/alpha-cli/src/alpha_cli/main.py`, register the sub-app — add the import and `app.add_typer`:
```python
from alpha_cli.data_cmds import data_app

app.add_typer(data_app, name="data")
```
(Place the `add_typer` call right after `app = typer.Typer(...)`.)

- [ ] **Step 5: Run, verify pass** — `uv run pytest tests/integration/test_data_cli.py -q` → PASS. Also `uv run alpha data --help` lists pull/snapshot/verify.

- [ ] **Step 6: Add the network-gated live smoke test**

Create `tests/integration/test_yfinance_live.py`:
```python
"""Live yfinance smoke test — skipped in CI/offline (run locally with -m network)."""
from __future__ import annotations

from datetime import date

import pytest

from alpha_data.adapters.yfinance_adapter import YFinanceAdapter

pytestmark = pytest.mark.network


def test_yfinance_live_pull_aapl() -> None:
    result = YFinanceAdapter().fetch("AAPL", date(2020, 8, 1), date(2020, 9, 30))
    assert result.bars.height > 10
    # the Aug-2020 4:1 split must be present as a raw action
    assert any(a.action_type.value == "split" and a.ratio == 4.0 for a in result.actions)
```

- [ ] **Step 7: Confirm CI excludes network tests**

The CI step is `uv run pytest -q`, which RUNS all tests including `network`. Change the CI test step and the default so network tests are deselected unless explicitly requested. In `.github/workflows/ci.yml`, change the test step to:
```yaml
      - name: Tests (incl. bias guards)
        run: uv run pytest -q -m "not network"
```
Run locally: `uv run pytest -q -m "not network"` (should pass, skipping the live test) and `uv run pytest -q -m network` (hits the network — may be skipped if offline; that's fine).

- [ ] **Step 8: Commit**
```bash
git add pyproject.toml .github/workflows/ci.yml apps/alpha-cli/src/alpha_cli/main.py apps/alpha-cli/src/alpha_cli/data_cmds.py tests/integration/test_data_cli.py tests/integration/test_yfinance_live.py
git commit -m "feat(cli): alpha data pull/snapshot/verify; network-gated live smoke test"
```

---

## Task 7: Final gate

- [ ] **Step 1: Run the full gate (mirrors CI)**

Run:
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy packages apps tests && uv run lint-imports && uv run pytest -q -m "not network"
```
Expected: all green; `lint-imports` still 5 kept / 0 broken (adapters/ingest/snapshot stay within `alpha_data`→`alpha_core`; CLI may import `alpha_data`).

- [ ] **Step 2: Fix anything red, re-run until green.** Common: ruff format on new files; mypy may want a type on the `monkeypatch` fixture param (annotate `monkeypatch: pytest.MonkeyPatch`); pandas has no stubs so `import pandas as pd` may need `# type: ignore[import-untyped]` (acceptable, with the reason) or add `pandas-stubs` to the dev group (preferred — do that instead of an ignore).

- [ ] **Step 3: Final commit (if fixes were made)**
```bash
git add -A && git commit -m "chore(data): phase-1b-i gate green"
```

---

## Done = Phase 1b-i complete

- `ParquetStore` stores + reads corporate actions (exact pydantic round-trip).
- `DataAdapter`/`FetchResult` seam defined; `YFinanceAdapter` pulls RAW OHLCV + splits/dividends.
- Parser is offline-tested incl. a real split+dividend → raw bars + actions, and fails loud on inconsistent OHLC.
- `create_snapshot` freezes data with a provenance manifest (source, adapter/parser version) + per-file sha256; `verify_snapshot` detects tampering.
- `alpha data pull|snapshot|verify` works (offline-tested via a fake adapter); a `network`-marked live smoke test exists and is excluded from CI.
- Full gate green; CI runs `-m "not network"`.

**Next:** Phase 1b-ii — more adapters (crypto via ccxt, FX via Dukascopy, FRED macro) on the same `DataAdapter` seam; then 1b-iii (dividend total-return adjustment + DuckDB ASOF).

## Notes / risks
- **pandas at the edge only.** It enters via yfinance in the adapter; everything downstream is Polars. Add `pandas-stubs` to the dev group rather than `# type: ignore` the import.
- **`store._bars_path`/`_actions_path` are accessed from `snapshot.py`** (a peer module) via name-mangled-free private methods — acceptable within the same package; if it grates, promote them to public `bars_path`/`actions_path`. Keep `# noqa: SLF001` with the reason.
- **yfinance reliability:** the live test is `network`-gated and may flake/rate-limit; never gate CI on it. Stored snapshots are frozen + hash-verified, so once pulled the data is reproducible regardless of upstream.
- **Announce dates absent** from yfinance → conservative `knowledge_time = ex_date`. When a source with announce dates lands (1b-ii) the firewall already honors it.
