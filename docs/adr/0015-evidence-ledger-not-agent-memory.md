# ADR-0015: Store cited evidence revisions, not an agent truth database

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** Owner-approved Workstation v3 plan and AI build agents

## Context

Cross-run learning is useful, but uncited chat summaries can leak future knowledge, discard negative
results, and harden speculation into truth. Vector similarity also cannot enforce compatible
universes, data cutoffs, frequencies, or OOS windows.

## Decision

ALPHA stores append-only typed evidence revisions. Every claim or negative result cites exact run
artifacts and separates market-data cutoff from observation time. Agent writes begin as `draft`;
corroboration, rejection, or supersession creates a new revision. As-of reads exclude later
knowledge. Cross-asset correlation requires aligned OOS evidence and is labeled association.

Typed CLI/REST/MCP projections are bounded and never expose raw SQL, paths, arbitrary commands, or
uncited generated text as evidence. No vector database is adopted in v3.

## Options considered

- Chat transcript/vector memory: rejected because provenance and temporal filtering are weak.
- Mutable note documents: rejected because revision and contradiction history are lost.
- Append-only cited ledger: chosen for auditability and deterministic as-of retrieval.

## Consequences

- Easier: evidence-backed agent answers, negative-result memory, contradiction review.
- Harder: claims require precise citations and human/CLI review transitions.
- Revisit: semantic search may be added only as a rebuildable index over the canonical ledger.

