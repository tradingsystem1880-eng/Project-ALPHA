# ADR-0004: Two-clock corporate actions (knowledge time vs ex-date)

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Corporate actions are the highest-risk component of the data layer. Every action carries several dates — `announce_date`, `ex_date`, `record_date`, `pay_date` — and conflating them silently injects look-ahead or mis-adjustment. The common shortcut, a single pre-adjusted (back-adjusted total-return) price series, bakes *future* splits and dividends into *past* prices: at simulated time `t` the series already reflects an action that, in reality, had not yet happened — a textbook look-ahead leak that also destroys the actual ex-date price drop a strategy might legitimately react to.

## Decision

Keep **two independent clocks**, never merged:

- **Knowledge time** = `announce_date` if present, else a conservative fallback to `ex_date` (flagged `knowledge_is_estimated`). Gates **whether** a backtest at time `t` is even aware of the action.
- **Valid time** = `ex_date`. Gates **how/when** the price series mechanically adjusts.

Two distinct filters apply: an action is *available* only when `knowledge_time <= as_of` (availability gate), and a split's price multiplier is *applied* only to bars strictly before its `ex_date` (application gate).

**Splits adjust the price series; dividends do not.** Dividends are **decoupled cash events** credited at `pay_date` and never folded into prices — so the real ex-date dividend price drop is left intact, and a dividend becomes visible once known (`knowledge_time <= when`) regardless of whether it has gone ex yet. Same-day actions compound multipliers in a deterministic order. The `action_type` enum generalizes the same table beyond equities (FX redenominations, crypto symbol migrations are PIT events too).

**Code anchors:**
- `packages/alpha-core/src/alpha_core/corporate.py` — `CorporateAction` (frozen; full date taxonomy), `knowledge_time` / `knowledge_is_estimated` properties; validator rejects `announce_date > ex_date`; `ActionType` enum.
- `packages/alpha-data/src/alpha_data/corporate.py` — `known_actions` (availability gate: `knowledge_time <= as_of`), `split_factor` (application gate: `ex_date > bar_date`, product of `1/ratio`), `cash_dividends` (DIVIDEND stream, fails loud on missing amount).
- `packages/alpha-data/src/alpha_data/pit.py` — `PointInTimeReader.as_of` (knowledge-gates then split-adjusts; volume inverse-adjusted) and `dividends_as_of` (knowledge-gated cash dividends for `pay_date` credit).
- Bias guard: the pinned AAPL 4-for-1 split (2020-08-31) test under `tests/bias_guards/`.

## Options Considered

### Option A: two-clock model; dividends as decoupled cash (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Medium — full date taxonomy + two separate gates to maintain |
| Cost | A small per-bar split-factor computation; a separate cash event stream |
| Correctness-risk | Low — visibility and application are independently correct; real ex-date drops preserved |
| Fit | Excellent — generalizes across asset classes via `action_type` |

### Option B: single pre-adjusted total-return price series

| Dimension | Assessment |
|---|---|
| Complexity | Lowest — one adjusted column, no event machinery |
| Cost | None at read time |
| Correctness-risk | High — future actions leak into past prices; ex-date drop is erased; look-ahead by construction |
| Fit | Poor — incompatible with point-in-time honesty |

### Option C: split-adjust only, ignore dividends

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | None |
| Correctness-risk | Medium — total-return understated; income strategies mis-modeled |
| Fit | Poor — silently wrong for any dividend-paying universe |

## Trade-off Analysis

Two clocks cost real complexity — a full date taxonomy and two gates that must never be collapsed — but that complexity is irreducible: the dates genuinely mean different things, and any model that hides the distinction (B, C) is wrong in a way that is invisible until it has corrupted a result. Decoupling dividends from prices is what lets the engine both preserve the true ex-date price move *and* account for income correctly. The fallback `knowledge_time := ex_date` with a `knowledge_is_estimated` flag keeps approximations honest rather than silently optimistic. The cost is paid once, in the data layer; every strategy and backtest inherits correctness for free.

## Consequences

- **Easier:** trusting that no backtest reacts to an action before it was announceable; modeling total return correctly; extending to non-equity lifecycle events (same table, `action_type`).
- **Harder:** ingesting a new source means sourcing the full date taxonomy, not a single "date"; same-day action ordering must stay deterministic and documented.
- **Revisit when:** sources disagree on dates/ratios (the spec's cross-source reconciliation / quarantine step), or when a non-equity action type needs application semantics beyond a price multiplier.
