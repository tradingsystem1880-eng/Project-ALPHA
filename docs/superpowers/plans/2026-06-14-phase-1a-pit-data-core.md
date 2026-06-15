# Phase 1a — Point-in-Time Data Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a correct, look-ahead-safe Point-in-Time data core — `Bar` with enforced invariants, a Parquet store, the two-clock (knowledge-time vs ex-date) **split** adjustment, and the `as_of(when)` firewall — proven entirely with deterministic fixtures, including the data bias-guards.

**Architecture:** All offline/fixture-driven; no network. Parquet is the source of truth (Polars I/O). The PIT reader scans Parquet, filters to `ts <= when` (the firewall — future bars physically excluded), and applies split factors gated by knowledge-time. Correctness is pinned by unit tests with exact expected values and by bias-guards (future-poison, point-in-time corporate-action, survivorship).

**Tech Stack:** Python 3.12 · Polars · pydantic v2 · pytest + Hypothesis. (DuckDB enters in Phase 1b as the scan/ASOF optimization; not required here.)

**Scope decisions (explicit):**
- **Splits only** in 1a (correctness-critical for momentum). Dividend *total-return* adjustment → Phase 1b (needs prior-close lookup; minimal effect on momentum direction).
- **Accessor in Polars over Parquet** for legible, fixture-pinned correctness. DuckDB ASOF join is the documented optimization for when scans get large (Phase 1b+).
- Folds in the Phase-0 review **carry-overs**: `Bar` OHLC/NaN invariants (+ Hypothesis), `as_of` takes `AwareDatetime`, `--import-mode=importlib`.

**Branch:** all work on `phase-1a-pit-data-core` (off `main`). Do not push.

---

## File Map

```
packages/alpha-core/src/alpha_core/
├── types.py          # MODIFY: add Bar invariant validator
├── corporate.py      # CREATE: ActionType enum + CorporateAction type
├── protocols.py      # MODIFY: DataSource.as_of(when: AwareDatetime)
└── __init__.py       # MODIFY: export CorporateAction, ActionType
packages/alpha-data/src/alpha_data/
├── store.py          # CREATE: ParquetStore (bars + corporate actions I/O)
├── corporate.py      # CREATE: knowledge-time gating + split factor math
├── pit.py            # CREATE: PointInTimeReader.as_of(symbol, when) → adjusted bars
└── placeholder.py    # DELETE (replaced by store/pit; alpha_backtest placeholder also deleted — it imported this)
tests/
├── unit/
│   ├── test_bar_invariants.py        # CREATE (+ Hypothesis property tests)
│   ├── test_corporate_actions.py     # CREATE (split factor math, two-clock)
│   └── test_parquet_store.py         # CREATE (round-trip)
├── bias_guards/
│   ├── test_pit_future_poison.py     # CREATE: poison future bars → past unchanged
│   ├── test_pit_corporate_action.py  # CREATE: AAPL split, knowledge-gated
│   └── test_survivorship.py          # CREATE: delisted names stay in as-of universe
└── fixtures/
    └── pit_fixtures.py               # CREATE: deterministic Bar/CorporateAction builders
pyproject.toml                        # MODIFY: pytest --import-mode=importlib
```

---

## Task 0: Branch

- [ ] **Step 1: Create the working branch**

Run:
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA
git checkout main && git checkout -b phase-1a-pit-data-core
```
Expected: `Switched to a new branch 'phase-1a-pit-data-core'`.

---

## Task 1: `Bar` invariants + Hypothesis + importlib mode

**Files:**
- Modify: `packages/alpha-core/src/alpha_core/types.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/test_bar_invariants.py`

- [ ] **Step 1: Add `--import-mode=importlib` to pytest config**

In `pyproject.toml`, change the `[tool.pytest.ini_options]` `addopts` line from:
```toml
addopts = "--strict-markers"
```
to:
```toml
addopts = "--strict-markers --import-mode=importlib"
pythonpath = ["."]
```
(`pythonpath = ["."]` puts the repo root on `sys.path` so `from tests.fixtures.pit_fixtures import ...` resolves as a namespace package.)

- [ ] **Step 2: Write failing invariant tests**

Create `tests/unit/test_bar_invariants.py`:
```python
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from alpha_core import Bar

TS = datetime(2024, 1, 2, tzinfo=UTC)


def _bar(**kw: float) -> Bar:
    base = dict(symbol="X", ts=TS, open=10.0, high=11.0, low=9.0, close=10.5, volume=100.0)
    base.update(kw)
    return Bar(**base)  # type: ignore[arg-type]


def test_valid_bar_constructs() -> None:
    assert _bar().high == 11.0


@pytest.mark.parametrize("kw", [
    {"high": 8.0},          # high < low
    {"low": 12.0},          # low > open/close/high
    {"close": 99.0},        # close > high
    {"open": 0.0},          # non-positive price
    {"volume": -1.0},       # negative volume
    {"high": float("nan")}, # NaN
    {"low": float("inf")},  # inf
])
def test_invalid_bar_rejected(kw: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        _bar(**kw)


# Property: any OHLC with low <= {open,close} <= high, all positive & finite, volume >= 0 constructs.
@given(
    low=st.floats(min_value=1.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    spread=st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    o_frac=st.floats(min_value=0.0, max_value=1.0),
    c_frac=st.floats(min_value=0.0, max_value=1.0),
    volume=st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_consistent_ohlc_always_constructs(
    low: float, spread: float, o_frac: float, c_frac: float, volume: float
) -> None:
    high = low + spread
    bar = Bar(symbol="X", ts=TS, open=low + o_frac * spread, high=high,
              low=low, close=low + c_frac * spread, volume=volume)
    assert bar.low <= bar.open <= bar.high
    assert bar.low <= bar.close <= bar.high
```

- [ ] **Step 3: Run, verify it fails**

Run: `cd /Users/hunternovotny/Desktop/Project-ALPHA && uv run pytest tests/unit/test_bar_invariants.py -q`
Expected: FAIL — `test_invalid_bar_rejected` cases pass through (no validator yet).

- [ ] **Step 4: Add the invariant validator to `Bar`**

In `packages/alpha-core/src/alpha_core/types.py`, add `import math` at top, add `model_validator` to the pydantic import, and add this method inside `Bar` (after the fields):
```python
    @model_validator(mode="after")
    def _check_invariants(self) -> "Bar":
        prices = {"open": self.open, "high": self.high, "low": self.low, "close": self.close}
        for name, v in {**prices, "volume": self.volume}.items():
            if math.isnan(v) or math.isinf(v):
                raise ValueError(f"Bar.{name} must be finite, got {v!r}")
        if self.volume < 0:
            raise ValueError(f"Bar.volume must be >= 0, got {self.volume}")
        for name, v in prices.items():
            if v <= 0:
                raise ValueError(f"Bar.{name} must be > 0, got {v}")
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError(
                f"OHLC inconsistent: low={self.low} open={self.open} high={self.high} close={self.close}"
            )
        return self
```
Update the import line to: `from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator`.

- [ ] **Step 5: Run, verify pass**

Run: `uv run pytest tests/unit/test_bar_invariants.py -q`
Expected: PASS (all parametrized cases + the property test).

- [ ] **Step 6: Commit**
```bash
git add packages/alpha-core/src/alpha_core/types.py pyproject.toml tests/unit/test_bar_invariants.py
git commit -m "feat(core): enforce Bar OHLC/positivity/finite invariants; importlib test mode"
```

---

## Task 2: `CorporateAction` type + `ActionType`

**Files:**
- Create: `packages/alpha-core/src/alpha_core/corporate.py`
- Modify: `packages/alpha-core/src/alpha_core/__init__.py`
- Test: `tests/unit/test_corporate_actions.py` (type-validation portion)

- [ ] **Step 1: Write failing type tests**

Create `tests/unit/test_corporate_actions.py`:
```python
from datetime import date

import pytest
from pydantic import ValidationError

from alpha_core import ActionType, CorporateAction


def test_split_requires_positive_ratio() -> None:
    a = CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT,
                        ex_date=date(2020, 8, 31), announce_date=date(2020, 7, 30), ratio=4.0)
    assert a.ratio == 4.0
    with pytest.raises(ValidationError):
        CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT, ex_date=date(2020, 8, 31))


def test_knowledge_time_falls_back_to_ex_date_when_announce_missing() -> None:
    a = CorporateAction(symbol="X", action_type=ActionType.SPLIT, ex_date=date(2021, 1, 5), ratio=2.0)
    assert a.knowledge_time == date(2021, 1, 5)
    assert a.knowledge_is_estimated is True
    b = CorporateAction(symbol="X", action_type=ActionType.SPLIT, ex_date=date(2021, 1, 5),
                        announce_date=date(2020, 12, 20), ratio=2.0)
    assert b.knowledge_time == date(2020, 12, 20)
    assert b.knowledge_is_estimated is False
```

- [ ] **Step 2: Run, verify it fails**

Run: `uv run pytest tests/unit/test_corporate_actions.py -q`
Expected: FAIL — `ImportError` (`ActionType`/`CorporateAction` not defined).

- [ ] **Step 3: Create the corporate-action types**

Create `packages/alpha-core/src/alpha_core/corporate.py`:
```python
"""Corporate-action / instrument-lifecycle types. See spec §6.1 (two-clock model)."""
from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class ActionType(StrEnum):
    SPLIT = "split"
    DIVIDEND = "dividend"
    REDENOMINATION = "redenomination"
    SYMBOL_MIGRATION = "symbol_migration"


class CorporateAction(BaseModel):
    """A point-in-time instrument-lifecycle event.

    Two clocks: ``ex_date`` (valid time — when the price mechanically adjusts) and
    knowledge time (``announce_date`` if present, else a conservative ``ex_date`` fallback).
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    action_type: ActionType
    ex_date: date
    announce_date: date | None = None
    record_date: date | None = None
    pay_date: date | None = None
    ratio: float | None = None   # SPLIT: new/old shares (a 4-for-1 split → 4.0)
    amount: float | None = None  # DIVIDEND: cash per share

    @property
    def knowledge_time(self) -> date:
        return self.announce_date if self.announce_date is not None else self.ex_date

    @property
    def knowledge_is_estimated(self) -> bool:
        return self.announce_date is None

    @model_validator(mode="after")
    def _check_payload(self) -> "CorporateAction":
        if self.action_type is ActionType.SPLIT and (self.ratio is None or self.ratio <= 0):
            raise ValueError("SPLIT requires ratio > 0")
        if self.action_type is ActionType.DIVIDEND and (self.amount is None or self.amount <= 0):
            raise ValueError("DIVIDEND requires amount > 0")
        if self.announce_date is not None and self.announce_date > self.ex_date:
            raise ValueError("announce_date cannot be after ex_date")
        return self
```

- [ ] **Step 4: Export from the package**

In `packages/alpha-core/src/alpha_core/__init__.py`, add imports and extend `__all__`:
```python
from alpha_core.corporate import ActionType, CorporateAction
```
Add `"ActionType"` and `"CorporateAction"` to `__all__`.

- [ ] **Step 5: Run, verify pass**

Run: `uv run pytest tests/unit/test_corporate_actions.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add packages/alpha-core/src/alpha_core/corporate.py packages/alpha-core/src/alpha_core/__init__.py tests/unit/test_corporate_actions.py
git commit -m "feat(core): add CorporateAction + ActionType (two-clock lifecycle events)"
```

---

## Task 3: `ParquetStore`

**Files:**
- Create: `packages/alpha-data/src/alpha_data/store.py`
- Modify: `packages/alpha-data/pyproject.toml` (add `polars`)
- Delete: `packages/alpha-data/src/alpha_data/placeholder.py`
- Test: `tests/unit/test_parquet_store.py`

- [ ] **Step 1: Add the polars dependency**

In `packages/alpha-data/pyproject.toml`, change `dependencies = ["alpha-core"]` to:
```toml
dependencies = ["alpha-core", "polars>=1.0"]
```

- [ ] **Step 2: Write failing round-trip test**

Create `tests/unit/test_parquet_store.py`:
```python
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from alpha_data.store import ParquetStore

SCHEMA = ["ts", "open", "high", "low", "close", "volume"]


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": [datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 3, tzinfo=UTC)],
            "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.5, 10.0],
            "close": [10.5, 11.0], "volume": [100.0, 120.0],
        }
    )


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("BTCUSD", _frame())
    out = store.read_bars("BTCUSD")
    assert out.columns == SCHEMA
    assert out.height == 2
    assert out["close"].to_list() == [10.5, 11.0]


def test_read_missing_symbol_raises(tmp_path: Path) -> None:
    import pytest

    from alpha_core import DataError

    with pytest.raises(DataError):
        ParquetStore(tmp_path).read_bars("NOPE")
```

- [ ] **Step 3: Run, verify it fails**

Run: `uv run pytest tests/unit/test_parquet_store.py -q`
Expected: FAIL — `ModuleNotFoundError: alpha_data.store`.

- [ ] **Step 4: Implement `ParquetStore`**

Create `packages/alpha-data/src/alpha_data/store.py`:
```python
"""Parquet source-of-truth store for raw (unadjusted) bars and corporate actions."""
from __future__ import annotations

from pathlib import Path

import polars as pl

from alpha_core import DataError

_BAR_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


class ParquetStore:
    """Stores raw bars as one Parquet file per symbol under ``<root>/bars/``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _bars_path(self, symbol: str) -> Path:
        return self.root / "bars" / f"{symbol}.parquet"

    def write_bars(self, symbol: str, df: pl.DataFrame) -> Path:
        missing = [c for c in _BAR_COLUMNS if c not in df.columns]
        if missing:
            raise DataError(f"bars for {symbol} missing columns: {missing}")
        path = self._bars_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.select(_BAR_COLUMNS).sort("ts").write_parquet(path)
        return path

    def read_bars(self, symbol: str) -> pl.DataFrame:
        path = self._bars_path(symbol)
        if not path.exists():
            raise DataError(f"no bars stored for symbol {symbol!r} at {path}")
        return pl.read_parquet(path)
```

- [ ] **Step 5: Delete the obsolete placeholders (both, together)**

`alpha_data.placeholder` is replaced by `store`/`pit`; `alpha_backtest.placeholder` exists only to import it — so remove both in this commit to keep every committed state consistent (`alpha_backtest` gets real content in Phase 2):
```bash
git rm packages/alpha-data/src/alpha_data/placeholder.py packages/alpha-backtest/src/alpha_backtest/placeholder.py
```
The import-linter contracts stay satisfied — the `alpha_backtest → core+data` contract is a *permission*, not a requirement.

- [ ] **Step 6: Run the gate (confirms the deletions left nothing dangling)**

Run:
```bash
uv run pytest tests/unit/test_parquet_store.py -q
uv run mypy packages apps tests
uv run lint-imports
```
Expected: pytest PASS; mypy clean (nothing imports the deleted modules); lint-imports 5 kept / 0 broken.

- [ ] **Step 7: Commit**
```bash
git add packages/alpha-data/pyproject.toml packages/alpha-data/src/alpha_data/store.py tests/unit/test_parquet_store.py
git add -u packages/alpha-data/src/alpha_data/placeholder.py packages/alpha-backtest/src/alpha_backtest/placeholder.py
git commit -m "feat(data): Parquet bar store; remove obsolete data/backtest placeholders"
```

---

## Task 4: Split-factor math (two-clock)

**Files:**
- Create: `packages/alpha-data/src/alpha_data/corporate.py`
- Test: extend `tests/unit/test_corporate_actions.py`

- [ ] **Step 1: Write failing math tests**

Append to `tests/unit/test_corporate_actions.py`:
```python
from datetime import date as _date

from alpha_data.corporate import known_actions, split_factor


def _aapl_split() -> CorporateAction:
    return CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT,
                           ex_date=_date(2020, 8, 31), announce_date=_date(2020, 7, 30), ratio=4.0)


def test_known_actions_gates_by_knowledge_time() -> None:
    a = _aapl_split()
    assert known_actions([a], _date(2020, 7, 29)) == []          # before announce → unknown
    assert known_actions([a], _date(2020, 7, 30)) == [a]         # on announce → known
    assert known_actions([a], _date(2020, 9, 1)) == [a]


def test_split_factor_applies_only_before_ex_date() -> None:
    splits = [_aapl_split()]
    assert split_factor(_date(2020, 8, 28), splits) == 0.25      # pre-ex → 1/4
    assert split_factor(_date(2020, 8, 31), splits) == 1.0       # ex day → unadjusted
    assert split_factor(_date(2020, 9, 1), splits) == 1.0


def test_multiple_splits_compound() -> None:
    s1 = CorporateAction(symbol="X", action_type=ActionType.SPLIT, ex_date=_date(2021, 1, 1), ratio=2.0)
    s2 = CorporateAction(symbol="X", action_type=ActionType.SPLIT, ex_date=_date(2022, 1, 1), ratio=3.0)
    # a bar before both is divided by 2*3 = 6
    assert split_factor(_date(2020, 6, 1), [s1, s2]) == pytest.approx(1 / 6)
    # a bar between them is divided by 3 only
    assert split_factor(_date(2021, 6, 1), [s1, s2]) == pytest.approx(1 / 3)
```
(Add `import pytest` at the top of the file if not already present.)

- [ ] **Step 2: Run, verify it fails**

Run: `uv run pytest tests/unit/test_corporate_actions.py -q`
Expected: FAIL — `ModuleNotFoundError: alpha_data.corporate`.

- [ ] **Step 3: Implement the math**

Create `packages/alpha-data/src/alpha_data/corporate.py`:
```python
"""Two-clock corporate-action math (splits). See spec §6.1."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from alpha_core import ActionType, CorporateAction


def known_actions(actions: Sequence[CorporateAction], as_of: date) -> list[CorporateAction]:
    """Actions whose knowledge_time <= as_of (availability gate)."""
    return [a for a in actions if a.knowledge_time <= as_of]


def split_factor(bar_date: date, splits: Sequence[CorporateAction]) -> float:
    """Back-adjustment multiplier for prices on ``bar_date``.

    Product of 1/ratio over every SPLIT with ex_date strictly after bar_date
    (application gate = ex_date). Pass only knowledge-gated actions in.
    """
    factor = 1.0
    for a in splits:
        if a.action_type is ActionType.SPLIT and a.ex_date > bar_date:
            assert a.ratio is not None  # guaranteed by CorporateAction validator
            factor /= a.ratio
    return factor
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest tests/unit/test_corporate_actions.py -q`
Expected: PASS (all type + math tests).

- [ ] **Step 5: Commit**
```bash
git add packages/alpha-data/src/alpha_data/corporate.py tests/unit/test_corporate_actions.py
git commit -m "feat(data): two-clock split-adjustment math (knowledge gate + ex-date application)"
```

---

## Task 5: `PointInTimeReader.as_of` (the firewall)

**Files:**
- Create: `packages/alpha-data/src/alpha_data/pit.py`
- Modify: `packages/alpha-core/src/alpha_core/protocols.py` (`as_of(when: AwareDatetime)`)
- Create: `tests/fixtures/pit_fixtures.py`
- Test: `tests/unit/test_pit_reader.py`

- [ ] **Step 1: Tighten the protocol to AwareDatetime**

In `packages/alpha-core/src/alpha_core/protocols.py`, change `DataSource.as_of` signature from `def as_of(self, symbol: str, when: datetime) -> list[Bar]:` to use `AwareDatetime`, and update imports: replace `from datetime import datetime` with `from pydantic import AwareDatetime`, and change the annotation to `when: AwareDatetime`.

- [ ] **Step 2: Create deterministic fixtures**

Create `tests/fixtures/pit_fixtures.py`:
```python
"""Deterministic builders for PIT tests — no network, no randomness."""
from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl

from alpha_core import ActionType, CorporateAction


def linear_bars(symbol: str, start: date, n: int, first_close: float = 100.0) -> pl.DataFrame:
    """n daily bars, close increasing by 1.0/day; OHLC kept consistent around close."""
    rows = []
    for i in range(n):
        d = date.fromordinal(start.toordinal() + i)
        c = first_close + i
        rows.append({
            "ts": datetime(d.year, d.month, d.day, tzinfo=UTC),
            "open": c - 0.5, "high": c + 0.5, "low": c - 1.0, "close": c, "volume": 1000.0,
        })
    return pl.DataFrame(rows)


def aapl_4for1_split() -> CorporateAction:
    return CorporateAction(symbol="AAPL", action_type=ActionType.SPLIT,
                           ex_date=date(2020, 8, 31), announce_date=date(2020, 7, 30), ratio=4.0)
```

- [ ] **Step 3: Write failing reader tests**

Create `tests/unit/test_pit_reader.py`:
```python
from datetime import UTC, date, datetime

import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import aapl_4for1_split, linear_bars


def _reader(tmp_path) -> PointInTimeReader:  # type: ignore[no-untyped-def]
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 25), 12))  # 25th..(25+11)
    return PointInTimeReader(store, actions={"AAPL": [aapl_4for1_split()]})


def test_firewall_excludes_future_bars(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _reader(tmp_path)
    when = datetime(2020, 8, 28, tzinfo=UTC)
    out = r.as_of("AAPL", when)
    assert out["ts"].max() <= when            # no future bars
    assert out.height == 4                     # 25,26,27,28


def test_split_applied_when_known(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _reader(tmp_path)
    out = r.as_of("AAPL", datetime(2020, 9, 5, tzinfo=UTC))
    pre = out.filter(out["ts"] < datetime(2020, 8, 31, tzinfo=UTC))
    post = out.filter(out["ts"] >= datetime(2020, 8, 31, tzinfo=UTC))
    # pre-ex closes are quartered (100..105 → 25..26.25); post-ex unadjusted
    assert pre["close"].to_list()[0] == pytest.approx(100.0 / 4)
    assert post["close"].to_list()[0] == pytest.approx(106.0)
```

- [ ] **Step 4: Run, verify it fails**

Run: `uv run pytest tests/unit/test_pit_reader.py -q`
Expected: FAIL — `ModuleNotFoundError: alpha_data.pit`.

- [ ] **Step 5: Implement the reader**

Create `packages/alpha-data/src/alpha_data/pit.py`:
```python
"""Point-in-time reader — the look-ahead firewall. Strategies read ONLY here."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

import polars as pl

from alpha_core import CorporateAction
from alpha_data.corporate import known_actions, split_factor
from alpha_data.store import ParquetStore

_PRICE_COLS = ("open", "high", "low", "close")


class PointInTimeReader:
    """Returns split-adjusted bars visible at ``when`` — future bars are physically excluded."""

    def __init__(self, store: ParquetStore, actions: Mapping[str, Sequence[CorporateAction]]) -> None:
        self._store = store
        self._actions = actions

    def as_of(self, symbol: str, when: datetime) -> pl.DataFrame:
        bars = self._store.read_bars(symbol).filter(pl.col("ts") <= when)  # firewall
        known = known_actions(self._actions.get(symbol, []), when.date())  # knowledge gate
        if not known:
            return bars
        factor = pl.col("ts").map_elements(
            lambda ts: split_factor(ts.date(), known), return_dtype=pl.Float64
        )
        adjusted = bars.with_columns(
            [(pl.col(c) * factor).alias(c) for c in _PRICE_COLS]
            + [(pl.col("volume") / factor).alias("volume")]
        )
        return adjusted
```

- [ ] **Step 6: Run, verify pass + full gate**

Run:
```bash
uv run pytest -q
uv run lint-imports
uv run mypy packages apps tests
```
Expected: pytest PASS; lint-imports 5 kept / 0 broken; mypy clean.

- [ ] **Step 7: Commit**
```bash
git add packages/alpha-core/src/alpha_core/protocols.py packages/alpha-data/src/alpha_data/pit.py tests/fixtures/pit_fixtures.py tests/unit/test_pit_reader.py
git commit -m "feat(data): PointInTimeReader.as_of firewall (split-adjusted, knowledge-gated)"
```

---

## Task 6: Bias guards

**Files:**
- Create: `tests/bias_guards/test_pit_future_poison.py`
- Create: `tests/bias_guards/test_pit_corporate_action.py`
- Create: `tests/bias_guards/test_survivorship.py`

- [ ] **Step 1: Future-poison guard on the real accessor**

Create `tests/bias_guards/test_pit_future_poison.py`:
```python
"""Poisoning bars AFTER `when` must not change the as_of(when) result."""
from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_future_poison_does_not_change_as_of(tmp_path) -> None:  # type: ignore[no-untyped-def]
    clean = linear_bars("X", date(2024, 1, 1), 10)
    store = ParquetStore(tmp_path)
    store.write_bars("X", clean)
    when = datetime(2024, 1, 5, tzinfo=UTC)
    baseline = PointInTimeReader(store, actions={}).as_of("X", when)

    # poison every bar strictly after `when` with absurd values, rewrite, re-read
    poisoned = clean.with_columns(
        pl.when(pl.col("ts") > when).then(pl.lit(9.9e9)).otherwise(pl.col("close")).alias("close")
    )
    store.write_bars("X", poisoned)
    after = PointInTimeReader(store, actions={}).as_of("X", when)

    assert baseline.equals(after)
```

- [ ] **Step 2: Point-in-time corporate-action guard (AAPL)**

Create `tests/bias_guards/test_pit_corporate_action.py`:
```python
"""A split must be invisible before its announce_date and applied only to pre-ex bars."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import aapl_4for1_split, linear_bars

pytestmark = pytest.mark.bias_guard


def _reader(tmp_path):  # type: ignore[no-untyped-def]
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 25), 12, first_close=100.0))
    return PointInTimeReader(store, actions={"AAPL": [aapl_4for1_split()]})


def test_split_invisible_before_announce(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _reader(tmp_path)
    # announce is 2020-07-30; as_of on 2020-08-28 is AFTER announce, so it's known.
    # Build a query BEFORE announce by using an earlier `when` that still has bars:
    # all fixture bars are >= 2020-08-25 (after announce), so instead assert the gate
    # via a reader whose action announce is in the future relative to `when`.
    from alpha_core import ActionType, CorporateAction

    store = ParquetStore(tmp_path)
    store.write_bars("ZZ", linear_bars("ZZ", date(2020, 1, 2), 5, first_close=100.0))
    future_announce = CorporateAction(symbol="ZZ", action_type=ActionType.SPLIT,
                                      ex_date=date(2020, 6, 1), announce_date=date(2020, 5, 1), ratio=4.0)
    r2 = PointInTimeReader(store, actions={"ZZ": [future_announce]})
    out = r2.as_of("ZZ", datetime(2020, 1, 6, tzinfo=UTC))  # before the 2020-05-01 announce
    assert out["close"].to_list() == [100.0, 101.0, 102.0, 103.0, 104.0]  # unadjusted


def test_split_applied_to_pre_ex_only_when_known(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _reader(tmp_path)
    out = r.as_of("AAPL", datetime(2020, 9, 5, tzinfo=UTC))
    by_ts = {row["ts"].date(): row["close"] for row in out.iter_rows(named=True)}
    assert by_ts[date(2020, 8, 30)] == pytest.approx(105.0 / 4)  # pre-ex quartered
    assert by_ts[date(2020, 8, 31)] == pytest.approx(106.0)      # ex day unadjusted
```

- [ ] **Step 3: Survivorship guard**

Create `tests/bias_guards/test_survivorship.py`:
```python
"""A symbol that later stops trading must still be readable as-of a date it was alive."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard


def test_delisted_symbol_present_in_as_of_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # "DEAD" trades only Jan 2024 then delists. As-of mid-Jan it MUST be visible.
    store = ParquetStore(tmp_path)
    store.write_bars("DEAD", linear_bars("DEAD", date(2024, 1, 1), 10))
    out = PointInTimeReader(store, actions={}).as_of("DEAD", datetime(2024, 1, 7, tzinfo=UTC))
    assert out.height == 7
    assert out["close"].max() is not None
```

- [ ] **Step 4: Run the guards**

Run: `uv run pytest -m bias_guard -q`
Expected: PASS — the original Phase-0 template guard plus the three new PIT guards (4 selected).

- [ ] **Step 5: Commit**
```bash
git add tests/bias_guards/test_pit_future_poison.py tests/bias_guards/test_pit_corporate_action.py tests/bias_guards/test_survivorship.py
git commit -m "test(bias): PIT future-poison, corporate-action knowledge gate, survivorship guards"
```

---

## Task 7: Final gate

- [ ] **Step 1: Run the full gate (mirrors CI)**

Run:
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy packages apps tests && uv run lint-imports && uv run pytest -q && uv run pytest -m bias_guard -q
```
Expected: all green. If `ruff format --check` flags new files, run `uv run ruff format .` and review the diff.

- [ ] **Step 2: Fix anything red, re-run until green.**

If mypy flags the `map_elements` lambda return type, ensure `return_dtype=pl.Float64` is set (it is). If a Polars datetime/`date()` comparison errors, confirm fixture timestamps are tz-aware (UTC) and `when` is tz-aware.

- [ ] **Step 3: Final commit (if fixes were made)**
```bash
git add -A && git commit -m "chore(data): phase-1a gate green"
```

---

## Done = Phase 1a complete

- `Bar` rejects inconsistent OHLC / non-positive prices / negative volume / NaN (unit + Hypothesis).
- `CorporateAction` two-clock semantics correct; split math compounds and gates correctly.
- `ParquetStore` round-trips bars.
- `PointInTimeReader.as_of(symbol, when)` returns split-adjusted, knowledge-gated bars and physically excludes future bars.
- Bias guards green: future-poison on the real accessor, the AAPL point-in-time split gate, and survivorship — all `@pytest.mark.bias_guard`, all in CI.
- Full gate green.

**Next plan:** Phase 1b — real free-data adapters (ccxt/binance.vision, Stooq/Tiingo/yfinance, Dukascopy, FRED), DuckDB ASOF optimization, dividend total-return adjustment, immutable snapshots + manifest (parser/source provenance), and the `alpha data pull/snapshot/verify` CLI.

## Notes / risks

- **Polars `map_elements` is row-wise (slow at scale).** Fine for fixtures and daily bars; when symbol histories get large in Phase 1b, replace the factor attach with a vectorized join or the DuckDB ASOF join (spec §6.1). Behavior is pinned by the tests, so the optimization is safe to swap in later.
- **`tests/fixtures/` import:** with `--import-mode=importlib` and unique filenames, `from tests.fixtures.pit_fixtures import ...` resolves from the repo root. If collection errors, add empty `tests/__init__.py` + `tests/fixtures/__init__.py`.
- **Dividend adjustment is intentionally absent** here — splits are the correctness-critical case for momentum; dividend total-return (needs prior-close `P_ref`) lands in Phase 1b.
