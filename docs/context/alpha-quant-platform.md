# ALPHA Quant Platform area map

**ALPHA Quant Platform** is the user-adopted platform name. This navigation label does not
expand the existing private, local scope or grant research, paper, broker or order authority.
Start with the [context index](README.md), [architecture](../ARCHITECTURE.md) and
[capability authority matrix](../governance/capability-authority-matrix.md).
Existing capability rows inherit the index's last source-inspected commit. The native row and
validation-dependency section below have the explicitly bounded 2026-10-26 inspection exception.
The native source is now assembled onto bc5; scoped public regressions and cheap checks passed.
The linked current plan/packet records exact identities, final review and remaining blockers.
The broader validation map remains source-inspection evidence only.

## Capability routes

Research reports are historical rationale; current contracts, source and receipts determine
behavior. Each test link identifies a verification location, not a test executed for this map.

| Capability | Research rationale | Decisions | Plan/spec | Code and representative checks |
|---|---|---|---|---|
| Data lineage and point-in-time access | [Market data](../../research/01-free-market-data.md); [storage](../../research/02-storage-layer.md) | [Two clocks](../adr/0004-two-clock-corporate-actions.md); [PIT firewall](../adr/0005-point-in-time-firewall.md); [family authority](../adr/0032-governed-crypto-data-house.md) | [Daily-data hardening spec](../superpowers/specs/2026-08-03-daily-data-ibkr-paper-hardening.md); [provider design and crypto-family amendment](../superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md) | [Data package](../../packages/alpha-data/); [data rules/module map](../../.claude/rules/alpha-data.md); [availability guard](../../tests/bias_guards/test_defillama_availability.py), scoped to DefiLlama (metadata only); [crypto-family contracts](../../packages/alpha-data/src/alpha_data/crypto/contracts.py); [family-authority/quality contract checks](../../tests/unit/test_crypto_contracts.py), not a complete new-provider acceptance suite |
| Governed research and study composition | [Synthesis](../../research/00-SYNTHESIS.md), historical starting point; dedicated study research report: none identified | [Research cases](../adr/0019-governed-research-cases-before-strategy-development.md); [D1 admission](../adr/0025-empirical-d1-research-runner-admission.md); [D2 authority](../adr/0026-d2-confirmation-readiness-gate-promotion-override.md); [study boundary](../adr/0035-generic-study-composition-and-external-capability-adapters.md) | [Research Scientist spec](../superpowers/specs/2026-08-06-research-scientist-program-design.md); [study plan](../superpowers/plans/2026-08-21-generic-study-composition.md); [D2 confirmation plan](../superpowers/plans/2026-08-07-research-first-R6-confirmation-promotion.md) | [Research CLI](../../apps/alpha-cli/src/alpha_cli/research_cmds.py); [control store](../../apps/alpha-cli/src/alpha_cli/control_store.py); [study package](../../packages/alpha-study/); [gate watermark checks](../../tests/integration/test_research_gate_watermark_cli.py); [study authority checks](../../tests/unit/study/test_authority.py); [D2 executor](../../apps/alpha-cli/src/alpha_cli/research_d2.py); [mechanical-classification store checks](../../tests/unit/test_research_control_store.py); [one-shot confirmation CLI checks](../../tests/integration/test_research_cli.py). Watermark checks cover override disclosure, not D2 authority |
| Backtesting and statistical validation | [Engine research](../../research/03-backtesting-engine.md); [statistical research](../../research/04-statistical-validation.md) | [t+1 fills](../adr/0003-t+1-fill-encoding.md); [null model](../adr/0006-two-tier-null-model.md); [run identity](../adr/0013-run-identity-v3-and-causal-artifacts.md); [four-family path risk](../adr/0029-four-family-monte-carlo-validation.md) | [Four-family validation spec](../superpowers/specs/2026-08-12-four-family-monte-carlo-validation.md), path risk only; dedicated randomized-price-null plan/spec: not identified | [Engine package](../../packages/alpha-backtest/); [validation package](../../packages/alpha-validation/); [gauntlet composition](../../apps/alpha-cli/src/alpha_cli/_gauntlet.py); [null-model integration checks](../../tests/integration/test_gauntlet_null_model.py), scoped to parametric selection and tier reporting, not every null model |
| Model candidates and isolated workers | [Strategy/ML research](../../research/06-strategy-encoding-ml.md) | [Forecast facade](../adr/0008-vendored-kronos-and-alpha-forecast-layer.md); [Qlib isolation](../adr/0016-isolated-qlib-worker.md); [candidate governance](../adr/0028-governed-market-state-and-model-candidates.md) | [Qlib worker spec](../superpowers/specs/2026-07-19-workstation-v3-qlib-worker-design.md); [tabular candidate and qualification states](../superpowers/plans/2026-10-26-qlib-tabular-wave1.md) | [Forecast package](../../packages/alpha-forecast/); [Qlib worker and checks](../../workers/qlib/README.md); [validated comparison](../../apps/alpha-cli/src/alpha_cli/ml_compare.py); [comparison checks](../../tests/unit/test_ml_compare.py); [real adapter checks](../../workers/qlib/tests/test_tabular.py). Additional inspection is scoped to the local tabular candidate; optional dependencies and scientific/economic acceptance remain separate |
| Workstation and advisory investigations | [Engineering research](../../research/07-architecture-ai-workflow.md), general rationale; dedicated investigation research report: none identified | [Collaboration boundary](../adr/0022-codex-collaboration-surface.md); [local confirmation](../adr/0038-local-confirmation-and-terminal-archive-charts.md) | [Workstation investigations plan](../superpowers/plans/2026-10-04-workstation-investigations.md) | [Web module map](../../.claude/rules/alpha-web.md); [frontend guide](../../apps/alpha-web/frontend/README.md); [investigation runbook](../operations/codex-investigations.md); [real-backend journey](../../apps/alpha-web/frontend/e2e/real-backend.spec.ts) |
| Separately gated paper operations | [Feeds/paper research](../../research/05-paper-trading-feeds.md), historical rationale | [Operational sessions](../adr/0012-operational-paper-sessions.md); [data/broker boundary](../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md); [readiness](../adr/0031-provider-readiness-and-paper-acceptance-v2.md) | [Provider/paper spec](../superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md) | [CLI module map](../../.claude/rules/alpha-cli.md); [local operations runbook](../operations/README.md); dedicated paper-acceptance test/receipt: not selected or verified in this inspection |
| Closed synthetic native workflow | Fixed engineering reference, no empirical claim | [Owner confirmation](../adr/0038-local-confirmation-and-terminal-archive-charts.md); [study boundary](../adr/0035-generic-study-composition-and-external-capability-adapters.md) | [Current plan, receipts, blockers and resume](../superpowers/plans/2026-10-26-native-rule-authority.md) | [Protocol](../../apps/alpha-cli/src/alpha_cli/_native_rule_protocol.py); [native loop](../../workers/rdagent/native_fixture.py); [canonical replay](../../workers/rdagent/costed_probe.py); [public authority/recovery checks](../../tests/unit/test_native_rule_authority.py). Engineering completion only; real discovery, empirical W08, private engineering suite and other-owner integration remain blocked/unverified. |

## Validation dependencies and open acceptance

[Authoritative planning source IDs and read limits](../superpowers/plans/2026-10-26-native-rule-authority.md#planning-sources)
bind the requirements below; the Library documents are planning authority, not implementation evidence.
Planning labels here mean **Master Library v1 §12 Wxx**, not historical August walkthrough
numbers (that document's W10 means regime testing). This is a lean dependency subset, not the
whole backlog: retain full Qlib framework breadth, all 25 pinned model entries and declared recipes,
full native RD-Agent architecture/recipes, and the other W01–W19 requirements. Existing v1/v2
models and this single frozen synthetic rule do not close that scope. W12 first-tabular adapters,
leakage-safe fit/predict/comparison and related UI/context hooks are separately owned/in progress
in the parent-reported isolated Mac task `01a1779c-ea81-774c-8289-0f464bd39006`; its source and
evidence are uninspected here, with no integration claim. W09 native Experiment/Runner/Feedback
parity and shared artifact-selector/data/horizon compatibility remain explicit handoff requirements,
not implementation in this slice. Full model-zoo scope remains open.

The validation table retains source inspection of the preserved e635e6cb-based candidate
(2026-10-26), supplied by the
read-only mapping receipt at `/workspace/alpha-native-rule-authority-receipts/validation-backlog-map.md`.
It does not establish that linked tests ran or passed. Current executed synthetic native coverage
and failures are linked from the [native handoff](../superpowers/plans/2026-10-26-native-rule-authority.md);
all other acceptance needs fresh scoped evidence. The unavailable eight-document navigation
handoff remains a reconciliation blocker. Use the existing [Monte Carlo guide](../operations/monte-carlo/README.md)
for the four families' explanations; preserve each family separately, with no vote.

| Requirement | Actual code / representative public check | Current status and remaining acceptance | Next Master v1 §12 task |
|---|---|---|---|
| Dependence-aware no-edge nulls and permutations | [MCPT](../../packages/alpha-validation/src/alpha_validation/mcpt.py), [gauntlet](../../apps/alpha-cli/src/alpha_cli/_gauntlet.py); [bar-permutation checks](../../tests/unit/test_bar_permutation.py), [full engine null](../../tests/integration/test_full_engine_null.py) | Return-block, full-engine and OOS bar-permutation source exists. Null/permutation hypothesis tests are not feature importance. Method-specific dependence assumptions and reusable controls/full counterfactual procedure refitting remain to qualify. | W10 controls; W11 full refitting/dependence. |
| IS/OOS chronology, fold refitting and Qlib breadth | [Walk-forward](../../packages/alpha-validation/src/alpha_validation/walkforward.py), [real Qlib worker](../../workers/qlib/src/alpha_qlib_worker/real.py); [walk-forward checks](../../tests/unit/test_walkforward.py), [worker checks](../../workers/qlib/tests/test_real_worker.py) | Fixed rules prime prior history with fresh OOS portfolios. Qlib folds fit models/preprocessing, but publishes `counterfactual_refit=False`; full ML gauntlet/promotion is unqualified. Fit every learned transform/model/sizer inside each null fold and preserve panel/time dependence. | W09 current 0.9.7 parity; W11 refits; W12 separate 0.9.8 migration, all 25 model entries/recipes/full framework. |
| `iid_empirical` path risk | [Path simulator](../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py), [family guide](../operations/monte-carlo/iid-empirical.md); [path checks](../../tests/unit/test_path_montecarlo.py) | Resamples canonical OOS account returns, removing dependence. Link immutable source diagnostics and monitoring; this is path risk, not independent no-edge or untouched confirmation evidence. | W14 diagnostics/monitoring. |
| `regime_switching` path risk | [Path simulator](../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py), [causal Markov guide](../operations/monte-carlo/causal-markov.md); [CLI checks](../../tests/integration/test_monte_carlo_cli.py) | Observed causal two-state volatility Markov bootstrap, **not HMM**. Frozen training/support guards exist; current adequacy and monitoring remain to qualify. Independent asset paths do not establish joint portfolio dependence. | W14 adequacy; W11 joint dependence. |
| `student_t` path risk | [Path simulator](../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py), [Student-t guide](../operations/monte-carlo/student-t.md); [path checks](../../tests/unit/test_path_montecarlo.py) | Fits account log-return location/scale/df and exponentiates. Retain tail/ruin assumptions and immutable configuration. Checklist EX14: finite simulated wealth mean does not prove finite population expected wealth for log-t paths. Distinct from the similarly named randomized-price null option. | W14 tail/ruin and EX14 acceptance. |
| `kronos_synthetic` path risk | [MC CLI](../../apps/alpha-cli/src/alpha_cli/monte_carlo_cmds.py), [Kronos replay guide](../operations/monte-carlo/kronos-replay.md); [CLI checks](../../tests/integration/test_monte_carlo_cli.py) | Frozen context/future timestamps and costed engine replay exist. FakeForecaster tests do not qualify real weights, calibration, pretraining overlap or joint portfolio risk. | W14 exact model/provenance/calibration evidence. |
| Complete search history, budgets and untouched confirmation | [Trial ledger](../../apps/alpha-cli/src/alpha_cli/_optim.py), [D2 boundary](../../apps/alpha-cli/src/alpha_cli/research_d2.py); [ledger checks](../../tests/unit/test_optim_trial_ledger.py), [D2 checks](../../tests/unit/test_research_d2_boundary.py) | Preserve successful/failed/rejected variants and manual choices. Native candidate adds one closed family reservation guard; generic study history remains open. Reserve before effects, link reconciled retries, keep D2 one-shot/D3 restricted. Renaming previously inspected periods does not make them untouched. | W06 shared irreversible exposure; W17 complete investigation/independent confirmation. |
| Controls, diagnosis and regime/execution stresses | [D1 controls](../../apps/alpha-cli/src/alpha_cli/research_d1.py), [scenario stress](../../packages/alpha-validation/src/alpha_validation/scenario.py); [D1 checks](../../tests/unit/test_research_d1_modules.py), [scenario checks](../../tests/unit/test_scenario.py) | Registered matched events/placebos/lead-lag and fixed stream stress exist. Generic native ablation/rival/threshold pipelines and full execution stress remain unqualified. Drift detection grants no automatic refit authority. | W10 governed diagnosis; W11 fold-local selection; W14 regime/execution degradation. |
| Costs and economic capacity | [Canonical engine](../../packages/alpha-backtest/src/alpha_backtest/engine.py), [frictions](../../packages/alpha-backtest/src/alpha_backtest/frictions.py); [friction checks](../../tests/integration/test_frictions.py), [synthetic native checks](../../tests/unit/test_native_rule_authority.py) | Fees and side-aware next-open slippage have source support; the native fixture has independent synthetic arithmetic evidence. Data-backed spread/impact/funding/capacity sensitivity remains open. Compute/job capacity is not trading capacity. | W11 sizing/portfolios; W14 venue-appropriate economics. |
| Paper, shadow and recovery | [Paper acceptance](../../apps/alpha-cli/src/alpha_cli/paper_acceptance.py), [readiness](../../apps/alpha-cli/src/alpha_cli/paper_readiness.py); [acceptance checks](../../tests/unit/test_paper_acceptance_v2.py), [store checks](../../tests/unit/test_paper_store.py) | Typed plans/callback facts/recomputed predicates and recovery source exist. Fresh operational receipts, owner opt-ins, independent confirmation and a separately qualified shadow gate remain required. Elapsed time/what-if previews earn no paper credit. No provider/broker check ran for this map. | W14 operational monitoring; W17 confirmation/paper/recovery boundary. |

The [W11 successor packet](../superpowers/plans/2026-10-26-qlib-w11-refit.md) records the
separate engineering refit scope. Its current [protocol reader](../../apps/alpha-cli/src/alpha_cli/ml_refit.py)
and [invocation-local trace helper](../../workers/qlib/src/alpha_qlib_worker/fit_provenance.py)
have [protocol checks](../../tests/unit/test_ml_refit.py) and
[pure trace checks](../../workers/qlib/tests/test_fit_provenance.py). These links do not claim
completed refit integration or scientific acceptance. Native/W06 source is now materialized and
assembled in the isolated successor. Its existing envelope reservation is not an approved Qlib
component-fit unit, world/reuse ancestry contract or consumer runtime qualification. These
compatibility decisions and the unavailable reviewed statistical source remain prerequisites.
The [worker scopes](../../workers/qlib/tests/test_fit_provenance_scopes.py),
[actual-call hook checks](../../workers/qlib/tests/test_fit_provenance_native.py) and
[frozen fixture harness](../../workers/qlib/tests/refit_harness.py) are the bounded engineering
paths; their final execution/review status is recorded in the dated packet, never inferred here.

## Trace the workflow without granting authority

Use the existing [research flow](../atlas/research-flow.md),
[curated lifecycle definitions](../../architecture/atlas/definitions/research-lifecycle.json)
and [data-lineage definitions](../../architecture/atlas/definitions/data-lineage.json).
Those definitions already carry `last_verified_commit` and provenance; this map does not
refresh their verification metadata or certify generated Atlas freshness.

The [research contracts](../operations/research-platform-contracts.md) and
[bounded workflow](../operations/bounded-research-workflow.md) explain operational constraints.
Research comes before strategy; D1 discovery and one-shot D2 remain governed admissions.
Study projections, model candidates, literature claims and advisory investigations confer no
empirical admission, promotion or execution authority. Path risk is not proof of edge.
For the purposes, assumptions and interpretation of all four retained Monte Carlo families,
read the [four-family Monte Carlo overview](../operations/monte-carlo/README.md).
Provider configuration is not data qualification; paper readiness remains separately gated.

## Historical and external evidence

The [June synthesis](../../research/00-SYNTHESIS.md) contains dated recommendations and scope
assumptions. Read accepted ADRs, current contracts and source before treating any recommendation
as implemented. Plans can describe incomplete or superseded work; consult their status and
[delivery history](../BUILD-STATUS.md), then seek a matching current receipt.

The October 14 archive's 46 files and 296 links are privately verified, but public intake is
pending and the corpus is not in GitHub. See the [intake boundary](README.md#external-research-intake).
This map imports no private archive contents or links and establishes no archive-to-code mapping.

## Verification status and remaining gaps

Last source inspection is recorded in the [index](README.md#source-inspection-and-executed-evidence).
No capability test, live provider check, browser journey or full gate is claimed passed by this map.
Selected checks are representative, not exhaustive capability coverage. Missing research, decision,
plan or test relationships must stay visible until inspected evidence supports a link.
Runtime/provider/private-suite acceptance and fresh aggregate receipts remain separate work.

### W05 integration successor — 2026-10-26

[Current packet](../superpowers/plans/2026-10-26-w05-research-integration.md) binds the reviewed
PR92 transport prerequisite and W05 UTC/request-budget patch to preserved W11 source.
Use its exact-tree receipts for tested status; original producer review is focused offline only.
Application attempts/body caps are not a network/TLS cap or proof of historical availability.
The missing query/restore, report and navigation handoffs remain separate dependencies.

The [combined Mac qualification](../superpowers/plans/2026-10-26-mac-portability-qualification.md)
consumes the verified native portability repair after preserved W05. Gate and review state must
come from its exact local receipts; producer Linux success is not consumer acceptance.
