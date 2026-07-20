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

Agent-facing writes cannot select human provenance or a reviewed status: the MCP surface forces an
agent author and `draft`. A source citation is admitted only after the referenced v3 manifest and
artifact hash have been verified, so a mutable or tampered sidecar cannot become ledger evidence.
When both a strategy version and experiment are supplied, the experiment must have been created
from that exact immutable version; the check is repeated for every revision.

AgentBrief time travel does not read today's mutable project pointers. The control plane appends a
`project_scope_events` row whenever the selected strategy version or experiment changes. At an
`as_of` cutoff, one SQLite read snapshot resolves the latest available scope event and filters
stage state, run links, and holdout audit to the same cutoff; evidence search independently applies
that cutoff to its knowledge/data clocks. A legacy database without scope history fails closed for
a cutoff before the current pointers' last recorded mutation instead of leaking later scope.

## Implementation anchors

- `apps/alpha-cli/src/alpha_cli/control_store.py:ControlStore` owns evidence rows, immutable
  revisions, source verification, contradiction links, append-only `project_scope_events`, and the
  point-in-time `get_agent_brief_context` projection.
- `apps/alpha-cli/src/alpha_cli/evidence_cmds.py` is the canonical command surface.
- `apps/alpha-mcp/src/alpha_mcp/server.py` and `_control.py` force bounded agent-draft provenance;
  `apps/alpha-web/src/alpha_web/api/development.py` provides typed owner-facing projections.
- Regression evidence: `tests/unit/test_control_store.py`,
  `tests/bias_guards/test_agent_brief_future_poison.py`,
  `tests/integration/test_control_cli.py`, `tests/integration/test_mcp_server.py`, and
  `tests/integration/test_web_api_development.py`.

## Options considered

- Chat transcript/vector memory: rejected because provenance and temporal filtering are weak.
- Mutable note documents: rejected because revision and contradiction history are lost.
- Append-only cited ledger: chosen for auditability and deterministic as-of retrieval.

## Consequences

- Easier: evidence-backed agent answers, point-in-time scope reconstruction, negative-result
  memory, contradiction review.
- Harder: claims require precise citations and human/CLI review transitions.
- Revisit: semantic search may be added only as a rebuildable index over the canonical ledger.
