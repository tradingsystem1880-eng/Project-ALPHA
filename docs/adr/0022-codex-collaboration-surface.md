# ADR-0022: Codex collaboration surface — context packets, protocol library, AI boundary

**Status:** Proposed
**Date:** 2026-08-07
**Deciders:** Project ALPHA owner and AI build agents

## Context

The research-first redesign requires a dedicated Codex (OpenAI) collaboration surface that is not
a generic chatbot: Codex must receive structured, bounded, visible context and its outputs must
become durable, epistemically-labeled artifacts. Codex is already first-class in the data model
(`ResearchResponsibility = owner | codex`), already attaches to the `alpha` MCP server via
`.codex/config.toml`, and already has two repository skills encoding the research method. What is
missing is recorded context (today the owner pastes ad hoc), a research-case analogue of the
strategy-plane `AgentBrief`, and a reusable protocol library. Claude Code builds the application
but must never be the in-product research or strategy AI.

## Decision

- **AI boundary (permanent product properties).** Codex is the sole in-product research and
  strategy-development AI collaborator, attached through MCP. There is no generic
  "choose your AI provider" abstraction, no OpenAI API key inside the application, no in-app chat
  transport, and no Claude surface in the product.
- **Context packets.** Add append-only, content-addressed `research_context_packets`
  (`cp_<sha256>` of canonical payload; kinds `asset | research_case | experiment | chart |
  validation | strategy_promotion`; optional protocol id + content hash). Packets are assembled
  server-side from authoritative records inside one read snapshot, following the `get_agent_brief`
  bounding pattern. Recording is visibility: the CodexBench panel shows the exact bytes of every
  packet ever built; MCP returns the identical bytes.
- **Delta brief.** `get_research_brief(project_id)` implements the spec-§10 "Resume with Codex"
  packet: what finished since the last owner visit, what changed, what remains, the exact next
  action.
- **Codex outputs.** Commentary (critiques, test designs, syntheses) lands in append-only
  `research_case_notes` with `author_kind='agent'`, badged "Codex commentary — not evidence" and
  structurally excluded from the gate packet's evidence-basis ladder. Literature claims land as
  `draft` source claims (ADR-0024). Empirical results exist only as contract-governed research
  runs. The existing draft-vs-corroborated evidence split and the typed-artifact evidence ladder
  are the sole verification mechanisms — no new trust machinery.
- **Protocol library.** Thirteen research protocols live in Git at
  `.agents/skills/alpha-research-protocols/` with a `protocols.json` index; the control store
  records only usage hashes on packets. Git storage keeps protocol content owner-reviewed and
  prevents agent self-modification.
- **MCP tool budget.** The pinned surface grows only by conscious per-phase pin updates in the
  same commit as the tools: R2 +6 (brief, packet build/get, protocol list/get, note add), R3 +5
  (data inventory), R4 +3 (sources/claims) — 48 → ~62. Every addition is read or draft-write.
  Approval, rejection, decision, D2 transition, D3 reveal, `corroborated` writes, paper, and
  order tools remain absent forever.

## Implementation anchors

- Spec: `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md` §3, §14
- Phase plan: `docs/superpowers/plans/2026-08-07-research-first-R2-codex-desk.md`
- Existing brief pattern: `apps/alpha-cli/src/alpha_cli/project_cmds.py` (`agent-brief`),
  `apps/alpha-cli/src/alpha_cli/control_store.py` (`get_agent_brief_context`)
- Codex registration: `.codex/config.toml`; skills: `.agents/skills/`
- Pin test: `tests/integration/test_research_mcp.py`

## Consequences

- Codex collaboration becomes structured, resumable, and auditable; the owner can always answer
  "what exactly did Codex see, and what did it claim?"
- Unverified agent commentary can never masquerade as project evidence; the ladder and badges
  make epistemic status visible everywhere.
- The MCP surface grows and each growth step is a conscious, pinned, documented decision; the
  authority ceiling does not move.
