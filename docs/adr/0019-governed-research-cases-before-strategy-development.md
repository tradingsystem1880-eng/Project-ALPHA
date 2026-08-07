# ADR-0019: Govern finite research cases before strategy development

**Status:** Accepted
**Date:** 2026-08-06
**Deciders:** Project ALPHA owner and AI build agents

## Context

ALPHA's existing development control plane begins with a concise hypothesis and falsification
criterion, then governs immutable strategy versions, experiments, validation stages, holdout, paper,
and decisions. It does not yet govern how a raw observation becomes a research protocol, how sources
and competing explanations are screened, when Codex asks the owner versus acts, or when exploratory
research must stop.

A prompt-only research workflow is not durable or auditable. Conversely, importing an autonomous
agent framework would duplicate Codex/MCP orchestration, add authority and dependency surfaces, and
still would not make the statistical method valid. A useful research layer must preserve ALPHA's
existing evidence, holdout, and execution boundaries while making the daily owner workflow finite
and resumable.

## Decision

Extend each `StrategyProject` with a governed upstream Research Case. The project remains the single
owner-facing aggregate; research records are additive control-plane records and immutable run
artifacts, not a second project or truth database.

The canonical research phase is:

```text
captured -> triage -> exploration_review -> pilot
pilot -> deep_research | research_decision
deep_research -> confirmation_review | research_decision
confirmation_review -> sealed_confirmation | research_decision
sealed_confirmation -> research_decision -> closed
```

Early `research_decision` is fail-closed: it may record only a non-`SUPPORTED` outcome and a
non-advance disposition while D2 remains sealed. `SUPPORTED` and `advance_to_strategy` require the
approved child confirmation path and one exact D2 consumption.

Execution state (`idle`, `queued`, `running`, `paused`, `blocked`, or `failed`) is orthogonal to the
phase. Every active case exposes one `next_action` and `responsibility` (`codex` or `owner`).
Append-only phase, execution, review, D2, attempt, and decision events make the case resumable.

D0–D3 are evidence zones, not aliases for those phases. D0 is synthetic and makes no market claim.
By default D1 receives the earliest 60%, D2 the next 20%, and D3 the newest 20% of chronologically
ordered eligible date/session/dependency groups. Groups are indivisible and allocated before event
outcomes are viewed; they are not split by row or by observed event count. A different allocation
requires an event-blind owner-approved exploration contract frozen before D1 and may never reduce
D3 below 20%. D1 is the only adaptive exploration zone; D2 may be consumed exactly once under one
immutable boundary hash and one owner-approved child confirmation contract; D3 remains the existing
final strategy holdout and is prohibited to research. A revision returns to `exploration_review`
under a new immutable contract lineage. It may reuse a boundary only when every prior D2 event is
still sealed and never authorized; it cannot reseal or reuse a consumed/contaminated D2.

The D2 boundary hash binds the allocation rule, ordered group membership, shares, chart, data, and
event semantics. It is copied through every D2 state event so a changed boundary cannot inherit
prior authorization. The Gate 1 CLI emits the canonical 60/20/20 commitment only; production
empirical D1/D2 admission remains hard-disabled.

The shipped D0 path is narrower than the future legal state machine: only the exact synthetic
SPY-like 60-minute acceptance fixture is approval-ready. A passing D0 run requires a canonical
hashed raw-measurement acceptance artifact whose detector, null, exact four-observation topology
embargo, and power criteria are mechanically recomputed on admission; manifest pass flags are not
authority. A passing D0 run moves directly to an
owner-owned early disposition because D1 is unavailable; D0 cannot substantiate `CONTRADICTED` or
enter the generic corroborated-evidence ledger.

Codex may autonomously perform bounded triage and approved research, but it asks at most three
material questions in one batch and requires owner action to freeze/amend the protocol, expand
scope/budget, use restricted data, choose the research disposition, reveal a holdout, enter paper,
or promote. It cannot change the primary outcome, event timing, data source, split, search family,
or acceptance threshold after results are visible without a new protocol revision.

The research decision records a scientific outcome
`SUPPORTED|CONTRADICTED|INCONCLUSIVE|INVALID` and a separate owner disposition
`advance_to_strategy|revise|park|reject`. This upstream decision and the Gate 1 terminal
`ResearchGatePacketV1` projection are distinct from the existing post-holdout/paper
`DecisionPacket`. The shipped packet supports D0 and other early-terminal cases and marks empirical
sections `NOT_TESTED` when D1/D2 evidence does not exist. Only `advance_to_strategy` may make the
existing strategy lifecycle ready; it is not evidence that the strategy passed validation.

Store source metadata, thesis/protocols, variants, attempts, and case state in the CLI-owned control
plane. Keep permitted full text in a content-addressed store outside Git; freeze source packs and
curated Markdown projections. Empirical claims still require verified ALPHA run/artifact citations
under ADR-0015. Negative results and rejected sources remain first-class.

Every newly created strategy project carries a research-required governance record. Public
`alpha project create` automatically captures its research case and enters triage, and a governed
strategy version requires an approved confirmation contract plus the owner's
`advance_to_strategy` decision. The schema-v2 migration explicitly grandfathers only projects that
already existed before the program launch. Only the verified migration transaction can create a
`legacy_import` marker, and a pre-existing v1 backup is accepted only when its logical schema-and-row
fingerprint matches the current source database. One SQLite writer lock is held continuously from
before that exact rollback snapshot through schema-v2 publication.

Codex remains the runtime. Repository skills define construct, attack, and synthesize passes. No
embedded provider loop, vector/graph truth database, Hermes runtime, unrestricted generated-code
execution, or self-modifying active skill is adopted.

## Implementation boundary

Gate 0 implements the authoritative design, this ADR, governance records, and repository skills.
The initial Gate 1 slice adds an additive schema-v2 control foundation, atomic restart-idempotent capture and
approval-ready draft materialization, dossier projection, a bounded local CLI D0 pilot, pure D0
and event-study/Holm/chart primitives, six bounded non-owner MCP tools, six matching strict REST
routes, a registered Cockpit for those safe operations, and a content-addressed terminal packet
that cannot upgrade D0 or missing evidence into a market claim. The Cockpit has no list-all/source-pack
workflow and REST cannot approve, decide, reveal/consume D2, run deep research, enter paper, or
construct orders. Gate 1 does not add MCP approval/decision/D2 authority, a source network worker,
qualified real-market data, orchestrated D1/D2 analytical runners, or an autonomous analytical
loop. Skills must not claim those later capabilities exist.

The dossier's canonical generated location is
`data_dir/research/projects/<project_id>/`. At this gate, “owner-only CLI” means a trusted local
operator explicitly invokes the mutation and the actor is recorded; it is not cryptographic
identity or verified physical owner presence. Verified owner-presence authentication for unattended
or multi-user operation is a later hard gate.

Future orchestration remains in `alpha_cli`; `alpha_web` and `alpha_mcp` remain thin bounded
subprocess surfaces. Holdout reveal, paper, and orders remain unavailable to research agents.

## Options considered

- **Prompt/checklist only:** rejected as non-resumable, non-auditable, and easy to skip.
- **Import an external multi-agent/autoresearch runtime:** rejected because it duplicates authority,
  increases supply-chain/credential risk, and does not inherit ALPHA's causal/statistical gates.
- **One governed Research Case upstream of the existing lifecycle:** chosen because it reuses the
  control plane, evidence ledger, durable jobs, owner gates, and thin surfaces.
- **Add every specialist as a persistent agent:** rejected initially. Three internal passes are
  sufficient until a frozen evaluation proves a specialist gap.

## Consequences

- Easier: natural-language intake, bounded autonomy, resumability, negative-knowledge retention,
  explicit owner checkpoints, and a decision-useful research packet.
- Harder: additive migrations, protocol-version/stale semantics, source/legal screening, budget
  enforcement, and more rigorous acceptance fixtures.
- Explicit limitation: good process reduces avoidable false discovery; it cannot guarantee a market
  edge or financial return.
- Revisit: another agent runtime or semantic index requires a measured capability gap and a separate
  evidence-gated ADR.
