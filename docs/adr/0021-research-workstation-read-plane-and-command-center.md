# ADR-0021: Research workstation read plane and the Research Command Center desk

**Status:** Accepted (implemented 2026-08-09/10; accepted 2026-08-10)
**Date:** 2026-08-07
**Deciders:** Project ALPHA owner and AI build agents

## Context

Gate 1 of the Research Scientist program deliberately shipped a single-case Research Cockpit with
no case-list route: the 2026-08-06 spec states the REST/Cockpit slice "cannot list all cases,
create source packs, approve, decide, consume D2, or run deep research." That absence bundled two
different things: mutation authority (which must stay owner-only) and read visibility (which the
research-first redesign needs — a backlog, an evidence hub, and a readiness scorecard are read
projections). Meanwhile `researchCockpitModel.ts` already ships the tested backlog/bucket/priority
/chart-board model with no serving endpoint, and the Research Cockpit is reachable only from the
command palette, not from any desk.

## Decision

Split read visibility from mutation authority, and supersede the Gate-1 "no list-all" scope
statement **for read-only projections only**.

- Add read-only research projections: `GET /api/research/cases` (bounded
  `ResearchCaseSummary[]`), `GET /api/research/cases/{id}/evidence-hub`, and
  `GET /api/research/cases/{id}/scorecard`, each backed by a closed-argv subprocess of a new
  `alpha research list --json` / existing status projections. The web process still never opens
  the research database.
- Add a seventh Workstation desk, preset id `research`, display name **Research Command Center**,
  containing `ResearchBacklog` (serving the existing unserved model), the existing
  `ResearchCockpit`, `EvidenceHub`, and (from later phases) `CodexBench` and
  `ResearchDataExplorer`. The **New Idea** action is the desk's primary entry point and contains
  no entry-rule, stop, target, indicator, or optimisation input.
- Mutation authority is unchanged and re-affirmed: approve, reject, decide, revise, D2
  transitions, D3 reveal, pause/resume/cancel, source-pack freezing, and the exploratory-gate
  override remain trusted-local owner CLI operations, absent from MCP, REST, and the Cockpit.
  The `ApprovalBoundary` pattern (print the exact owner CLI command) remains the UI's answer to
  every owner-only action.
- A regression test asserts that the `/api/research` router exposes no mutation verbs beyond the
  existing bounded three (capture, proposal, pilot launch).

## Implementation anchors

- Spec: `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md` §2, §6
- Phase plan: `docs/superpowers/plans/2026-08-07-research-first-R1-command-center.md`
- Unserved model: `apps/alpha-web/frontend/src/panels/researchCockpitModel.ts`
- Router: `apps/alpha-web/src/alpha_web/api/research.py`; seam `apps/alpha-web/src/alpha_web/_research.py`
- Desk presets: `apps/alpha-web/frontend/src/layouts/presets.ts`

## Consequences

- The research backlog, evidence hub, and scorecard become first-class, and the research desk —
  not a strategy form — is the application's front door.
- The Gate-1 scope statement in the 2026-08-06 spec is narrowed, not violated: every mutation
  listed there remains impossible from agent-reachable surfaces, and the change is recorded here
  rather than made silently.
- The read plane grows; each new route carries a strict response model, OpenAPI/generated-TS
  regeneration, and e2e coverage, so the contract pipeline cost is paid per route.
