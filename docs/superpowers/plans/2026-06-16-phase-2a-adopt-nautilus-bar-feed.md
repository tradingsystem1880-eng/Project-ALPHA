# Phase 2a — Adopt nautilus_trader + the Bar-Feed Translation Seam

> **For agentic workers:** TDD per `CLAUDE.md` — failing test → minimal code → green → commit.

**Goal:** Kick off Phase 2 (backtest core). Two steps: (1) adopt the spec-mandated engine `nautilus_trader` into the workspace, proving it installs, imports, and leaves the whole gate green; (2) build the first thin wrapper — translate the PIT firewall's typed `alpha_core.Bar` objects (from `PointInTimeSource`) into nautilus `Bar` objects, the data feed the `BacktestEngine` will consume. This is the spec §13 "early Phase-2 spike" reduced to its lowest-risk core: the data-feed bridge, offline-tested, before any engine run.

**Dependency note:** `nautilus-trader>=1.228` requires `pandas<3`, so the workspace pandas pins down `3.0.3 → 2.3.3`. This is an accepted cost of the chosen engine; the existing gate (incl. the yfinance pandas edge) stays green under it. nautilus ships `py.typed`, so `mypy --strict` analyses it directly (no blanket ignores).

**Architecture:** `alpha_backtest.feed` is the only place `alpha_core.Bar` becomes a nautilus `Bar`. Strategies/engine never touch a raw DataFrame or fetch data — they consume `PointInTimeSource` bars translated here. Chronology and the bar-close timestamp are preserved (`ts_event = ts_init =` bar-close ns); nothing is fetched or reordered. Price/size precision is parameterised (equity default 2/0; FX/crypto pass their own) pending real instrument definitions in the next increment.

**Tech Stack:** Python 3.12 · nautilus_trader 1.228 · pandas 2.3 · pytest. DAG: `alpha_backtest` → `alpha_core` + `alpha_data` (+ nautilus). No network at test time (the dep is vendored once installed).

**Scope:** dependency adoption + `Bar` translation only. Instrument definitions, a `BacktestEngine` run harness, fill/fee models, the TS-momentum strategy, and result extraction are later Phase-2 increments.

**Branch:** `claude/practical-feynman-wwazv2` (session branch; extends PR #1).

---

## File Map

```
packages/alpha-backtest/pyproject.toml          # MODIFY: add nautilus-trader>=1.228
uv.lock                                          # MODIFY: re-locked (pandas -> 2.3.x, +nautilus)
packages/alpha-backtest/src/alpha_backtest/feed.py  # CREATE: daily_bar_type + to_nautilus_bar(s)
tests/unit/test_backtest_deps.py                 # CREATE: nautilus import + version smoke
tests/unit/test_nautilus_feed.py                 # CREATE: Bar translation (equity/crypto/FX), chronology, ts
```

---

## Task 1: Adopt nautilus_trader
- [ ] Add `nautilus-trader>=1.228` to `packages/alpha-backtest/pyproject.toml`; `uv sync`.
- [ ] **Red→Green:** `tests/unit/test_backtest_deps.py` — import `nautilus_trader`, assert major version and that pandas is the engine-compatible 2.x line.
- [ ] Confirm the **whole** gate stays green under the pandas downgrade.
- [ ] **Commit:** `build(backtest): adopt nautilus_trader (pandas pinned <3 for engine compat)`

## Task 2: Bar-feed translation
- [ ] **Red:** `tests/unit/test_nautilus_feed.py` —
  - `daily_bar_type("AAPL")` → a `1-DAY-LAST-EXTERNAL` BarType on the SIM venue; slash-symbol `BTC/USD` also works;
  - `to_nautilus_bar(bar, bt)` preserves OHLCV (float round-trip) and sets `ts_event == ts_init ==` bar-close ns;
  - FX precision (5 dp) and crypto magnitude survive round-trip;
  - `to_nautilus_bars(source.as_of(...))` preserves chronological order and count.
- [ ] **Green:** create `feed.py` — `daily_bar_type`, `to_nautilus_bar`, `to_nautilus_bars`.
- [ ] **Commit:** `feat(backtest): nautilus bar-feed translation — alpha_core.Bar -> nautilus Bar`

## Task 3: Final gate
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy packages apps tests && uv run lint-imports && uv run pytest -q -m "not network" && uv run pytest -m bias_guard -q`
- [ ] All green; `lint-imports` 5 kept / 0 broken. **Commit** fixups: `chore(backtest): phase-2a gate green`.

---

## Done = Phase 2a complete
- nautilus_trader is a workspace dependency; it imports and the full gate is green under the required pandas downgrade.
- A single, tested seam translates look-ahead-safe `PointInTimeSource` bars into nautilus `Bar` objects, preserving chronology and the bar-close timestamp.

**Next:** Phase 2b — instrument definitions per asset class + a `BacktestEngine` run harness feeding these bars (do-nothing strategy first, asserting bar count + no intrabar fills), then the TS-momentum strategy, fill/fee models, and the standard result schema.
