# Options expression research (W16)

**Status:** Scoped
**Rough size:** L

## Problem / why

Compare no-trade, underlying and options expressions of a frozen thesis. No qualified options
quote, contract or lifecycle simulator exists; underlying replay cannot stand in for derivative
semantics, so the package is blocked on data and a separate simulator.

## What "done" looks like

Options quotes, contracts and lifecycle are captured as qualified snapshots; a separate options
simulator is accepted; a frozen thesis can be compared across no-trade, underlying and options
expressions with the checklist's acceptance evidence.

## Dependencies

Derivative snapshots, separate simulator acceptance and W15 where relevant.

## Sources

- [Checklist W16](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/context/feature-readiness-checklist-2026-10-27.md#w16-add-options-expression-when-data-is-sufficient)
- [Checklist: Conditional data and optional adoption](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/context/feature-readiness-checklist-2026-10-27.md#conditional-data-and-optional-adoption)
