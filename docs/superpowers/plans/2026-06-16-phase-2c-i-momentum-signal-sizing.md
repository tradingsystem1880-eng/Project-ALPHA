# Phase 2c-i — Time-Series Momentum Signal + Volatility-Target Sizing

> **For agentic workers:** TDD per `CLAUDE.md`. Pure functions only — the look-ahead-sensitive quant core of the v1 strategy. The nautilus `Strategy` wiring (decide-on-close / execute-on-open) is the next increment (2c-ii).

**Goal:** Encode the v1 strategy's mathematics (spec §7) as pure, strongly-typed, bias-guarded functions in `alpha_strategies` (DAG-legal: depends only on `alpha_core`, no nautilus yet): the time-series momentum signal and volatility-targeted position sizing. These are the highest-risk, most testable pieces — isolating them as pure functions makes them trivial to unit-test and bias-guard before they touch the engine.

**Strategy math (pre-registered, fixed for v1):**
- **Signal:** sign of the trailing `lookback`-bar return, skipping the most recent `skip` bars (classic "12-1": `lookback≈252`, `skip≈21`). +1 / -1 / 0. The skipped bars never influence the decision (short-term reversal) — a property we bias-guard.
- **Sizing:** volatility targeting — scale notional to a constant annualized `target_vol` using realized vol, capped at a per-position leverage limit. `units = signal * min(capital·target_vol/realized_vol, capital·max_leverage) / price`.

**Tech Stack:** Python 3.12 · pure stdlib math · pytest. No new deps, no network. Remove the Phase-0 `placeholder.py` (its dependency edge is now carried by the real modules).

**Scope:** the two pure functions + `realized_volatility` helper. The nautilus `Strategy` subclass, monthly rebalance cadence, portfolio-level caps, and the backtest integration are 2c-ii.

---

## File Map
```
packages/alpha-strategies/src/alpha_strategies/signals.py   # CREATE: ts_momentum_signal
packages/alpha-strategies/src/alpha_strategies/sizing.py    # CREATE: realized_volatility, vol_target_size
packages/alpha-strategies/src/alpha_strategies/placeholder.py # DELETE (edge now carried by signals/sizing)
tests/unit/test_ts_momentum_signal.py                       # CREATE
tests/unit/test_sizing.py                                   # CREATE
tests/bias_guards/test_momentum_signal_lookahead.py         # CREATE: skipped bars never affect the signal
```

## Tasks (TDD red → green)
- [ ] **signals.ts_momentum_signal(closes, lookback, skip)** → +1/-1/0; 0 on insufficient history; `DataError` on bad params / non-positive prices used.
- [ ] **sizing.realized_volatility(closes, *, periods_per_year=252)** → annualized sample-std of simple returns; fails loud.
- [ ] **sizing.vol_target_size(signal, price, annualized_vol, *, target_vol, capital, max_leverage=1.0)** → signed units, leverage-capped; 0 for flat signal; fails loud.
- [ ] **Bias guard:** poisoning the most-recent `skip` bars must not change the signal (they are provably excluded — the momentum encoding's causality property).
- [ ] **Gate** green; delete `placeholder.py`.

## Done = Phase 2c-i complete
- The v1 momentum signal and vol-target sizing exist as pure, typed, unit-tested functions; a bias guard pins that the skipped recent bars never leak into the decision.

**Next:** Phase 2c-ii — the nautilus `TimeSeriesMomentum(Strategy)` wiring these functions on the decide-on-close / execute-on-open base, run through `run_backtest`, producing the first end-to-end equity curve.
