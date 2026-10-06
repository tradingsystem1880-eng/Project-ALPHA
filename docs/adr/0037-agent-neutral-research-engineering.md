# ADR-0037: Agent-neutral engineering and reproducible research

Status: Accepted; implemented locally (2026-09-16).

## Context

The owner approved the [agent-neutral refactor plan](../superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md):
thin local engineering guards, supported historical reads and migrations, and screening plus
reproducibility without application-authority expansion. The former Claude-specific per-edit
ceremony and duplicated local/CI steps create maintenance work unrelated to scientific validity.

## Decision

- One gate-step definition serves local checks and CI. Backend, frontend, literature, Qlib and
  Atlas components report exact-tree results; aggregate full PASS requires every required component.
- Thin Git commit checks replace routine per-edit acknowledgments, shell interception and numeric
  protection counts; replacement behavior checks passed and the former hooks are retired.
  Hidden-test isolation, sandbox restrictions, strict
  typing, import boundaries, bias guards and quantitative verification remain load-bearing.
- Generated source discovery provides bounded terminal orientation and optional Atlas views;
  it reads no owner data or hidden tests and confers no runtime authority.
- New exploration plans use the versioned registered-family V2 path. Supported historical plans,
  artifacts and migrations remain readable under their original contracts. Frozen screening
  specifications and replay provenance remain exploratory and cannot authorize D1/D2, promotion,
  paper, broker or orders.
- Engineering attestations never substitute for application owner presence, sealed-share
  authorization, provider receipts, immutable evidence verification or paper opt-ins.

This supersedes only the engineering ceremony in [ADR-0034](0034-agent-operating-system-v2.md).
It does not supersede scientific, data, sandbox or owner-authority controls in other ADRs.

## Consequences and acceptance

The root manual becomes a compact invariant-and-navigation document. Historical prose is retained
as history, not pinned verbatim by tests. Contracts, generated references and behavior checks
replace brittle line/count assertions. The approved plan controls phased implementation;
targeted tests establish local slice verification, while aggregate gate, independent review and
current-tree evidence establish acceptance. All five components passed together on the candidate
tree; the delivery plan records verification and limitations. A changed tree requires a new pass;
this decision does not confer provider, owner-action or trading readiness.
