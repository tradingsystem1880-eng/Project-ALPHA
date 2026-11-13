# Design — Workstation v3 evidence ledger and agent interface

**Status:** Implemented; offline release gate passed
**Date:** 2026-07-19
**Implementation reviewed:** 2026-07-19
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

Project scope is temporal too. Every selected version/experiment change appends a
`project_scope_events` record. A point-in-time `AgentBrief` resolves the latest scope selection at
or before its cutoff, then filters stage state, run links, holdout audit, and evidence to that same
cutoff. Missing legacy scope history fails closed before the current pointers' last recorded
mutation rather than exposing a later version, experiment, or holdout result.

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

## Current implementation note — 2026-07-19

The append-only ledger is implemented in `alpha_cli.control_store.ControlStore`, projected by
`evidence_cmds.py`, `alpha_web.api.development`, and the typed MCP control helpers. Source run
citations are accepted only after the v3 manifest and cited artifact hash are verified. If an
evidence record supplies both a strategy version and experiment, the immutable experiment must have
been created from that exact version; revisions revalidate the same lineage. Agent-facing draft
calls force `author_kind=agent`, derive the agent author from the bounded request, and force
`status=draft`; they cannot impersonate a human reviewer or create corroborated truth. As-of reads
apply both source/data cutoff and knowledge-time rules, and immutable revision/counterevidence links
remain external to run manifests.

The same control store appends `project_scope_events` on version and experiment selection.
`get_agent_brief_context` resolves scope, stage/run lineage, and holdout audit from one SQLite read
snapshot at the requested cutoff; the evidence query applies the same cutoff to its own temporal
filters. Later re-selection, stage completion, reveal, or contamination therefore cannot enter an
earlier brief, and pre-migration missing scope history is reported rather than guessed.

The same surface exposes a bounded `AgentBrief`, versioned REST contract metadata, filtered chart
bundles, run comparison, and asset evidence search without raw SQL, runtime Python, filesystem
paths, holdout reveal, or order authority. The 42-tool MCP surface retains the original 12 tools
during deprecation and adds 30 typed v3 tools. Retained action `options` accept only closed,
bounded per-tool compatibility vocabularies; managed model/tokenizer values reject filesystem-like
paths. Run-producing action responses use capped manifest reads and verify every declared v3
artifact before returning data. Compatibility reads and all new resources remain explicitly
bounded.

Primary checks live in `tests/unit/test_control_store.py`,
`tests/bias_guards/test_agent_brief_future_poison.py`,
`tests/integration/test_control_cli.py`, `tests/integration/test_mcp_server.py`, and
`tests/integration/test_web_api_development.py`. The parity, bounded-payload, and OpenAPI gates
passed; exact release counts live in the audit closeout.
