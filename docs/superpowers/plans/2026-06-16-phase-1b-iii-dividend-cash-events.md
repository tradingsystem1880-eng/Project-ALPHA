# Phase 1b-iii — Dividends as Decoupled Cash Events (PIT firewall)

> **For agentic workers:** TDD per `CLAUDE.md` — failing test → minimal code → green → commit. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gap where cash dividends are *parsed and stored* (yfinance adapter emits `DIVIDEND` actions) but are **invisible to the point-in-time firewall** — `split_factor` applies only `SPLIT`s, and `PointInTimeReader` never surfaces dividends at all. After this phase the firewall exposes knowledge-gated cash dividends as a separate channel the backtest engine (Phase 2) will credit at `pay_date`.

**Decision (owner-confirmed):** dividends are **decoupled cash events**, not a price adjustment. This follows spec §6.1.4 — *"Decouple price from cash: the price series adjusts on ex-date; cash dividends are credited to the portfolio on pay_date. Different events in the engine."* The ex-date price drop stays a real price move; we do **not** back-adjust prices into a total-return series. (A total-return *view* for signal computation, if wanted, is an additive later increment and does not change this firewall behavior.)

**Architecture:** Keep the two clocks separate. `split_factor` (price adjustment, application gate = `ex_date`) is unchanged. A new `cash_dividends()` helper pulls the `DIVIDEND` actions out of a knowledge-gated action list. `PointInTimeReader` gains `dividends_as_of(symbol, when)` — the cash-event sibling of `as_of` — gated by the *same* knowledge clock (`knowledge_time <= when` on the UTC session date). The bars channel (`as_of`) is untouched: dividends never alter prices.

**Tech Stack:** Python 3.12 · Polars · pydantic · pytest (`bias_guard` marker). No new dependencies, no network.

**Scope:** dividend cash-event exposure through the PIT seam only. FX (Dukascopy), FRED macro, total-return price views, and DuckDB ASOF remain in later plans.

**Branch:** `claude/practical-feynman-wwazv2` (session branch). Finish step pushes + opens a draft PR.

---

## File Map

```
packages/alpha-data/src/alpha_data/corporate.py   # ADD: cash_dividends()
packages/alpha-data/src/alpha_data/pit.py         # ADD: PointInTimeReader.dividends_as_of()
tests/fixtures/pit_fixtures.py                     # ADD: aapl_dividend() (real 2020-Q3 AAPL div)
tests/unit/test_dividends_pit.py                   # CREATE: cash_dividends + dividends_as_of units
tests/bias_guards/test_pit_dividend_event.py       # CREATE: invisible-before-announce, no price
                                                   #         contamination, exposed-for-crediting
```

---

## Task 1: `cash_dividends` helper (corporate.py)

- [ ] **Red:** `tests/unit/test_dividends_pit.py::test_cash_dividends_filters_to_dividend_only` — feed a mixed `[split, dividend]` list, expect only the `DIVIDEND` back. Import `cash_dividends` → `ImportError`.
- [ ] **Green:** add `cash_dividends(actions)` to `corporate.py` — returns the `DIVIDEND` actions in input order; fails loud (`DataError`) if a `DIVIDEND` somehow has no `amount` (mirrors `split_factor`'s ratio guard).
- [ ] **Commit:** `feat(data): cash_dividends — separate DIVIDEND events from split_factor's price path`

## Task 2: `dividends_as_of` on the firewall (pit.py)

- [ ] **Red:** unit tests for the knowledge-gate boundary (invisible at `announce - 1d`, visible on `announce` day) and the split+dividend coexistence case; bias-guard tests below.
- [ ] **Green:** add `PointInTimeReader.dividends_as_of(symbol, when)` — `cash_dividends(known_actions(self._actions.get(symbol, []), when.astimezone(UTC).date()))`. Reads no bars; does not touch the price series.
- [ ] Add `aapl_dividend()` to `pit_fixtures.py` — AAPL's 2020-Q3 cash dividend: `ex_date=2020-08-07`, `announce_date=2020-07-30` (same day it announced the 4-for-1 split), `record_date=2020-08-10`, `pay_date=2020-08-13`, `amount=0.82`.
- [ ] **Commit:** `feat(data): PIT dividends_as_of — knowledge-gated cash events, prices untouched (spec §6.1.4)`

## Task 3: Bias guard (the headline)

`tests/bias_guards/test_pit_dividend_event.py` (`pytestmark = pytest.mark.bias_guard`):
- [ ] **Invisible before announce:** `dividends_as_of(when < announce)` → `[]`.
- [ ] **No price contamination:** `as_of` close series is identical with vs. without the dividend in the action set (the decouple property — dividends are cash, not price).
- [ ] **Exposed for crediting:** after announce, `dividends_as_of` returns the dividend with correct `ex_date` / `pay_date` / `amount`.

## Task 4: Final gate

- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy packages apps tests && uv run lint-imports && uv run pytest -q -m "not network" && uv run pytest -m bias_guard -q`
- [ ] Expected: all green; `lint-imports` 5 kept / 0 broken; bias_guard count grows by the new dividend guard.
- [ ] **Commit** any format/lint fixups: `chore(data): phase-1b-iii gate green`.

---

## Done = Phase 1b-iii complete
- Cash dividends flow through the PIT firewall as knowledge-gated events for `pay_date` crediting; the price series (`as_of`) is provably unchanged by them.
- A bias guard pins a real AAPL dividend: invisible before its announce_date, never contaminating prices, surfaced for crediting once known.
- Full gate green; CI still `-m "not network"`.

**Next:** total-return signal view (optional) · FX (Dukascopy) + FRED macro adapters · dividend pay-date crediting wired in the Phase-2 engine · DuckDB ASOF. Then settle the PIT seam before the Phase 2 engine.
