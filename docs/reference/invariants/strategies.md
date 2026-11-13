---
owner: strategy layer
sources:
  - packages/alpha-strategies/src/**
  - tests/unit/test_rules*.py
  - tests/unit/test_signal*.py
  - tests/unit/test_sizing.py
  - tests/unit/test_ts_momentum_signal.py
  - tests/unit/test_run_identity_rules.py
  - tests/bias_guards/test_momentum_signal_lookahead.py
  - tests/bias_guards/test_signal_window_boundary.py
  - tests/integration/test_order_rejection.py
verified: 0377681b
---

# Strategy invariants

What must hold in `alpha_strategies` (`packages/alpha-strategies/src/alpha_strategies/`): pure signals,
vol-target sizing, owner-authored rule specs, and the shared Nautilus lifecycle `VolTargetStrategy`.

## Package boundary

- Import only `alpha_core` and `alpha_patterns`. Enforced by the import-linter contract
  `alpha_strategies depends only on core and patterns` in `pyproject.toml`.
  [engineering § Import layers](engineering.md#import-layers).
- Take indicators from `alpha_patterns` (the functions `alpha chart overlays` draws); never re-implement
  one here. Parity is pinned by `tests/unit/test_rules_indicators_parity.py`.
- Never import `alpha_backtest`. The engine reaches the strategy only through the optional
  `configure_cash_execution` hook it looks up with `getattr`, so the dependency stays one-way.

## Decide at close, fill at next open

- `VolTargetStrategy.on_bar` (the close of t) fixes the target; `on_quote_tick` (the open of t+1) only
  turns the pending target into an order. Never compute or change a target from the opening quote.
  [research integrity § Decide at close, fill at next open](research-integrity.md#decide-at-close-fill-at-next-open).
  Enforced by `tests/bias_guards/test_cash_fee_affordability_future_poison.py`.
- Record a `DecisionTrace` with a reason for every decision taken (rebalance or halt), including flat,
  halted and zero-volatility outcomes; the trace is a published causal artifact.
- Subclasses implement only `_signal()`; history, cadence, sizing and order flow stay in the base.

## Pure signals

- Functions in `signals.py` return -1, 0 or 1 from the trailing window they are handed and never read past
  the decision bar. They return 0 on insufficient history and raise `DataError` on bad parameters or on a
  non-finite or non-positive price. `tests/bias_guards/test_momentum_signal_lookahead.py`,
  `tests/bias_guards/test_signal_window_boundary.py`, `tests/unit/test_signals_extra.py`.
- `ts_momentum_signal` excludes the most recent `skip` bars; they must never influence the signal.

## Sizing

- `realized_volatility` is the sample standard deviation (ddof 1) of simple returns times
  `sqrt(periods_per_year)`; it needs at least 3 finite positive closes.
- `vol_target_size`: notional = min(capital x target_vol / vol, capital x max_leverage);
  units = signal x notional / price. Inputs must be finite and positive. `tests/unit/test_sizing.py`.
- Zero realized volatility means flat (`zero_volatility`), never a division by zero.

## Rule specs

- A `RuleSpec` (version 1) is strict JSON: unknown keys fail, at most 12 conditions per side, name at most
  80 characters, `history` a whole number between the longest indicator warm-up and 2,000 bars.
- A rule describes a state on the decision bar (`left op right`, ops `> < >= <=`); there is no "crosses"
  and no order state. Both sides true, or neither, means flat.
- `evaluate_rules` takes exactly `history` trailing bars and raises otherwise. The fixed window keeps the
  decision point-in-time and makes the engine, the Tier-1 surrogate and scans agree bar for bar.
- A non-finite operand on the decision bar (warm-up or undefined statistic) is a `DataError`, never zero.
- Sources are `high`, `low`, `close` only (the history the base keeps). A source `lag` is a non-negative
  integer; an omitted or zero lag keeps the original bytes. `tests/unit/test_rules_source_lag.py`.
- `canonical_json` (sorted keys, compact separators, no NaN) is the run-identity byte string and
  `spec_sha256` hashes it. Never change how an existing spec serialises: it changes run ids.
  `tests/unit/test_run_identity_rules.py`. Bias guard: `tests/unit/test_rules_bias_guard.py`.

## Shared lifecycle

- CASH affordability: on a CASH backtest account with a positive fee, a BUY is rejected whole when
  principal at the t+1 ask plus the currency-rounded commission (same `bps_rate`) exceeds the free quote
  balance. The close-time target is kept and an `ExecutionRejectionTrace` is appended. Sells and MARGIN
  orders are not limited by this check. `tests/integration/test_order_rejection.py`.
- `prime_history` is for paper warm-up only: the caller first enforces snapshot provenance and the
  knowledge cutoff; timestamps must strictly increase; it creates no target and no order.
- Paper risk (`configure_paper_risk`) requires a durable `ExecutionEventSink`. Order authority stays
  withheld until `mark_paper_reconciled` after exact broker-state reconciliation, and each order passes the
  freshness, cutoff, open-order, daily-loss and notional limits. Deterministic backtests leave both unset.
  [research integrity § No live capital](research-integrity.md#no-live-capital).
- `halt_drawdown` is a kill switch: once halted, flatten at the next open and never re-enter.
- Round every order with `normalize_order_quantity` to the instrument's size increment and precision.

## Replay and sandbox strategies

- `SignalReplay` replays a precomputed per-bar signal by bar index; an index the cache does not cover is a
  `DataError`, so a schedule mismatch aborts the run. `tests/unit/test_signal_replay.py`.
  [ADR-0009](../../adr/0009-forecast-leakage-and-tier2-cost-policy.md).
- `hedged_basis.py` only evaluates an already-materialised point-in-time crowding event stream. It builds
  no orders, connects to no venue, and never treats either leg as a universal crypto price.
  [ADR-0033](../../adr/0033-governed-crypto-crowding-research-and-sandbox-basis.md).

## Source identity

- `strategy_fingerprint` hashes `base.py`, `signals.py`, `sizing.py` plus the selected strategy module
  (`apps/alpha-cli/src/alpha_cli/_identity.py`); the whole package also feeds `execution_fingerprint`
  and the RD-Agent rule profiles ([workers § RD-Agent worker](workers.md#rd-agent-worker)). Any byte change
  makes new run identities. [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
