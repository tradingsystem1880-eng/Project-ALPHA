# Phase 4g — Risk controls + the §13 funding caveat

> **For agentic workers:** TDD per `CLAUDE.md`. Institutional-grade safety + honest cost accounting.

**Goal:** pre-trade risk controls on the paper node (per-order notional cap + kill-switch) and make
the spec §13 crypto borrow/funding gap **visible and quantified**, not silently ignored.

## What landed

- **`PaperSpec.max_notional_per_order: float | None`** — optional pre-trade cap.
- **`alpha_paper/node.py`**:
  - `build_paper_node` configures `LiveRiskEngineConfig(max_notional_per_order={str(instrument.id):
    int(cap)})` when the cap is set (nautilus types the cap as whole quote-currency units).
  - `halt_trading(node)` / `resume_trading(node)` — the **kill-switch**, via
    `node.kernel.risk_engine.set_trading_state(HALTED/ACTIVE)`.
- **`alpha_paper/funding.py`** (pure) — `estimate_short_funding_cost(short_notional, annual_rate_bps,
  days)`: the borrow cost the backtest and sandbox both ignore, so it can be logged/reported (4h).
  `max_leverage` already flows to the sandbox venue's `default_leverage` (4d).

## Tests
- `tests/integration/test_paper_risk.py`:
  - **Kill-switch (end-to-end):** with trading HALTED, every order the strategy attempts is `DENIED`
    by the RiskEngine before the sandbox matcher; zero fills.
  - **Notional cap (config wiring):** `build_paper_node` registers the cap on the RiskEngine
    (`max_notional_per_order(instrument.id) == cap`).
- `tests/unit/test_paper_funding.py`: the funding estimator (scaling + fail-loud on negatives).

## Honest limitations (documented, not hidden)
- **Notional-cap enforcement needs cached market data.** For a MARKET order the RiskEngine computes
  notional from the latest cached quote; with no price it logs "Cannot check MARKET order risk" and
  skips the cap. The synthetic fixture doesn't reliably populate the quote cache at check time, so we
  verify *our wiring* and rely on nautilus's own enforcement tests; the kill-switch path (which denies
  before notional) is proven end-to-end. In live trading the quote cache is continuously populated.
- **Crypto borrow/funding is unmodeled** by both the backtest and the sandbox, so paper PnL is
  optimistic for shorts. `estimate_short_funding_cost` quantifies the gap; 4h logs it into the session
  report. This must be revisited before any real-money phase (spec §13).

## Done = Phase 4g complete
Kill-switch + notional cap wired; funding gap quantified. Gate green (ruff · format · lint-imports
7-kept · mypy --strict 122 files · 206 tests).

**Next:** Phase 4h — the `alpha paper` CLI (`run`/`status`/`report`/`halt`), lazy node imports, wired
into `main.py`; session reporting reuses `alpha_validation.metrics` + the funding estimate.
