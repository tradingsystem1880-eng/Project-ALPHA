# Phase 1c — Settle the PIT Seam: a Typed Point-in-Time `DataSource`

> **For agentic workers:** TDD per `CLAUDE.md` — failing test → minimal code → green → commit. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Settle the point-in-time seam before the Phase-2 engine. `alpha_core` already defines the `DataSource` protocol — `available_symbols()` + `as_of(symbol, when) -> list[Bar]` (typed, validated `Bar`s). The current `PointInTimeReader` returns a Polars **DataFrame** and deliberately does *not* satisfy it ("reserved for a later phase"). This phase provides the typed bridge: a `PointInTimeSource` that emits chronologically-ordered, validated `Bar` objects — the single seam the backtest engine and strategies consume (they never touch a raw DataFrame).

**Architecture:** `PointInTimeSource` *composes* `PointInTimeReader` (no logic duplication): the same look-ahead firewall, split back-adjustment, and knowledge gate apply. `as_of` converts the reader's frame rows into typed `alpha_core.Bar`s (re-validating OHLC invariants — split-adjusted prices stay valid since all OHLC scale by one factor). Dividends ride the reader's separate decoupled cash channel (spec §6.1.4), surfaced via a `dividends_as_of` passthrough so the engine has one seam for both. `ParquetStore` gains `list_symbols()` (slash-symbols like `BTC/USD` reconstructed from the `bars/` tree) to back `available_symbols()`.

**Tech Stack:** Python 3.12 · Polars · pydantic · pytest. No new dependencies, no network. DAG-legal: `alpha_data` → `alpha_core` only.

**Scope:** the typed `DataSource` seam + `list_symbols` only. nautilus engine, strategies, FX/FRED adapters, total-return view, and DuckDB ASOF remain in later plans.

**Branch:** `claude/practical-feynman-wwazv2` (session branch; PR #1 updates on push).

---

## File Map

```
packages/alpha-data/src/alpha_data/store.py    # ADD: ParquetStore.list_symbols()
packages/alpha-data/src/alpha_data/source.py   # CREATE: PointInTimeSource (typed DataSource)
tests/unit/test_parquet_store.py               # ADD: list_symbols (slash-safe, empty)
tests/unit/test_pit_source.py                  # CREATE: protocol conformance, typed/adjusted bars,
                                               #         symbols, dividend passthrough, unknown symbol
tests/bias_guards/test_source_future_poison.py # CREATE: typed path excludes + is immune to future data
```

---

## Task 1: `ParquetStore.list_symbols`
- [ ] **Red:** `test_list_symbols_reconstructs_slash_symbols` (AAPL + BTC/USD → `["AAPL", "BTC/USD"]`) and `test_list_symbols_empty_when_no_bars`.
- [ ] **Green:** walk `<root>/bars/**/*.parquet`; symbol = path relative to `bars/` with the `.parquet` suffix stripped; sorted. Empty list when the dir is absent.
- [ ] **Commit:** `feat(data): ParquetStore.list_symbols — enumerate stored symbols (slash-safe)`

## Task 2: `PointInTimeSource` typed `DataSource`
- [ ] **Red:** `tests/unit/test_pit_source.py` —
  - structurally satisfies `alpha_core.protocols.DataSource` (`isinstance`, runtime_checkable);
  - `as_of` returns `list[Bar]`, chronological, split-adjusted (AAPL 4-for-1: pre-ex bar quartered, ex-day untouched);
  - `available_symbols()` includes a slash symbol;
  - `dividends_as_of` passthrough returns known dividends;
  - `as_of` on an unknown symbol raises `DataError`.
- [ ] **Green:** create `source.py` — `PointInTimeSource(store, actions)` wrapping a `PointInTimeReader`; `as_of` maps frame rows → validated `Bar`s; `available_symbols` → `store.list_symbols()`; `dividends_as_of` delegates.
- [ ] **Commit:** `feat(data): PointInTimeSource — typed point-in-time DataSource seam (settle PIT seam)`

## Task 3: Bias guard — typed-path future poison
- [ ] `tests/bias_guards/test_source_future_poison.py` (`pytestmark = pytest.mark.bias_guard`): `as_of(when)` yields only bars `ts <= when`; poisoning bars strictly after `when` and re-querying returns byte-identical typed `Bar`s.

## Task 4: Final gate
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy packages apps tests && uv run lint-imports && uv run pytest -q -m "not network" && uv run pytest -m bias_guard -q`
- [ ] Expected: all green; `lint-imports` 5 kept / 0 broken; bias_guard count +1.
- [ ] **Commit** any fixups: `chore(data): phase-1c gate green`.

---

## Done = Phase 1c complete
- A typed `PointInTimeSource` satisfies `alpha_core.DataSource`, emitting validated chronological `Bar`s with split adjustment + knowledge gate intact; dividends reachable via the same seam.
- A bias guard proves the typed path excludes future bars and is immune to post-cutoff data.
- Full gate green. The seam the Phase-2 nautilus engine will consume is now settled.

**Next:** Phase 2 — adopt nautilus_trader (thin wrappers), translate `PointInTimeSource` bars into the engine's data feed, encode TS-momentum, configure frictions. FX/FRED adapters, total-return view, and DuckDB ASOF remain optional data-spine increments.
