# Phase 4f — Fractional sizing (crypto)

> **For agentic workers:** TDD per `CLAUDE.md`. Parity-preserving change to one shared strategy.

**Goal:** let `TimeSeriesMomentum` trade fractional crypto sizes (instruments with
`size_precision > 0`), which the integer-lot path rejected, while leaving equity behaviour byte-for-byte
unchanged — and prove crypto parity (backtest == sandbox) with fractional quantities.

## The problem
`on_quote_tick` sized orders with `round(abs(delta))` + `Quantity.from_int(lots)` — precision-0
integer lots. A crypto `CurrencyPair` (`BTCUSDT`, `size_precision=6`) rejects that:
`RuntimeError: Invalid size precision … instrument size precision is 6`. (Surfaced by the 4e crypto
parity attempt.)

## What changed
`alpha_strategies/ts_momentum.py` `on_quote_tick` now sizes against the traded instrument's precision:
```
instrument = self.cache.instrument(self._iid)   # fail loud (AlphaError) if absent
precision  = instrument.size_precision
qty_value  = round(abs(delta), precision)        # precision 0 == the old round(); 6 dp for crypto
if qty_value <= 0.0: return                       # below one increment -> skip
Quantity(qty_value, precision)
```
- **Equity unchanged:** `round(x, 0) == round(x)` and `Quantity(v, 0) == Quantity.from_int(v)`, so
  every existing equity backtest / gauntlet / parity result is identical (verified: those tests pass
  untouched).
- One shared strategy class serves both engines, so the change mirrors into backtest and paper
  automatically — parity is preserved by construction.

## Tests
`tests/bias_guards/test_paper_parity.py` refactored to a shared `_parity_order_logs(...)` helper with
two bias-guard cases:
- **equity** (integer lots, prices ~100) — order logs match.
- **crypto** (`BTC/USDT`, `size_precision=6`, realistic ~$60k prices) — order logs match **and** at
  least one quantity is fractional (`_has_fractional_quantity`), proving fractional sizing is genuinely
  exercised. This second live node coexists thanks to the 4e session logging guard.

## Done = Phase 4f complete
Crypto trades fractional units; backtest == sandbox for both asset classes; equity behaviour
preserved. Gate green (ruff · format · lint-imports 7-kept · mypy --strict 119 files · 199 tests).

**Next:** Phase 4g — risk controls (RiskEngine caps, max leverage, kill-switch) + the spec §13
crypto borrow/funding caveat (document + estimate, don't silently ignore).
