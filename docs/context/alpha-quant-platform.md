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
| Governed research and study composition | [Synthesis](../../research/00-SYNTHESIS.md), historical starting point; dedicated study research report: none identified | [Research cases](../adr/0019-governed-research-cases-before-strategy-development.md); [D1 admission](../adr/0025-empirical-d1-research-runner-admission.md); [D2 authority](../adr/0026-d2-confirmation-readiness-gate-promotion-override.md); [study boundary](../adr/0035-generic-study-composition-and-external-capability-adapters.md) | [Research Scientist spec](../superpowers/specs/2026-08-06-research-scientist-program-design.md); [study plan](../superpowers/plans/archive/2026-08/2026-08-21-generic-study-composition.md); [D2 confirmation plan](../superpowers/plans/archive/2026-08/2026-08-07-research-first-R6-confirmation-promotion.md) | [Research CLI](../../apps/alpha-cli/src/alpha_cli/research_cmds.py); [control store](../../apps/alpha-cli/src/alpha_cli/control_store.py); [study package](../../packages/alpha-study/); [gate watermark checks](../../tests/integration/test_research_gate_watermark_cli.py); [study authority checks](../../tests/unit/study/test_authority.py); [D2 executor](../../apps/alpha-cli/src/alpha_cli/research_d2.py); [mechanical-classification store checks](../../tests/unit/test_research_control_store.py); [one-shot confirmation CLI checks](../../tests/integration/test_research_cli.py). Watermark checks cover override disclosure, not D2 authority |
| Backtesting and statistical validation | [Engine research](../../research/03-backtesting-engine.md); [statistical research](../../research/04-statistical-validation.md) | [t+1 fills](../adr/0003-t+1-fill-encoding.md); [null model](../adr/0006-two-tier-null-model.md); [run identity](../adr/0013-run-identity-v3-and-causal-artifacts.md); [four-family path risk](../adr/0029-four-family-monte-carlo-validation.md) | [Four-family validation spec](../superpowers/specs/2026-08-12-four-family-monte-carlo-validation.md), path risk only; dedicated randomized-price-null plan/spec: not identified | [Engine package](../../packages/alpha-backtest/); [validation package](../../packages/alpha-validation/); [gauntlet composition](../../apps/alpha-cli/src/alpha_cli/_gauntlet.py); [null-model integration checks](../../tests/integration/test_gauntlet_null_model.py), scoped to parametric selection and tier reporting, not every null model |
| Model candidates and isolated workers | [Strategy/ML research](../../research/06-strategy-encoding-ml.md) | [Forecast facade](../adr/0008-vendored-kronos-and-alpha-forecast-layer.md); [Qlib isolation](../adr/0016-isolated-qlib-worker.md); [candidate governance](../adr/0028-governed-market-state-and-model-candidates.md) | [Qlib worker spec](../superpowers/specs/2026-07-19-workstation-v3-qlib-worker-design.md); [tabular candidate and qualification states](../superpowers/plans/archive/2026-10/2026-10-26-qlib-tabular-wave1.md) | [Forecast package](../../packages/alpha-forecast/); [Qlib worker and checks](../../workers/qlib/README.md); [validated comparison](../../apps/alpha-cli/src/alpha_cli/ml_compare.py); [comparison checks](../../tests/unit/test_ml_compare.py); [real adapter checks](../../workers/qlib/tests/test_tabular.py). Additional inspection is scoped to the local tabular candidate; optional dependencies and scientific/economic acceptance remain separate |
| Workstation and advisory investigations | [Engineering research](../../research/07-architecture-ai-workflow.md), general rationale; dedicated investigation research report: none identified | [Collaboration boundary](../adr/0022-codex-collaboration-surface.md); [local confirmation](../adr/0038-local-confirmation-and-terminal-archive-charts.md) | [Workstation investigations plan](../superpowers/plans/archive/2026-10/2026-10-04-workstation-investigations.md) | [Web module map](../../.claude/rules/alpha-web.md); [frontend guide](../../apps/alpha-web/frontend/README.md); [investigation runbook](../operations/codex-investigations.md); [real-backend journey](../../apps/alpha-web/frontend/e2e/real-backend.spec.ts) |
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

Use the [architecture](../ARCHITECTURE.md) for the package boundaries and runtime flow;
this map does not certify that any linked description is current.

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

[Current packet](../superpowers/plans/archive/2026-10/2026-10-26-w05-research-integration.md) binds the reviewed
PR92 transport prerequisite and W05 UTC/request-budget patch to preserved W11 source.
Use its exact-tree receipts for tested status; original producer review is focused offline only.
Application attempts/body caps are not a network/TLS cap or proof of historical availability.
The missing query/restore, report and navigation handoffs remain separate dependencies.

The [combined Mac qualification](../superpowers/plans/2026-10-26-mac-portability-qualification.md)
consumes the verified native portability repair after preserved W05. Gate and review state must
come from its exact local receipts; producer Linux success is not consumer acceptance.

## Native upstream first — 2026-11-06

Planning direction: prefer pinned upstream Qlib workflows, RD-Agent native loops and
NautilusTrader primitives before writing equivalent internals. Integrate their supported
interfaces into ALPHA; an upstream example is not an ALPHA acceptance receipt. This crosswalk
refines existing W01–W19 work, preserves every acceptance ID and all model/framework breadth,
and creates no replacement roadmap or completion denominator. Prioritize retail-feasible durable
economic mechanisms, crypto/altcoin research and discretionary decision support. Non-HFT
intraday and swing remain in scope; pure HFT is excluded. Neither complexity nor presumed
market inefficiency establishes an edge or profitability. Agentic research and self-healing must
retain attempts and distinguish a same-spec mechanical repair from a changed hypothesis:
the latter is new metered research with its own selection/exposure consequences, not a clean
retry. Neither category confers autonomous trading authority. The canonical Space checklist
is maintained separately; neither it nor the repository checklist mirror is amended here.

Source inspection for this section: main `5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff`.
PR #115 is a separate, unmerged QuantPad documentation correction and is not included here.
The following additional receipts were supplied by the coordinating owner, not rerun here:
Qlib and Nautilus each ran synthetic native demonstrations; combined UI candidate
`9b3f279d43b89199a4e84d8f98fb00ff234fd71d` is unmerged, with 16 public tests, scoped lint,
types/build and both browser views reported passing. RD-Agent CLI is installed in that supplied
environment, but no model backend, spend cap or research loop is configured. None establishes
main integration, real-data evidence, full qualification, paper readiness or trading authority.

Isolated native demonstrations may progress before broad platform acceptance when their own
source, environment and effect boundaries are satisfied. No optional library is a prerequisite
for the working native route, and full Qlib/model coverage is not a prerequisite for a bounded
frozen-rule investigation. Governed admission and scientific acceptance remain separate.
W03/W09/W12/W13 follow-on implementation should use native runtimes with thin ALPHA bindings;
this preserves their requirements rather than renaming them or declaring them complete.

### Duplication inventory and retained integration

| Existing source and observed fact | Upstream-first disposition | ALPHA responsibilities retained | Existing owners |
|---|---|---|---|
| [Alpha158 formulas](../../workers/qlib/src/alpha_qlib_worker/features.py) implement Qlib-style definitions locally. [Official-name check](../../workers/qlib/src/alpha_qlib_worker/real.py) compares feature names, not numerical values. This is demonstrated duplicated feature computation, with semantic equivalence still unproved. | First replacement candidate: pinned native Qlib feature/provider/handler workflow. Compare values, missing data, windows, adjustment conventions and availability before deprecating local formulas. No removal yet. | Immutable ALPHA panels, point-in-time eligibility, universe and label clocks, fold-local transforms, schema/version compatibility and future-poison controls. | W03–W05, W09, W11, W12 |
| [Qlib worker](../../workers/qlib/src/alpha_qlib_worker/real.py) already invokes native Qlib models and recorder; its in-memory dataset and fold orchestration adapt ALPHA contracts. | Prefer the pinned native workflow/recorder and official recipes for future breadth. Treat remaining dataset/orchestration overlap as a comparison candidate, not demonstrated removable duplication. Do not rewrite native estimators. | Isolation, bounded jobs, input/output validation, fit provenance, deterministic identities, prediction timing and canonical replay. Qlib diagnostics do not replace ALPHA validation. | W04, W06, W09–W12, W17 |
| [RD-Agent worker](../../workers/rdagent/README.md) uses real LoopBase/LoopMeta and a pinned import closure; the fixed fixture is not a copied production research loop. | Prefer upstream loop/experiment/runner/feedback/checkpoint interfaces for admitted expansion. Do not build a second scheduler or trial ledger. Installed CLI and synthetic loop coverage do not qualify autonomous operation. | One continuation owner, pre-effect admission, explicit model/spend configuration, irreversible exposure and trial accounting, cancellation, containment, recovery and review authority. | W02–W04, W06–W10, W13, W17 |
| [Engine harness](../../packages/alpha-backtest/src/alpha_backtest/engine.py) uses Nautilus BacktestEngine; [feed](../../packages/alpha-backtest/src/alpha_backtest/feed.py) and [frictions](../../packages/alpha-backtest/src/alpha_backtest/frictions.py) express ALPHA semantics. No separate replacement engine was demonstrated in this inspection. | Reuse pinned Nautilus engine, data/execution adapters and lifecycle primitives. Compare any bespoke wrapper against native capability before adding or retiring it. | Close-t decision/open-t+1 fills, calendars and action clocks, costs, instrument/venue units, accounting, deterministic artifacts, risk controls and paper boundary. A default upstream fill model is not parity. | W03–W05, W10, W11, W14, W17 |
| [CCXT adapter](../../packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py) already delegates exchange access to CCXT. [Tear sheet](../../packages/alpha-validation/src/alpha_validation/tearsheet.py) already uses QuantStats-Lumi at the pandas rendering boundary. | Inspect these installed integrations before adding competing exchange/report libraries. Extend supported native capability only for an evidenced gap. | Provider authority, pagination/gaps, request budgets, source/availability clocks and rights; report units, deterministic output and agreement with the canonical ledger. Neither library grants scientific acceptance. | W05, W14, W18, W19 |

### Migration and acceptance sequence

All new acceptance proposals in this section are **NOT RUN**. Existing acceptance IDs and
statuses remain unchanged; these are implementation choices and evidence proposals for their
existing owners, not a second acceptance ledger.

1. W01–W04: bind the official repository, immutable commit/release, source/lock hashes,
   environment, license/notices and a supported entry point. Inventory exact old symbols and
   proposed native counterparts. Label each as demonstrated duplication, suspected overlap or
   required integration. Absence of a source comparison is not permission to delete.
2. W05/W09/W11/W12: run both paths on the same immutable synthetic fixture with declared units,
   clocks, folds, costs and seeds. Freeze numeric tolerances before comparison; explain any
   intentional difference. Cover boundary/missing-data cases, future poisoning, normalization,
   fit/reload/prediction and t+1 fills as applicable. Reuse the existing T05/T07/T08/T10,
   T12–T16/T24 obligations referenced by the W11 packet, without redefining or marking them met.
3. W06/W08/W09/W13: route native calls through the existing admitted case and accounting owner.
   Test pre-effect budget rejection, every attempted variant, retries/reuse, crash and lost-ack
   recovery, cancellation and checkpoint ownership. Native checkpoints or recorder runs cannot
   silently become ALPHA trial/exposure authority. Keep model backends and spend disabled until
   explicitly configured and admitted; this docs change executes no model calls.
4. W10/W14/W17/W18/W19: preserve controls, claim-specific validation, retained snapshots and
   artifact readers. Reproduce chart/table/ledger values and reopen old artifacts. Test migration
   and backout on disposable state, including interrupted migration and original-reader replay.
   Rollback restores the old supported route without erasing attempted trials or exposure.
5. Only after semantic parity, dependency/license review, migration/backout proof and exact-tree
   qualification plus independent review may the owning slice deprecate a named duplicate.
   Keep the old route until the explicit retirement decision and compatibility obligations are
   satisfied; preserve source history and evidence. No code removal or dependency change occurs
   in this amendment. An upstream capability gap can justify a minimal ALPHA extension.

W07 semantics and methodology routing, W15 catalyst research and W16 options expression remain
full-scope requirements, as do every other W01–W19 package and the declared model variants.
Optional trials are **arch** for a specifically missing statistical primitive, **Docling** for
source-faithful extraction, and **skfolio** for a declared portfolio experiment. They are not
adopted replacements for the gauntlet, evidence store or engine; choose one bounded missing
capability, compare the existing path, measure incremental value and stop on failed or
inconclusive evidence. Review the [dependency/license matrix](../governance/2026-07-19-dependency-license-matrix.md#native-upstream-planning-review--2026-11-06)
for personal noncommercial use and separate code, weights, data and service terms.

### Further optional research candidates

These are proposed capability trials, not installed/adopted packages or proven replacement-safe
paths. Official repositories below identify candidate sources; pin selection, exact license and
dependency review, acceptance evidence and migration remain pending. A source list is not a
claim of complete library/model coverage. Reuse existing installed capabilities first.

| Proposed comparison | Existing boundary and decision before trial |
|---|---|
| [statsmodels](https://github.com/statsmodels/statsmodels) HAC/regression covariance; [arch](https://github.com/bashtage/arch) statistical primitives | W10/W11/W14: inspect current dependencies and statistics, define the estimator, lag/bandwidth and uncertainty convention, and test an independent numerical reference. No blanket gauntlet replacement. |
| [ruptures](https://github.com/deepcharles/ruptures) offline break diagnostics; [STUMPY](https://github.com/stumpy-dev/stumpy) analogue windows | W07/W10/W14: retrospective segmentation is diagnostic; full-series break detection cannot silently become a causal signal. Restrict analogue candidates to information available at the decision, including exclusion windows and normalization. No automated regime/edge-decay verdict. |
| [fredapi](https://github.com/mortada/fredapi) ALFRED vintage access; [sdmx1](https://github.com/khaeru/sdmx) international macro | W05/W15/W19: retain the planned direct FRED/ALFRED source authority. Check vintages, revisions, units, release and ingestion clocks; a vintage date alone is not intraday availability. An SDK is a transport choice, not a new authority or acquisition approval. |
| [NeuralForecast](https://github.com/Nixtla/neuralforecast) / [MLForecast](https://github.com/Nixtla/mlforecast) | W09/W11/W12: optional isolated model-worker comparisons with frozen horizons, folds, budget and fit provenance. Existing PyTorch/Kronos and Qlib paths are present; do not replace them or require these candidates to run the native route. |
| [PaperQA2](https://github.com/Future-House/paper-qa), [GROBID](https://github.com/grobidOrg/grobid), Docling and selective [PyAlex](https://github.com/J535D165/pyalex) patterns | W07/W13/W19: compare exact-source extraction, citation spans and metadata against the current literature path. OpenAlex, Crossref, arXiv metadata and SSRN DOI handling already exist; they are not missing-provider claims. Model-backed synthesis requires separate backend/spend and data-disclosure authority; no external model call occurs here. |

Existing-source comparison starts with the [Kronos facade](../../packages/alpha-forecast/src/alpha_forecast/kronos.py),
[literature metadata](../../workers/literature/src/literature_worker/metadata.py) and
[current literature extraction boundary](../../workers/literature/README.md), including pypdf.
SSRN DOI handling is metadata/version evidence, not verified SSRN full-text acquisition.

OpenBB remains an optional isolated comparison, with provider-specific rights, clocks,
coverage and capability qualification; it cannot silently replace direct-source authority.
QuantPad remains excluded from active/future source plans by the owner decision; the separate
PR #115 documents that correction. Neither candidate discovery nor this amendment acquires
market data, reactivates QuantPad or resolves the blocked canonical checklist transfer.

A supplied external review also suggested Dagster, LangGraph, Langfuse, Perspective, Dockview
and MLflow. These are unverified alternatives, not adopted dependencies. First compare their
claimed gap against ALPHA's existing continuation owner, control/trial records, tracing,
Qlib recorder/storage and UI. Do not introduce a second orchestrator or evaluator by default;
source/license review and a bounded duplication assessment remain pending. This note adds no
prerequisite to the working native route.

Follow the amended [native authority plan](../superpowers/plans/2026-10-26-native-rule-authority.md#native-upstream-first-follow-on--2026-11-06),
[Qlib refit packet](../superpowers/plans/2026-10-26-qlib-w11-refit.md#native-workflow-preference--2026-11-06)
and [Nautilus harness plan](../superpowers/plans/archive/2026-06/2026-06-16-phase-2b-nautilus-run-harness.md#native-engine-reuse--2026-11-06).
Historical plans and delivered receipts remain intact. The supplied demonstrations and this
planning review create no profitability claim, new delivery date or waiver of remaining gates.

The [DeltaTrend workflow proposal](../superpowers/plans/2026-10-26-native-rule-authority.md#deltatrend-workflow-proposal--2026-11-06)
maps description/chapter-level source observations and separately labeled ALPHA research-card,
contract, control and educational-UI proposals to W07/W08/W10/W17/W18. Full spoken transcripts
were not verified; Instagram supports no claim. New acceptance proposals remain NOT RUN.

### Versioned feature correction candidate (2026-11-09)

An explicit feature recipe v2 now reuses pinned Qlib operators for 40 columns across eight
families and all five windows. The other 118 columns and the VWAP proxy remain legacy.
Feature v1/default requests remain unchanged. This is a bounded correction, not completion of
the native feature/provider/handler replacement or whole-Alpha158 parity. See the
[scope and compatibility plan](../superpowers/plans/2026-11-09-alpha158-versioned-correction.md).
Focused synthetic engineering checks do not establish model, provider, economic or scientific
qualification. No historical output is reinterpreted.

### Upstream Alpha158 recipe v3 (2026-11-14)

Opt-in feature recipe v3 computes all 158 Alpha158 columns with upstream Qlib expressions and
operators and normalises folds with upstream `DataHandlerLP` processors (training rows only). A
parity test against upstream's own provider + `Alpha158` handler path shows exact equality for
every column; `VWAP0` uses the disclosed typical-price proxy. V1 stays the default; v1/v2 are
legacy readers. See [ADR-0042](../adr/0042-qlib-worker-delegates-data-layer-to-upstream.md).
