# Phase R6 — Confirmation, Readiness Gate, Promotion, UI Enforcement

> **For agentic workers:** TDD per `CLAUDE.md`. Authority: spec §10, §11, §15 + ADR-0026. Audit
> rows: W14, W15, W16, W17. Depends on R5.

**Goal:** The research lifecycle closes end-to-end: one-shot sealed D2 confirmation, a
transparent readiness gate ahead of the owner's decision, automatic lossless carry-forward into
strategy development, and enforced (but owner-overridable, watermarked) anti-premature-
backtesting across the UI.

**Scope:** D2 runner + un-disable of confirmation approval/D2 transitions, edge-validation
checklist + full scorecard wiring, `strategy_promotion` packet + AgentBrief research block,
`research_gate_state` + override CLI + watermark propagation. NOT in scope: research ML (still
reserved), any new MCP tools (pin stays 62), any change to holdout/paper authority.

**Constraints:** D2 is one-shot under the immutable boundary; outcome = mechanical
classification only; decisions stay `actor_kind='human'` CLI; the override is append-only with a
reason, never a boolean; the scorecard has no numeric aggregate; TS↔Python scorecard parity
fixtures mandatory.

## File Map
```
apps/alpha-cli/src/alpha_cli/research_runtime.py (research_d2 section)  # ADD: sealed one-shot D2 executor (frozen family, REGISTERED CONFIRMATORY
                                                                        #      watermark, confirmation checks recomputed)
apps/alpha-cli/src/alpha_cli/research_cmds.py       # MODIFY: `run confirm` live; decision view assembles checklist+scorecard+packet
apps/alpha-cli/src/alpha_cli/control_store.py       # MODIFY: un-disable confirmation approval + D2 transitions (cites ADR-0026);
                                                    #         strategy_promotion packet recorded inside record_research_decision txn;
                                                    #         research_gate_state derivation; override scope event
apps/alpha-cli/src/alpha_cli/project_cmds.py        # ADD: `alpha project override-research-gate --actor --reason`; agent-brief research block
apps/alpha-cli/src/alpha_cli/_artifacts.py / manifest path  # MODIFY: EXPLORATORY / RESEARCH GATE NOT COMPLETED manifest marker for overridden-gate runs
apps/alpha-web/src/alpha_web/api/{research,development}.py, models.py  # MODIFY: scorecard full view, research_gate_state on project projections,
                                                                        #         promotion-packet read
apps/alpha-web/frontend/src/panels/{ResearchCockpit,EvidenceHub}.tsx    # MODIFY: decision tab = checklist + full scorecard + packet + history
apps/alpha-web/frontend/src/panels/{StrategyLab,V3Workbenches,Pipeline}.tsx  # MODIFY: gate-state disabling with reason + case link;
                                                                              #         DevelopmentCenter renders carried-forward research block
apps/alpha-web/frontend/src/panels/{RunBrowser,rundetail}/…             # MODIFY: exploratory-override watermark on rows/detail/tear sheet
apps/alpha-web/frontend/src/panels/ProviderSystem.tsx (or Operations desk surface)  # MODIFY: active overrides listed
```

## Tasks
- [ ] **D2 executor** — failing tests first: requires approved child confirmation contract +
      `authorized` D2 for the exact boundary hash; executes the frozen family once; emits
      REGISTERED-CONFIRMATORY artifacts + `ResearchGateEvidenceV1` with `confirmation_claim`;
      writes `consumed` (or `contaminated` on integrity failure); second launch impossible.
- [ ] **Un-disable (scoped)** — confirmation approval + D2 transitions admitted; every existing
      negative test that should still fail (agent actors, wrong boundary, early CONTRADICTED)
      re-asserted; commit cites ADR-0026.
- [ ] **Checklist + full scorecard** — decision view (CLI `--json` + REST + decision tab):
      14 questions each bound to a finding or `NOT_TESTED`; full 13-dimension scorecard +
      transparent recommendation line; TS↔Python parity fixture (same JSON asserted in vitest and
      pytest).
- [ ] **Promotion packet** — recorded atomically inside the `advance_to_strategy` decision
      transaction (`packet_kind='strategy_promotion'`, content per spec §11); byte-identical
      retrieval via packet tools; **test: AgentBrief for the linked strategy project embeds the
      packet reference and survives `as_of` point-in-time reads**.
- [ ] **`research_gate_state`** — derivation {not_required (grandfathered/legacy), open, passed,
      overridden} on project projections (CLI/REST/MCP `get_project`); tests per state.
- [ ] **Override** — `alpha project override-research-gate` (owner CLI): append-only scope event
      with actor+reason; runs launched under an overridden gate carry the manifest marker;
      RunBrowser/run detail/tear sheet render `EXPLORATORY / RESEARCH GATE NOT COMPLETED`;
      Operations desk lists active overrides. **Test: the marker is visible in ≥3 surfaces.**
- [ ] **UI gating** — StrategyLab/DevelopmentCenter/Pipeline disable strategy-creation and
      optimisation affordances for `open` research-required projects with the reason + case
      link; non-research contexts unaffected; e2e covers both states.
- [ ] **Program acceptance** — the full 2026-08-06 §13 + spec-§17 suite: end-to-end
      capture→…→SUPPORTED→promotion with lossless inheritance; park/reject paths; agent
      authority negatives at MCP+REST; kill-and-resume; honest terminal packets.
- [ ] **Gates** — full Python + frontend gates; `static/app`; `CLAUDE.md` + 2026-08-06 spec
      Gate-3/Gate-6 state updates; ADR-0021..0026 statuses flipped to Accepted where landed.

## Done = R6 complete
Idea → evidence → gate → strategy runs end-to-end under governance: confirmation is one-shot and
mechanical, the gate is multidimensional and honest, promotion is lossless, and premature
backtesting is visible wherever it is chosen.

**Next (optional):** R7 — bounded research ML (`research:ml`, 2026-08-06 spec Gate 5).
