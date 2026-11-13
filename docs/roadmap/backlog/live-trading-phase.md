# Live trading phase (private, single owner)

**Status:** Scoped
**Rough size:** XL

## Problem / why

The readiness checklist names a definite later phase in which ALPHA trades real capital for its
single owner. Nothing in the tree routes orders to a broker or venue today: paper paths are opt-in
and "no live-capital route ships" (README). The phase is unsized until the venue, instrument family
and limits are chosen.

## What "done" looks like

- A venue/broker adapter behind explicit credential boundaries.
- Order intent and lifecycle with idempotency and basic realistic execution.
- Position, cash and order reconciliation against the venue.
- Risk limits, kill/freeze controls and disconnect/restart recovery.
- Paper/shadow/fault qualification, then a separate limited-capital approval by the owner.

## Dependencies

W17 (whole research process and paper boundary) for paper qualification; W14 for monitoring and
pause/restart; an owner decision on venue, instruments, limits and observation requirements. A new
ADR and threat/risk review (the crypto readiness plan lists live capital as explicitly deferred).

## Sources

- [Checklist: Definite later live trading phase](../../context/feature-readiness-checklist-2026-10-27.md#definite-later-live-trading-phase)
- [Checklist: Explicit exclusions and boundaries](../../context/feature-readiness-checklist-2026-10-27.md#explicit-exclusions-and-boundaries)
- [Checklist W17](../../context/feature-readiness-checklist-2026-10-27.md#w17-qualify-the-whole-research-process-and-paper-boundary)
- [Crypto operational readiness plan, deferral table](../../work/2026-08-30-crypto-operational-readiness/02-plan.md)
- [README: Implemented scope and limits](../../../README.md#implemented-scope-and-limits)
