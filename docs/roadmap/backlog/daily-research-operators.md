# A route for new daily-bar research ideas

**Status:** Idea
**Rough size:** L

## Problem / why

A new daily-bar idea cannot get past triage. `alpha research capture` accepts it, but
`alpha research proposal-options` reports `RESEARCH_OPERATOR_UNAVAILABLE` unless the idea is a
double bottom: the only registered operators are the synthetic SPY 60-minute double bottom, the
Tiingo SPY daily double bottom and the Bybit BTCUSDT crowding reversal. So "close below the
20-day low, rebound over five sessions" stops at stage 01 of the research pipeline with no
governed way forward; the only executable alternative is the discovery-only
`alpha research diagnostic run-plan` baseline, which is never case evidence. Found by the
research-pipeline walk-through on 2026-11-14 (`research/stages/01-idea/CONTEXT.md`).

## What "done" looks like

A reviewed, registered daily event operator (or a small closed family of them) that a daily-bar
idea can bind to through `alpha research draft`, with its own D0 acceptance evidence, bias guards
and the same D1/D2 discipline as the double bottom; or an owner decision that new daily ideas run
only as discovery diagnostics until such an operator exists, written into the research method.

## Dependencies

[D0 generalisation](d0-generalisation.md) (ADR under ADR-0035); a qualified Tiingo daily dataset
for D1 ([offline import](offline-data-import.md) covers only offline testing).

## Sources

- [Research pipeline, stage 01](../../../research/stages/01-idea/CONTEXT.md)
- [Command line research invariants](../../reference/invariants/cli-research.md)
- [ADR-0019](../../adr/0019-governed-research-cases-before-strategy-development.md)
