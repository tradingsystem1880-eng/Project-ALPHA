# Atlas runtime layer (traced execution view)

**Status:** Idea
**Rough size:** L

## Problem / why

Atlas is static analysis only. Its design reserved a `runtime_observation` node kind and trace
provenance so a later OpenTelemetry investigation (user action → frontend → API → CLI → worker →
artifact) is additive. Phase 7 was "deferred by design".

## What "done" looks like

Runtime observations are captured and shown in Atlas, kept separate from static analysis, with
trace/span/execution identifiers on every observed edge.

## Dependencies

An OpenTelemetry (or equivalent) instrumentation decision; Atlas schema already reserves the kind.

## Sources

- [Atlas design plan, §11 Phase 7](../../superpowers/plans/archive/2026-08/2026-08-20-project-alpha-atlas-design.md#11-phase-7-runtime-layer--deferred-by-design)
- [Atlas README](../../../tools/alpha-atlas/README.md)
