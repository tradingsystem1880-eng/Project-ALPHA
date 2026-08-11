# Phase R1 — Research Command Center Desk (read plane + workspace)

**Delivery state:** Completed 2026-08-09 and integrated into the fixed Explore/Build screens.
The checklist records the delivered phase; its original desk/Dockview wording is historical. The
TypeScript scorecard twin named below was retired on 2026-08-11 in favor of the sole Python
projection (ADR-0027).

> **For agentic workers:** TDD per `CLAUDE.md`. Authority: spec
> `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md` §1–§2, §5–§6, §10.2,
> §15.6 + ADR-0021. Read the spec sections and ADR before starting. Audit rows: W1, W6, W13, W15.

**Goal:** The research desk becomes the application's front door: a backlog over every research
case, the Cockpit promoted onto a desk, an Evidence Hub with honest empty states, the
HypothesisCard rendering, a `NOT_TESTED` scorecard, and a New Idea action that never asks for
trading rules. Read-only; zero new mutation authority.

**Scope:** one CLI projection, three REST routes, one desk preset, two new panels + Cockpit
extensions, two pure TS models. NOT in scope: Codex tools/panel (R2), data explorer (R3),
literature (R4), any runner, any approval/decision surface, MCP changes (pin stays 48).

**Constraints:** Gate-1 authority unchanged (ADR-0021); web process never opens the research
SQLite (`_research.py` closed-argv seam only); StrictModel `extra='forbid'` + OpenAPI/generated-TS
regeneration; every panel `guarded()`-registered; e2e desk registration + axe zero
serious/critical; native-unit budgets never summed.

## File Map
```
apps/alpha-cli/src/alpha_cli/research_cmds.py          # ADD: `alpha research list --json` (bounded case summaries)
apps/alpha-cli/src/alpha_cli/control_store.py          # ADD: list_research_cases(limit, offset) read query
apps/alpha-cli/src/alpha_cli/research_gate_packet.py   # ADD: hypothesis_card + scorecard projections (pure, from summary+contract)
apps/alpha-web/src/alpha_web/_research.py              # ADD: list/evidence_hub/scorecard seam fns (closed argv, 60s)
apps/alpha-web/src/alpha_web/api/research.py           # ADD: GET /research/cases, /cases/{id}/evidence-hub, /cases/{id}/scorecard
apps/alpha-web/src/alpha_web/api/models.py             # ADD: ResearchCaseSummaryRow, EvidenceHub*, HypothesisCard, ScorecardV1 StrictModels
apps/alpha-web/frontend/src/panels/ResearchBacklog.tsx # CREATE: bucketed backlog serving researchCockpitModel sort/progress
apps/alpha-web/frontend/src/panels/EvidenceHub.tsx     # CREATE: 11-section hub w/ honest empty states
apps/alpha-web/frontend/src/panels/researchScorecardModel.ts (+.test.ts)  # CREATE: pure dimension-state projection
apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx # MODIFY: sticky header + scorecard strip + HypothesisCard section
apps/alpha-web/frontend/src/panels/registry.tsx        # MODIFY: register ResearchBacklog, EvidenceHub (+PANEL_MENU)
apps/alpha-web/frontend/src/layouts/presets.ts         # MODIFY: 7th preset `research` "Research Command Center"; WorkspacePresetId
apps/alpha-web/frontend/src/App.tsx                    # MODIFY (only if needed): New Idea affordance; else palette entry only
apps/alpha-web/frontend/e2e/workstation.spec.ts        # MODIFY: DESKS entry + responseFor() mocks + no-rule-inputs assertion
tests/unit/test_research_cmds.py, test_web_research_projection.py, test_web_contracts.py  # extend
```

## Tasks
- [x] **`ControlStore.list_research_cases`** — failing test first: bounded (limit ≤ 200,
      offset), newest-updated first, returns the exact `research_case_summary` shape per case
      (reuse it; no new composite). Then `alpha research list --json` in `research_cmds.py`.
- [x] **HypothesisCard projection** — pure fn mapping contract fields → card vocabulary
      (spec §5.1 table) with per-field `complete|partial|missing`; test on the canonical D0
      contract fixture. Exposed inside `alpha research status --json` output (additive key).
- [x] **Scorecard projection (Python)** — pure fn (summary + contract + packet-inputs) →
      13 dimension states + recommendation line (spec §10.2); all-`NOT_TESTED` for a fresh case;
      test the derivation table exhaustively. Exposed via `alpha research report --json`
      (additive key) — no new store queries.
- [x] **Web seams + routes** — `_research.list_cases/evidence_hub/scorecard` (closed argv,
      pinned in `test_web_research_projection.py` with exact calls+timeouts); three GET routes
      with StrictModels; 422/404 mapping; **negative test: `/api/research` router exposes no new
      mutation verbs** (assert route methods).
- [x] **Regenerate contracts** — `uv run python scripts/generate_web_openapi.py` +
      `npm run generate:api`; aliases in `src/api/types.ts`; `api.researchCases()/…` in
      `client.ts`.
- [x] **Historical `researchScorecardModel.ts` delivery** — the original TS twin and parity
      fixture shipped in R1, then were deliberately removed during 2026-08-11 hardening. The
      Python readiness/checklist projection is now the sole authority (ADR-0027).
- [x] **ResearchBacklog panel** — serves `sortResearchCases`/`researchCaseBucket`/
      `researchCaseProgress` from the list route; bucket headers via `researchBucketLabel`;
      row click → `setLinked({projectId})`; poll via the `durableJobs.ts` cadence pattern
      (active 5 s / hidden dormant).
- [x] **EvidenceHub panel** — 11 sections (spec §6.2) off the evidence-hub route; every
      pre-D1 section renders `NOT_TESTED`/`Placeholder` honestly; for/against sections
      identical markup/prominence.
- [x] **Cockpit extensions** — sticky header (case · phase · state · responsibility ·
      next_action · scorecard strip · native-unit budgets); HypothesisCard section.
- [x] **Desk + New Idea** — preset `research` per spec §2.1 anchors; New Idea = topbar action on
      the research desk + palette entry opening the existing capture form. e2e asserts the
      capture flow contains **zero** rule/stop/target/parameter inputs.
- [x] **e2e** — DESKS entry {id:'research', label, activePanel}; mock every new endpoint in
      `responseFor()` (typed fixtures); axe + screenshots + dormancy pass.
- [x] **Gate** — full Python gate + frontend gate; commit rebuilt `static/app`; update
      `CLAUDE.md` (desk count, panel list, new commands) in the same change.

## Done = R1 complete
Backlog/Cockpit/EvidenceHub on a Research Command Center desk; scorecard honest at every stage;
New Idea front door with no trading-rule inputs; zero new mutation authority (proved by tests).

**Next:** R2 (Codex desk — context packets + protocol library).
