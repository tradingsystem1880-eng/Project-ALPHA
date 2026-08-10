# ADR-0020: Keep intraday event research outside daily validation and paper evidence

**Status:** Accepted
**Date:** 2026-08-06
**Deciders:** Project ALPHA owner and AI build agents

## Context

The first Research Scientist acceptance case asks whether the S&P 500 bounces after a double bottom
on a four-hour chart. ALPHA's canonical market-data, point-in-time snapshot, backtest feed, validation
geometry, and stock/ETF paper decisions are currently daily. Treating an ad hoc four-hour dataset as
if it satisfied those contracts would silently weaken timestamp, session, corporate-action,
provider, execution, and holdout guarantees.

Four-hour US-equity bars also have ambiguous construction: the regular XNYS session is 6.5 hours.
Alternating one 240-minute observation and one 150-minute remainder creates unequal observations;
calling both "four-hour bars" is false. A symmetric double-bottom pivot is unavailable until its
right-hand confirmation window has elapsed. Ignoring either fact creates misleading events and
look-ahead.

## Decision

Create a separate research-only intraday data and event-study lane before any generalized intraday
strategy path. Intake must not silently translate "S&P 500 four-hour chart." The owner chooses one
exact chart contract:

- `spy_extended_fixed_4h`: fixed 240-minute SPY extended-hours bars under an explicit anchor;
- `es_fixed_4h`: separately governed fixed 240-minute ES bars with dated-contract, roll, and
  futures-session policy; or
- `spy_rth_60m_four_hour_window`: fixed 60-minute SPY regular-hours bars with a
  240-trading-minute pattern window, explicitly labeled a proxy rather than a literal four-hour
  chart.

All accepted collections use equal-duration observations. `ResearchDatasetRef` fixes provider,
provider symbol, instrument, venue, timeframe, timezone, session, content hash, and permanent
`research_only` scope. `ResearchBar` records timezone-aware start/end/`available_at` and OHLCV.
Mixed 240/150-minute collections, overlaps, dataset mismatches, and knowledge timestamps before bar
end fail closed.

- The Gate 1 acceptance fixture uses synthetic 60-minute proxy bars only and makes no SPY claim.
- The primary double-bottom event cannot fire before the second trough is causally confirmable. A
  neckline-breakout definition is a separate registered variant.
- The owner freezes one endpoint and economic hurdle before real-data research. The study estimates
  a point-in-time executable forward return relative to matched non-event controls, with overlapping
  windows and serial dependence handled explicitly.
- Weekday, trend, volatility, prior drawdown, gap, volume, VIX, breadth, macro-event state, and bar
  construction are candidate confounders. SPY and SPX are same-underlying equivalence checks, not
  independent replications. QQQ, IWM, and DIA are dependence-aware correlated-market
  transportability checks. Genuine replication is reserved for the unchanged contract on
  non-overlapping future data or a defensibly independent data-generating setting. ES requires a
  separate dated-contract/roll/session protocol.

Research intraday input and event-study output cannot enter the canonical daily store, a daily
validation snapshot, strategy promotion evidence, final holdout, paper readiness, or order intent.
QuantPad remains scratch research input under ADR-0018 until receipt, qualification, and written
retention controls are implemented.

A future intraday strategy release requires a separate ADR proving an authoritative and licensed
receipt-backed provider, correction/corporate-action rules, generalized snapshot identity,
point-in-time interval semantics, Nautilus feed/fill parity, intraday split/embargo/null geometry,
realistic costs, and paper acceptance. This ADR grants none of those authorities.

## Implementation boundary

Gate 1 supplies fixed-duration research-only types, a causal detector, evidence topology,
prospective-power and confirmation primitives, and synthetic fixtures. It does not supply a
real-market adapter or evidence, and production empirical D1/D2 admission was unavailable at this
decision point. ADR-0025/0026 later admitted the qualified daily lane; Gate 4
must later supply the qualified real-data slice for one owner-selected chart contract and its
session acceptance suite. This ADR and the synthetic Cockpit projection grant no real-data,
validation, paper, or execution authority.

## Options considered

- **Approximate four hours with existing daily bars:** rejected because it does not test the owner's
  observation.
- **Alternate 240- and 150-minute SPY RTH observations:** rejected because unequal observation
  duration changes the detector population and mislabels the 150-minute remainder.
- **Push arbitrary intraday bars through the daily feed:** rejected because session, mixed-duration,
  availability, validation, and execution semantics would be false.
- **Build a full intraday trading platform first:** rejected as unnecessary scope before the event
  study demonstrates a credible research need.
- **Isolated research lane, then evidence-gated promotion:** chosen because it answers the question
  without weakening daily authority.

## Consequences

- Easier: honest fixed-duration/proxy labeling, causal pivot timing, explicit session construction,
  and a bounded path to later intraday support.
- Harder: research data cannot reuse daily types blindly, and an unavailable licensed provider stops
  the empirical case.
- Explicit limitation: event-study association is not a validated strategy, executable P&L, or
  paper evidence.
