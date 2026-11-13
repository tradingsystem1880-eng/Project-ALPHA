---
owner: domain core
sources:
  - packages/alpha-core/src/**
  - tests/unit/test_core_types.py
  - tests/unit/test_bar_invariants.py
  - tests/unit/test_corporate_actions.py
  - tests/unit/test_universe_store.py
  - tests/unit/test_forecast_settings.py
verified: 1ac86fc02443
---

# Core invariants

What must hold in `alpha_core` (`packages/alpha-core/src/alpha_core/`): the frozen domain values, typed
errors, settings and structural protocols that every other package imports. Project-wide rules live in
[research integrity](research-integrity.md) and [engineering](engineering.md); this file holds the core mechanics.

## Package boundary

- Never import another `alpha_*` package from `alpha_core`: it is layer 0 of the DAG. Enforced by the
  import-linter contract `alpha_core imports nothing internal` in `pyproject.toml` (`uv run lint-imports`).
  [engineering § Import layers](engineering.md#import-layers), [ADR-0001](../../adr/0001-strict-layered-dag.md).
- Concrete implementations of the protocols live in higher packages, never here (`protocols.py`).

## Domain values

- Keep every value type frozen (`ConfigDict(frozen=True)`): traces and hashes downstream assume values never
  change after construction. `tests/unit/test_core_types.py::test_bar_is_frozen`.
- `Bar` rejects non-finite fields, negative volume, any price <= 0, and an open or close outside `[low, high]`.
  Do not relax these checks to admit vendor data; repair or quarantine belongs in `alpha_data`.
  Enforced by `tests/unit/test_bar_invariants.py`.
  [research integrity § Invalid data fails loud](research-integrity.md#invalid-data-fails-loud).
- `Bar.ts` is timezone-aware. Daily bars are stamped at the session date 00:00 UTC, not at the close
  instant; the close-time stamp is added by the backtest feed ([backtest § Next-open fills](backtest.md#next-open-fills)).
- `DecisionTrace.signal` is -1, 0, 1 or None; `target_quantity` is finite; `instrument_id` and `reason`
  are non-empty.
- `IndicatorTrace.value` and `ChartAnchor.value` are finite. `ChartAnnotationTrace` needs at least two
  anchors and no anchor after `decision_ts`: annotations are emitted at decision time, never reconstructed.
- `ExecutionRejectionTrace` only describes an unaffordable CASH buy: side `BUY`, positive quantity and
  price, finite amounts, `required_cash > available_cash`.
  `tests/unit/test_core_types.py::test_execution_rejection_trace_requires_a_real_cash_shortfall`.

## Errors

- Raise `DataError` for ingestion, storage or integrity failures and `LookAheadError` when a read would see
  the future; both subclass `AlphaError`. Never raise bare `Exception` and never swallow these (`errors.py`).
  [engineering § Errors](engineering.md#errors).

## Corporate actions and membership

- `CorporateAction.knowledge_time` is `announce_date`, else `ex_date` with `knowledge_is_estimated = True`.
  Treat the fallback as an estimate, never as a known announcement. `announce_date` after `ex_date` is
  rejected. [research integrity § Corporate actions: two clocks](research-integrity.md#corporate-actions-two-clocks),
  [ADR-0004](../../adr/0004-two-clock-corporate-actions.md).
- `SPLIT` needs a finite `ratio > 0` (new shares over old: a 4-for-1 split is 4.0); `DIVIDEND` needs a
  finite `amount > 0` in cash per share. Enforced by `tests/unit/test_corporate_actions.py`.
- `pay_date` travels on the action; dividend cash lands at `pay_date`, see [backtest § Dividends](backtest.md#dividends).
- `UniverseMembership` is the interval `[effective_from, effective_to)`; `effective_to` is None while the name
  is a member, and `delisting_return` requires `effective_to`. `members_as_of` is the only sanctioned
  membership read. `tests/unit/test_universe_store.py`, `tests/bias_guards/test_universe_survivorship.py`.

## Protocols

- `DataSource.as_of(symbol, when)` takes an aware datetime and must never return a bar not knowable at
  `when`. [research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads),
  [ADR-0005](../../adr/0005-point-in-time-firewall.md).
- `ExecutionEventSink` is for paper execution only. Keep it out of deterministic run specifications and
  hashes; payloads are flat JSON scalars so no engine object, credential, tick or bar crosses it.
  [ADR-0012](../../adr/0012-operational-paper-sessions.md).

## Costs

- Convert basis points with `costs.py::bps_rate`: it rejects a non-finite or negative fee and divides by
  10,000 first. `BpsFeeModel` and the strategy CASH affordability check both call it, so the reserved fee
  and the charged fee use the identical operation. `tests/integration/test_frictions.py`,
  `tests/integration/test_order_rejection.py::test_fee_reserve_uses_the_identical_rate_operation_and_currency_rounding`.

## Settings

- `AlphaSettings` reads `ALPHA_*` environment variables and `.env`. `paper_enabled` and `ibkr_paper_enabled`
  default to False; both must be true before execution clients may be built. Never change these defaults.
  [research integrity § No live capital](research-integrity.md#no-live-capital).
- `data_dir` stays the authority for manifests, control state and sensitive metadata; `bulk_data_dir` may
  live on a separately pinned volume for public bulk datasets only.
- Paper sessions, `ibkr_gateway_app`, `forecast_hub_cache` and `forecast_local_only` are machine-local
  execution details: never put them in run ids, manifests or signal-cache keys. Kronos weight identity is
  model id plus revision. [ADR-0010](../../adr/0010-local-kronos-weights-offline-policy.md).
- `random_seed` (default 7) is a setting; research D0/D1 seeds are frozen, not derived from settings.
  [research integrity § Deterministic seeds and identity](research-integrity.md#deterministic-seeds-and-identity).
- Forecast settings (device, revisions, pretrain cutoff) are covered in [forecast § Settings and leakage](forecast.md#settings-and-leakage).

## Source identity

- `alpha_core` source bytes feed the v3 run `execution_fingerprint` (`apps/alpha-cli/src/alpha_cli/_identity.py`)
  and the RD-Agent rule profiles ([workers § RD-Agent worker](workers.md#rd-agent-worker)): any byte change,
  comments included, changes those identities. [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
