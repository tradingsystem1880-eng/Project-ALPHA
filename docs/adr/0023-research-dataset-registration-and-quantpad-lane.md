# ADR-0023: Research dataset registration and the QuantPad qualification lane

**Status:** Accepted (implemented 2026-08-09/10; accepted 2026-08-10)
**Date:** 2026-08-07
**Deciders:** Project ALPHA owner and AI build agents

## Context

Research-first work needs to know what data exists, whether it is trustworthy, and which exact
bytes a hypothesis was tested on. ALPHA already computes rich inventory and quality facts
(provenance schema v2, receipt-backed quality.json, snapshot manifests, PIT candles with quality
status, provider registry) but exposes none of it to MCP, has no snapshot-list projection at all,
and has no binding between the pure `ResearchDatasetRef` type and physical data. ADR-0018 admits
QuantPad as external research scratch data pending a receipt-backed adapter and qualification
suite. ADR-0020 requires research intraday data to stay permanently `research_only`.

## Decision

- **Inventory read plane.** Add `alpha data snapshots --json` (the one missing CLI projection)
  and five read-only MCP tools wrapping existing projections: `get_data_inventory`,
  `get_data_quality`, `get_data_candles` (bounded PIT preview), `list_snapshots`,
  `get_provider_registry`. All subprocess the CLI with projection-class timeouts; none mutate.
- **Dataset registration.** Add `research_dataset_refs` binding `ResearchDatasetRef` (permanent
  `research_only` scope) to its physical origin — canonical store slice, immutable snapshot, or
  QuantPad `FetchReceipt` — via `alpha research data register|audit`. Fail-closed both ways: no
  receipt/provenance → no registration; no registration → a research contract cannot reference
  the data.
- **Descriptive analytics.** Add pure `alpha_research/descriptives.py` (coverage/gap/calendar
  checks, distributions, seasonality, regime tagging, effective-sample estimates) executed by a
  bounded `alpha research run data-audit` run class whose artifacts are admissible to the
  Evidence Hub data dimension only — data understanding is never hypothesis evidence.
- **QuantPad lane.** Implement the ADR-0018 receipt-backed adapter for bulk research data
  (official SDK/REST only), preserving symbol/schema identity, UTC event and knowledge time,
  request/response hashes, coverage/corrections, then passing the existing
  candidate/quality/quarantine path. Qualified output lands as registered dataset refs — still
  `research_only`, still barred from the canonical store, validation snapshots, strategy
  evidence, final holdout, paper readiness, and order intents. Permanent bulk retention and any
  use beyond private single-operator research remain gated on explicit written QuantPad
  permission.

## Implementation anchors

- Spec: `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md` §8
- Phase plan: `docs/superpowers/plans/2026-08-07-research-first-R3-data-hub.md`
- Pure type: `packages/alpha-research/src/alpha_research/data.py` (`ResearchDatasetRef`)
- Quality gate: `packages/alpha-data/src/alpha_data/pipeline.py`; snapshots:
  `packages/alpha-data/src/alpha_data/snapshot.py`
- Boundary authority: ADR-0018, ADR-0020

## Consequences

- Codex and the owner can finally ask "what data do we have, over what range, with what quality
  flags?" through governed tools, and every research result binds to exact, receipt-backed bytes.
- Data feasibility becomes a real triage step; the scorecard's data dimension is fed by machine
  evidence rather than assumption.
- QuantPad coverage becomes usable for research without weakening Tiingo/CCXT authority, the PIT
  firewall, or any execution boundary.
