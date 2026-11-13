# Remove the remaining QuantPad code

**Status:** Scoped
**Rough size:** S

## Problem / why

QuantPad is excluded from active and future data-source plans (README), and its Codex MCP
registration was removed. The code remains: `alpha_data.quantpad_archive` (414 lines),
`alpha_data.adapters.quantpad_adapter`, the `alpha quantpad-data` CLI sub-app
(`alpha_cli.quantpad_data_cmds`, 128 lines, still registered in `main.py`) and three unit test
files. Removal was deferred because QuantPad is bound into a ControlStore SQLite CHECK constraint
and the `quantpad_receipt` research dataset kind, ADR-0018/ADR-0023 and SPA models.

## What "done" looks like

Code, CLI registration and tests removed; historical receipts and attribution remain readable
(the dataset kind stays readable for existing rows or is migrated); ADR-0018/0023 get a
superseding note; generated OpenAPI/TypeScript regenerated.

## Dependencies

A ControlStore schema migration decision for `quantpad_receipt`; an ADR update.

## Sources

- [Edge-first Phase A plan, out of scope](../../superpowers/plans/archive/2026-09/2026-09-10-edge-first-phase-a-shorten-the-loop.md)
- [ADR-0018](../../adr/0018-quantpad-external-research-data-boundary.md) and [ADR-0023](../../adr/0023-research-dataset-registration-and-quantpad-lane.md)
- [README: Implemented scope and limits](../../../README.md#implemented-scope-and-limits)
