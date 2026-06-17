# Phase 2d-iii — Faithful per-session mark-to-market equity curve

> **For agentic workers:** TDD per `CLAUDE.md`. Replaces the realized-cash equity curve with a
> per-session MtM net-liquidation curve — the clean returns input the Phase-3 gauntlet needs.

**Goal:** The 2d-i equity curve came from the account report `total`, which for a CASH account is realized cash only (an open position isn't marked to market) and emits rows only on balance changes. Replace it with a **per-session mark-to-market** curve so returns reflect unrealized P&L each session.

**Spike findings (probed):**
- Neither CASH nor MARGIN account reports mark-to-market per session (rows only on balance changes; margin `total` ignores unrealized P&L).
- `portfolio.realized_pnls(venue)` is **net of commissions** (1978 = 2000 − 22).
- `equity = starting_cash + Σ realized_pnls + Σ unrealized_pnls` reconciles exactly (closed: 1,001,978; holding @120: 1,002,000) and is **account-type-agnostic** and **short-correct** (signed unrealized).

**Mechanism:** a lightweight nautilus `Actor` (`_EquityRecorder`) subscribes to the execution quotes (one per session open) and appends `(ts, starting_cash + realized + unrealized)` on each. `run_backtest` adds it via `engine.add_actor` and returns `recorder.curve` as `BacktestResult.equity_curve`. (Gotcha hit + fixed: an instance attr named `_start` clobbers nautilus `Component._start()` — renamed to `_starting_cash`.)

**Tech Stack:** Python 3.12 · nautilus_trader 1.228 · pytest. Offline. No new deps.

---

## File Map
```
packages/alpha-backtest/src/alpha_backtest/engine.py    # MODIFY: _EquityRecorder actor; curve from it (drop account-report _equity_curve)
packages/alpha-backtest/src/alpha_backtest/results.py   # MODIFY: equity_curve docstring (now per-session MtM)
tests/integration/test_equity_curve.py                  # CREATE: buy-and-hold marks to market each session
```

## Tasks (TDD red → green)
- [ ] `_EquityRecorder(Actor)`: per-quote snapshot of `starting + realized + unrealized`.
- [ ] `run_backtest` adds the actor and returns `recorder.curve`.
- [ ] **Test:** buy-and-hold (never closes) → 5 session snapshots; equity marks to each session's open (session 1 → 1,001,000; session 4 → 1,004,000) — proving MtM, since a realized-cash curve would sit flat near 990,000. Existing round-trip / fee tests still pass via the new formula.
- [ ] **Gate** green.

## Done = Phase 2d-iii complete
- The equity curve is a per-session, net-of-fees, mark-to-market net-liquidation series — the returns basis for validation. **Phase 2 is complete**: PIT-safe data → decide-on-close/fill-at-open execution → trade log + MtM equity curve, with fees + slippage.

**Next:** Phase 3 — the `alpha validate` gauntlet (walk-forward OOS, randomized-price null, block-bootstrap BCa CIs) consuming the equity curve / trade log.
