# Data-directory naming migration

**Status:** Idea
**Rough size:** M

## Problem / why

The data directory has two confusing name pairs: `forecast/` (Kronos forecast-evaluation run
directories, `forecast_cmds`) next to `forecasts/` (content-keyed Kronos signal cache,
`_forecast_cache`), and `research/` next to `research_executions/` (`research_execution`).
ADR-0009 records the forecast pair as deliberate. Renaming on-disk layouts needs a migration that
keeps existing runs and receipts readable.

## What "done" looks like

Either clearer names with a migration plus legacy readers, or an explicit decision to keep the
names, recorded in the architecture data-directory table.

## Dependencies

Owner decision; ADR-0009 revisit for the forecast pair; migration tests over existing layouts.

## Sources

- [ADR-0009](../../adr/0009-forecast-leakage-and-tier2-cost-policy.md) (two run-dir namespaces)
- [Architecture](../../ARCHITECTURE.md)
