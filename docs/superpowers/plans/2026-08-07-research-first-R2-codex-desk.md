# Phase R2 — Codex Research Desk (context packets + protocol library)

> **For agentic workers:** TDD per `CLAUDE.md`. Authority: spec §3, §14 + ADR-0022. Audit rows:
> W2, W12. Depends on R1 (desk + panels exist).

**Goal:** Codex collaboration becomes structured, recorded, and resumable: content-addressed
context packets visible byte-identically in the UI, a delta brief ("Resume with Codex"), a
Git-owned 13-protocol library with usage hashes, and an append-only notes channel for Codex
commentary that can never masquerade as evidence.

**Scope:** two store tables, protocol library files, CLI commands, +6 MCP tools (pin 48→54, one
conscious update), CodexBench panel, REST read routes for packets/notes/protocols. NOT in scope:
any chat transport, any OpenAI API usage, data-inventory tools (R3), source claims (R4).

**Constraints:** packets assembled inside one read snapshot following `get_agent_brief_context`
(bounded limits, truncation flags, fail-closed point-in-time); canonical-JSON hashing must reuse
the store's existing canonical-JSON convention (see the dual-convention golden tests from the
2026-08-07 audit); notes excluded from `research_gate_packet_inputs` by construction; protocol
content never stored in SQLite.

## File Map
```
apps/alpha-cli/src/alpha_cli/control_store.py     # ADD: research_context_packets + research_case_notes DDL (additive migration v2.x),
                                                  #      build/get/list packet, add/list note methods
apps/alpha-cli/src/alpha_cli/research_cmds.py     # ADD: `alpha research context build|show|list`, `alpha research note add|list`,
                                                  #      `alpha research protocols list --json`
.agents/skills/alpha-research-protocols/          # CREATE: 13 protocol .md files + protocols.json index (id,title,purpose,packet_kind,output_contract)
apps/alpha-mcp/src/alpha_mcp/server.py            # ADD: get_research_brief, build_research_context_packet, get_research_context_packet,
                                                  #      list_research_protocols, get_research_protocol, add_research_note
apps/alpha-mcp/src/alpha_mcp/_control.py, _types.py  # ADD: subprocess wrappers + strict outputs
tests/integration/test_research_mcp.py            # MODIFY: pin 48→54 (same commit as the tools)
apps/alpha-web/src/alpha_web/_research.py, api/research.py, api/models.py  # ADD: GET packets/notes/protocols projections
apps/alpha-web/frontend/src/panels/CodexBench.tsx (+codexBenchModel.ts+.test.ts)  # CREATE
apps/alpha-web/frontend/src/layouts/presets.ts    # MODIFY: CodexBench into the research preset (right, 420)
```

## Tasks
- [ ] **Packet tables + builder** — failing tests first: `cp_<sha256>` id over canonical payload
      bytes; deterministic (same inputs → same id); kinds `asset|research_case|experiment|chart|
      validation|strategy_promotion`; per-kind payload assembled in ONE read snapshot with
      bounded collections + `*_truncated` flags; `protocol_id`/`protocol_content_hash` recorded
      when supplied; append-only (no update/delete paths).
- [ ] **Notes table** — `note_kind ∈ {critique, confounder_review, test_design,
      completeness_review, synthesis}`; `author_kind ∈ {owner, agent}`; optional
      `context_packet_id` FK; **test: `research_gate_packet_inputs` output is byte-identical
      before/after adding notes** (structural evidence exclusion).
- [ ] **Delta brief** — `get_research_brief`: case summary + what changed since the previous
      brief for this project (diff of phase/execution/attempt/decision sequences) + exact
      `next_action`; deterministic given store state; recorded as a `research_case` packet.
- [ ] **Protocol library** — 13 files per spec §14 table, each: purpose, required packet kind,
      method steps (grounded in `alpha-research-scientist`/`alpha-adversarial-reviewer`
      formats), output contract (where the result lands: material answers / notes / claims /
      analysis-plan proposals). `protocols.json` index; CLI list validates index↔files
      consistency (hash per file), fails loud on drift.
- [ ] **CLI commands** — context build/show/list, note add/list, protocols list; `--json`
      everywhere; owner and agent actor paths (`--created-by`).
- [ ] **MCP tools (+6)** — wrappers with strict types; `add_research_note` forces
      `author_kind="agent"`; pin test 48→54 **in the same commit**; negative tests: no
      approve/decide/D2 tool names appear.
- [ ] **REST + CodexBench** — read routes (packets list/get, notes list, protocols list);
      regenerate contracts; CodexBench: packet composer (kind + case → preview exact JSON →
      record → copy, reusing the AgentBrief clipboard pattern), protocol picker (pairs packet
      with protocol text), packet history (byte-identical display), notes stream badged
      "CODEX COMMENTARY — NOT EVIDENCE".
- [ ] **e2e + gates** — mock new endpoints; axe; full Python + frontend gates; `static/app`;
      `CLAUDE.md` + `.codex/config.toml` docs note (no config change needed — same MCP server).

## Done = R2 complete
Every byte Codex receives is a recorded, retrievable packet; a new idea starts from the intake
protocol, not an empty prompt; Codex commentary is durable and epistemically fenced; pin = 54.

**Next:** R3 (Data Hub) and/or R4 (Source plane) — independent of each other.
