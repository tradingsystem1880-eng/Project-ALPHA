---
owner: backtest engine
sources:
  - packages/alpha-backtest/src/**
  - tests/unit/test_nautilus_feed.py
  - tests/unit/test_utc_day_execution_feed.py
  - tests/unit/test_portfolio_replay_engine.py
  - tests/integration/test_nautilus_engine.py
  - tests/integration/test_dividend_credit.py
  - tests/integration/test_frictions.py
  - tests/integration/test_order_rejection.py
  - tests/bias_guards/test_cash_fee_affordability_future_poison.py
verified: 1ac86fc02443
---

# Backtest invariants

What must hold in `alpha_backtest` (`packages/alpha-backtest/src/alpha_backtest/`): the single-instrument
Nautilus harness, its feed encoding, fee model and result schema, and the multi-asset weight replay.

## Package boundary

- Import only `alpha_core` and `alpha_data`. Enforced by the import-linter contract
  `alpha_backtest depends only on core + data` in `pyproject.toml`.
  [engineering § Import layers](engineering.md#import-layers).
- Never import `alpha_strategies`; use the optional `configure_cash_execution` hook found with `getattr`.
- Treat edits under `packages/alpha-backtest/src` as high risk: ask for an independent review on the pull
  request. That review is advisory; CI and the owner's merge decide.
  [engineering § Checks and commits](engineering.md#checks-and-commits).

## Next-open fills

- `to_execution_feed` emits two events per session: an open-priced `QuoteTick` at `bar.ts`, then the
  decision `Bar` (full OHLC) at `bar.ts + 23h`. Strategies decide on the bar and fill on the next quote.
  [ADR-0003](../../adr/0003-t+1-fill-encoding.md),
  [research integrity § Decide at close, fill at next open](research-integrity.md#decide-at-close-fill-at-next-open).
- Run the venue with `bar_execution=False` so only quotes fill orders; Nautilus's default fills market
  orders at the bar close. `tests/integration/test_nautilus_engine.py::test_market_order_decided_on_close_fills_at_next_open`.
- The feed requires strictly increasing bars at least 24h apart and raises `DataError` otherwise: tighter
  spacing would make a non-chronological feed that the engine runs silently with zero fills.
  `tests/unit/test_nautilus_feed.py`.
- `timing="utc_day_end_next_open"` needs UTC-midnight bars: the decision bar is stamped at the next
  midnight and the quote one microsecond later. It models execution; it is not evidence the price was
  executable. The default stays `session_close_23h`. `tests/unit/test_utc_day_execution_feed.py`.
- Build instruments through `instrument_for`: slash pairs get a 5-decimal `CurrencyPair`, because
  precision 2 rounds sub-dollar tokens to garbage or zero.

## Fee and slippage model

- Slippage is a side-aware half-spread on the opening quote: bid = open x (1 - s), ask = open x (1 + s).
  The spread is quantised to the price precision, so slippage under one tick has no effect. Quote size is
  large on purpose: book depth is not the slippage model.
- Fees are separate: `BpsFeeModel` charges notional x `bps_rate(fee_bps)` in the instrument's quote
  currency. `run_backtest` rejects a `fee_bps` that is negative or not finite (NaN would silently mean no fee model).
  `tests/integration/test_frictions.py`.
- The account is denominated in the instrument's quote currency so PnL never needs an exchange rate.

## Accounts and rejections

- The default account is CASH (long-flat equities); pass MARGIN, where `leverage` applies, for long-short
  crypto or FX. A CASH venue always gets leverage 1.
- A spot `CurrencyPair` on CASH starts with quote cash and zero base units; starting cash must be in the
  quote currency.
- Nautilus stops without raising when the balance goes negative. `run_backtest` raises `DataError` when the
  equity curve has fewer samples than opening quotes; never catch this to keep a truncated curve.
  `tests/integration/test_dividend_credit.py::test_insolvent_fill_fails_loud_not_truncated`.
- The terminal equity sample is re-read after the run so a final-session fill's fee is never lost.
- Shared-lifecycle CASH buy rejections land in `BacktestResult.execution_rejections`; the CLI persists them
  as `pretrade_rejections.parquet` and reconciles the count with venue denials. Strategies without the hook
  keep only the truncation check. `tests/integration/test_order_rejection.py`.
- The run manifest records the `pretrade_rejections` count; the execution digest
  (`alpha_cli/research_execution_digest.py`) fails loud when it disagrees with the sidecar rows, and counts
  them in the total `rejected`.

## Dividends

- Entitlement is the net position held before the ex-date session's open; cash lands from the first session
  at or after `pay_date` (`ex_date` when the vendor gave none). A short is debited; a `pay_date` after the
  last session is never credited; only `DIVIDEND` actions with an amount are accepted.
  Enforced by `tests/integration/test_dividend_credit.py`. [ADR-0004](../../adr/0004-two-clock-corporate-actions.md),
  [research integrity § Corporate actions: two clocks](research-integrity.md#corporate-actions-two-clocks).

## Equity and traces

- Equity = starting cash + realized PnL + unrealized PnL + credited dividend cash, sampled at each opening
  quote before that quote's fills settle.
- The benchmark curve is a passive open-to-open, price-only series (`benchmark_kind`
  `passive_open_to_open_price_only`); keep that label on anything derived from it.
- `accounting_trace` must be an empty list and needs a CASH account; it is filled only after successful
  execution and reconciliation.

## Multi-asset replay

- `run_weight_replay` keeps one cash ledger across symbols; per-symbol engines cannot reconcile a rotating
  cross-sectional book. [ADR-0016](../../adr/0016-isolated-qlib-worker.md).
- Inputs: at least 2 symbols with at least 3 bars each on one aligned daily session grid. Each target
  cross-section covers the full universe, sums to one, has weights in [0, 1], shares one origin and fold,
  executes on the session after its origin, and has `available_at = origin + 23h`.
- Quantities are fixed at the decision close; the next open sets only the price. Sells run before buys; a
  cash shortfall scales all buys pro rata (`PARTIALLY_FILLED`), never borrowing or dropping a symbol.
- Long-only: a short raises. The replay must end flat with every target reconciled to one following open.
  `fee_bps` and `slippage_bps` are finite and in [0, 10000). `tests/unit/test_portfolio_replay_engine.py`,
  `tests/bias_guards/test_ml_replay_future_poison.py`.

## Source identity

- Package bytes feed the v3 run `execution_fingerprint` and the RD-Agent economics profile
  ([workers § RD-Agent worker](workers.md#rd-agent-worker)).
  [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
