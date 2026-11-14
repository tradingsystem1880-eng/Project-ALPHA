# Make the weekly mutation sweep pass on main

**Status:** Scoped
**Rough size:** S

## Problem / why

The weekly mutation workflow (`.github/workflows/mutation-weekly.yml`) has failed on every
scheduled run checked on 2026-11-14 (25 October, 1 and 8 November): the "Checkpoint and measure
assigned module" step fails for the `alpha_research` modules. This is the one genuinely unfinished
slice of the closed repository tidy-up programme (triage card 14); the nightly run is green.

## What "done" looks like

Two scheduled weekly runs in a row succeed on main, or the workflow is changed so its failures
name a real surviving mutant rather than a broken step, with the reason recorded.

## Dependencies

The CI rewrite under way in a separate stream; `packages/alpha-research/src` is hash-bound, so
any fix belongs in the workflow or the test harness, never in those bytes.

## Sources

- [Closed tidy-up programme](../../work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md) (slice "Validate and finish weekly mutation workflow")
- [Triage sheet, card 14](../triage-2026-11.md#14-old-clean-up-programmes)
