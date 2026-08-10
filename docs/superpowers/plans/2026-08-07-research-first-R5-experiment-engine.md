# Phase R5 — Pre-Strategy Experiment Engine (D1 runner + real-data lane)

**Delivery state:** Completed 2026-08-09. The temporary D1 admission flag described below was
retired after ADR-0025/0026 acceptance; phase and evidence-zone governance now enforce admission.

> **For agentic workers:** TDD per `CLAUDE.md`. Authority: spec §9 + ADR-0025 (+2026-08-06 spec
> §7, §13). Audit rows: W7, W8, W9, W10, W11, W14. Depends on R2 + R3 (packets, registered
> datasets). **Historical sequencing:** the temporary D1 admission switch was the final change of
> this phase after every acceptance scenario passed; it was retired after ADR-0025/0026 acceptance.

**Goal:** The phenomenon is tested before any strategy exists: preregistered per-hypothesis
analysis plans execute as durable D1 jobs on registered `research_only` data, emitting typed
`ResearchGateEvidenceV1` + watermarked charts, with budgets, stop rules, falsification families,
and mechanical admission.

**Scope:** contract `analysis_plan` extension, four new pure modules, the D1 runner
(`run deep` → durable `research:event-study` jobs), Gate-4 real-data lane, Evidence Hub
experiment sections live. NOT in scope: confirmation/D2 (R6), research ML (`research:ml` stays
reserved), any MCP additions (pin stays 62; `research_launch` stays pilot-only — deep runs are
owner-launched via CLI in this phase).

**Constraints:** research runs have no orders/fills/sizing/costs (economic magnitude enters only
as the registered hurdle check); every analysis family + grid + multiplicity family frozen at
exploration approval; admission re-verifies mechanically (D0 pattern — producer flags never
authority); semantic seeds; heavyweight capacity via the reserved `research:event-study` kind
(one at a time); all artifacts `research_only`/`EXPLORATORY`/zone-D1 marked and excluded from
strategy surfaces.

## File Map
```
packages/alpha-research/src/alpha_research/conditional_returns.py  # CREATE: conditional forward returns, quantile analysis, diff-in-means/medians
packages/alpha-research/src/alpha_research/stability.py            # CREATE: temporal/regime/subsample stability, rolling effect size
packages/alpha-research/src/alpha_research/ic.py                   # CREATE: information coefficient / rank correlation (graded signals)
packages/alpha-research/src/alpha_research/leadlag.py              # CREATE: lead/lag + leakage diagnostics
packages/alpha-research/src/alpha_research/__init__.py             # MODIFY: export new surface
tests/bias_guards/test_research_d1_future_poison.py                # CREATE: future-poison over every new windowed statistic
apps/alpha-cli/src/alpha_cli/research_intake.py                    # MODIFY: analysis_plan draft section (per-hypothesis family selection,
                                                                    #        registered grids, multiplicity families; blanket batteries rejected)
apps/alpha-cli/src/alpha_cli/control_store.py                      # MODIFY: validate analysis_plan at approval; register `research:event-study`
                                                                    #        in _SUITE-equivalent research job admission; D1 attempt admission (FINAL COMMIT)
apps/alpha-cli/src/alpha_cli/research_runtime.py (+research_d1.py) # ADD: D1 executor — plan → analyses → v3 artifacts + ResearchChartData +
                                                                    #        ResearchGateEvidenceV1; checkpointed, budget-debiting, stop-rule-aware
apps/alpha-cli/src/alpha_cli/research_cmds.py                      # MODIFY: `run deep` launches durable jobs (DurableJobLease pattern) instead of failing
apps/alpha-web/frontend/src/panels/EvidenceHub.tsx                 # MODIFY: exploration/experiments/falsification/robustness sections live;
                                                                    #        headline board via headlineResearchCharts
tests/unit + tests/integration                                      # planted/null/confounder fixtures, resume, budget exhaustion, admission re-verification
```

## Tasks
- [x] **Pure modules** — one at a time, failing test first; deterministic, core-only, fail-loud;
      cluster-aware uncertainty via existing bootstrap; every windowed statistic gets a
      bias_guard future-poison test.
- [x] **`analysis_plan` contract extension** — draft section: selected families each with
      registered grid + multiplicity family + rationale line; approval validation rejects
      unregistered families, unbounded grids, and blanket batteries (family count ceiling from
      the funnel budget); HypothesisCard shows the plan.
- [x] **D1 executor** — per-analysis: registered dataset → events/features → family fn →
      `ResearchGateEvidenceV1` fields + `ResearchChartData` renders; checkpoint after each
      analysis (`d1:<family>:<n>` execution checkpoints); budget debits in native units; stop
      rules/continuation triggers enforced between analyses; failure → typed attempt + resume
      instruction (the D0 crash-recovery pattern).
- [x] **Durable job wiring** (in-process governed job with heartbeat checkpoints: the deterministic executor makes exact re-execution the resume mechanism, so no subprocess lease is spawned) — `run deep` reserves capacity (`research:event-study`), spawns the
      worker process group under `DurableJobLease.start_for_process`, records
      `active_job_id`; JobMonitor shows it (existing kind-agnostic cards); cancel/resume paths
      tested (kill-and-resume reproduces identical hashes/budgets/next action).
- [x] **Mechanical admission** — store-side re-verification: run identity, zone D1, markers,
      recomputed acceptance-relevant numbers from artifacts; producer pass-flags ignored;
      contaminating rewrites fail closed (the completed-D0 integrity pattern).
- [x] **Acceptance fixtures (phase gate, before the flag)** — planted synthetic pattern
      recovered end-to-end; planted-confounder case rejected; pure-null family stays null after
      Holm accounting; future-poison suite green; budget exhaustion terminates with an honest
      packet; kill-and-resume at every checkpoint.
- [x] **Gate-4 real-data lane** (registered Tiingo-daily fallback loader + acceptance + executor end-to-end; empirical-lifecycle navigation of a daily chart contract awaits its D0 operator generation) — one owner-selected chart contract on ADR-0023-qualified data
      (QuantPad intraday if retention evidence lands; else the registered Tiingo-daily fallback
      contract); session/DST/equal-duration acceptance per ADR-0020.
- [x] **Evidence Hub live** — exploration/experiments/falsification/robustness sections render
      real findings; headline board ≤6 one-per-category; scorecard dimensions flip from
      NOT_TESTED as evidence lands.
- [x] **FINAL COMMIT: admit D1** — change the hard-disable for `deep_research` attempt admission
      only (confirmation approval + D2 transitions stay disabled); the commit message cites
      ADR-0025 and the passing acceptance suite.
- [x] **Gates** — full Python + frontend gates; `static/app`; `CLAUDE.md` + 2026-08-06 spec
      Gate-3/Gate-4 state-line updates.

## Done = R5 complete
Non-strategy phenomenon testing is real: registered analyses run durably on registered data,
falsifiers execute, selection is ledgered, and admission is mechanical. D2 remains sealed.

**Next:** R6 (confirmation, gate, promotion, UI enforcement).
