# Intraday (1h) equity timeframe

**Status:** Idea
**Rough size:** M

## Problem / why

Edge-first Phase B left the 1h equity timeframe out of scope because of its blast radius across
the engine, runner, point-in-time store and web. The checklist keeps non-HFT intraday and swing
research in scope.

## What "done" looks like

Hourly equity bars flow through acquisition, the PIT store, the engine and the web views with the
same look-ahead guards as daily bars.

## Dependencies

A qualified intraday equity data source (W05).

## Sources

- [Edge-first Phase B plan, out of scope](../../work/2026-09-10-edge-first-phase-b-feed-the-machine/02-plan.md)
- [Checklist: Explicit exclusions and boundaries](../../context/feature-readiness-checklist-2026-10-27.md#explicit-exclusions-and-boundaries)
