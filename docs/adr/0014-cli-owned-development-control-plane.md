# ADR-0014: Keep development lifecycle state in a CLI-owned control plane

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** Owner-approved Workstation v3 plan and AI build agents

## Context

Run manifests are immutable analytical evidence, while projects, stages, attempts, jobs, and
holdout status are mutable operational state. Inferring lineage from the newest run or embedding
project timestamps/status into manifests breaks both semantics.

## Decision

`alpha_cli` owns a local SQLite control database outside `RUN_DIRS`. It stores mutable projects,
append-only stage/attempt/holdout/job events, and immutable content-addressed strategy versions and
experiment specs. Run lineage is an external atomic link; completed manifests are untouched.

The web and MCP surfaces use public CLI projections/actions and never query SQLite directly.
Holdout reveal, contamination, candidate freeze, paper launch, and promotion have explicit audited
transitions. All attempted configurations, including failures and rejections, are retained.

## Options considered

- Put project metadata in manifests: rejected because mutable, wall-clock state would alter evidence.
- Keep frontend-local JSON state: rejected because agents/CLI cannot share or audit it reliably.
- CLI-owned SQLite: chosen for transactions, restart safety, zero new runtime dependency, and thin surfaces.

## Consequences

- Easier: durable lineage, restart-safe jobs, holdout governance, multi-surface parity.
- Harder: database migrations and explicit projections.
- Revisit: multi-host/multi-user operation would require a new control-plane ADR.

