# Make the weekly mutation sweep pass on main

**Status:** Scoped
**Rough size:** S

## Problem / why

The weekly mutation workflow (`.github/workflows/mutation-weekly.yml`) failed on every scheduled
run checked on 2026-11-14 (25 October, 1 and 8 November). A full dispatch on 14 November (run
43483950887) passed 259 of 261 jobs; one `alpha_research/rendering.py` fragment ran out of its
5,400-second budget with half its mutants timed out, so the aggregate failed. The cause was
measured: mutmut's default fork mode deadlocks mutants whose tests call Polars (2,983 of 15,066
`alpha_research` mutants were such timeouts). The fix, forkserver isolation plus a complete staged
copy, is in [the task folder](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-11/2026-11-14-mutation-sweep-timeouts/02-plan.md).

## What "done" looks like

Two scheduled weekly runs in a row succeed on main, or the workflow is changed so its failures
name a real surviving mutant rather than a broken step, with the reason recorded. What is left:
watch the first two scheduled runs after the fix merges, then delete this note.

## Dependencies

`packages/alpha-research/src` is hash-bound, so any fix belongs in the workflow or the test
harness, never in those bytes.

## Sources

- [Closed tidy-up programme](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-10/2026-10-08-repository-hygiene/02-plan.md) (slice "Validate and finish weekly mutation workflow")
- [Triage sheet, card 14](../triage-2026-11.md#14-old-clean-up-programmes)
