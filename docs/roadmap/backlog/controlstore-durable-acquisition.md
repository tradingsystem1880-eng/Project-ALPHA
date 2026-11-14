# ControlStore-owned durable acquisition journal

**Status:** Idea
**Rough size:** L

## Problem / why

Provider acquisition has bounded, local, per-run controls, but no durable journal: the offline
funding path "does not constitute a durable acquisition journal", and durable acquisition
budgets/recovery are listed as prerequisites before any live funding route. Backfill plans avoid
"inventing durable acquisition quota policy".

## What "done" looks like

Acquisition attempts, budgets and resume state are owned by the ControlStore with crash-safe
recovery, so a provider fetch can be resumed or refused from durable state rather than local
artifacts alone.

## Dependencies

ControlStore schema change (see the control-store split refactor); W02/W05 evidence binding;
owner policy for acquisition budgets.

## Sources

- [Offline funding delivery](../../operations/2026-11-05-offline-funding-delivery.md)
- [Research platform contracts](../../operations/research-platform-contracts.md)
- [Backfill verification budget plan](../../work/archive/2026-11/2026-11-07-backfill-verification-budget/02-plan.md)
- [BUILD-STATUS, 2026-11-05 funding entries](../../BUILD-STATUS.md)
