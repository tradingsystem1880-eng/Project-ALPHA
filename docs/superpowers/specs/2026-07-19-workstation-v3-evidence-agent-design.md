# Design — Workstation v3 evidence ledger and agent interface

**Status:** Approved for implementation  
**Date:** 2026-07-19  
**Authority:** `CLAUDE.md`, ADR-0002, ADR-0015

## Goal

Give Codex durable cross-run and cross-asset context without turning generated prose into truth.
The memory is an append-only evidence ledger whose claims remain reviewable, time-aware, and linked
to exact canonical artifacts.

## Evidence record

Each immutable revision contains:

- claim or negative result;
- project, version, strategy, assets, frozen universe, timeframe, and method;
- market-data cutoff plus separate observation/knowledge timestamp;
- metric/value/unit where applicable;
- exact source run, artifact, field, and row selector;
- counterevidence and contradiction references;
- status `draft`, `corroborated`, `rejected`, or `superseded`;
- human/agent author and parent revision.

Agent-created records always start as `draft`. A later state is a new revision; records are never
overwritten. Negative findings and search-space history are first-class evidence.

As-of queries exclude records or source data unavailable at the requested time. Cross-asset
correlation requires aligned OOS periods, compatible frequency and availability policy, an explicit
frozen universe, and sample count. It is always labeled association, not causation.

## Agent surface

Codex remains the LLM runtime; no provider loop is embedded in the Workstation. Add stable typed
identifiers for projects, stages, runs, artifacts, panels, metrics, and glossary definitions.

Bounded CLI/REST/MCP capabilities include:

- project/version/suite status and safe stage actions;
- paginated/downsampled chart bundles and run comparisons;
- evidence search, draft, review, reject, and supersede;
- an `AgentBrief` containing hypothesis, scope, source/version, exact evidence, allowed action set,
  and required tests.

No API exposes raw SQL, filesystem paths, arbitrary CLI flags, giant Parquet payloads, dynamic
Python, gate bypass, holdout reveal, paper start, or order placement. Canvas information always has
a typed JSON/table representation. Existing MCP tools remain available while new versioned tools
are added.

## Asset Memory

The Workstation surfaces prior compatible findings, failures, regimes, related assets, and cited
correlation artifacts for the active symbol or universe. It never presents uncited agent prose as
research evidence and never uses later evidence in an earlier as-of context.

## Acceptance

- Revision chains, state transitions, source existence, and counterevidence integrity are tested.
- Future-poison tests prove as-of evidence results cannot change when later records are appended.
- MCP/REST parity, pagination, payload limits, path rejection, and authority limits are tested.
- Every agent answer/action can deep-link to typed project/run/artifact evidence.

