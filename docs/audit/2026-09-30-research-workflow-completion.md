# Research workflow completion and specialist architecture

Status: implementation and verification in progress. No new paired-panel results yet.
Baseline: `e54aa7ab05f48a6add384feeb6dcb98e9541e7df`. Historical Claude results remain retained evidence; new model work is Codex-only.

## Decision

Introduce typed specialist stages on ALPHA's isolated Codex runtime. Defer a PydanticAI transport migration until a paired experiment demonstrates a benefit and the replacement passes isolation acceptance. The observed bottlenecks were missing executable operators, late feasibility checks, and searches that produced rules without measurements. More agents cannot repair those failures by themselves.

Pydantic validates structure and declared constraints; evidence verification and deterministic statistical checks must establish what is true. ALPHA already uses typed dataset references, evidence topology, immutable artifact references, and verified gate packets. Reuse those authorities rather than creating agent-owned copies.

[PydanticAI's multi-agent documentation](https://pydantic.dev/docs/ai/guides/multi-agent-applications/) supports programmatic handoffs; a graph or autonomous swarm is optional. Its [typed output](https://pydantic.dev/docs/ai/core-concepts/output/) and [dependency injection](https://pydantic.dev/docs/ai/core-concepts/dependencies/) are useful composition mechanisms, not research validation. Its [Codex provider](https://pydantic.dev/docs/ai/models/openai-codex/) supports subscription OAuth, including existing CLI credentials, but directly calls the backend. It does not inherit ALPHA's tested CLI filesystem boundary. Do not characterize this option as requiring a separate API key or as preserving the current sandbox automatically. Sources checked 2026-09-30.

## Responsibilities

| Stage | Required evidence | Output | Authority |
|---|---|---|---|
| Research lead | Owner question, prior experiments, operator inventory | Falsifiable target, baseline, bounded experiment and stop rule | Propose and reconcile; no approval |
| Data reviewer | Snapshot hashes, schema, calendar and availability clocks | Data/PIT feasibility, missingness, admissible uses and exact blockers | Read-only |
| Overfitting reviewer | Frozen plan, complete variant ledger, folds and results | Leakage, selection, dependence and conclusion-strength findings | Read-only |
| Economic and market-structure reviewer | Instrument/venue, timing, fills, cost and liquidity evidence | Measured versus assumed economics, implementation limits | Read-only |
| Deterministic controller | Validated contract and existing CLI authority | Execute allowed operator, preserve artifacts, enforce limits | Single writer; cannot grant owner authority |

Start with combined economics/market-structure review. A separate macroeconomic analyst is justified when release vintages, publication lags or cross-market transmission are material to a question. Adding a title without distinct evidence and responsibility increases cost and correlated opinions.

Sequence: feasibility → data checks → baseline and frozen candidate bound → existing CLI execution → evidence-bound specialist reviews → reconciliation → existing research gates. Do not repeatedly request opinions before the first empirical baseline. Reviewers cannot rewrite the experiment they review or approve themselves.

A specialist envelope records schema version, role, case/contract identity, input artifact hashes, claims with evidence selectors, findings, missing evidence, next action and execution status. Validate hash/selector resolution outside the model. Schema-valid prose is not completed research. Whole-case budgets include model invocations, tools, elapsed time and candidate count. Permit at most one schema-repair attempt; preserve failures. Stop on provider failure. Never retry sealed D2 as if it were a transient task. Unknown billing stays unknown.

## Workflow changes and acceptance

- R20 V2 uses XNYS session entry/exit dates and synthetic daily MTM accounting. Mark paths are explicitly synthetic. Daily/monthly/trade outputs must reconcile. Scenario stress is not a fitted parameter grid. Old fixtures are unchanged.
- Weekly classifier answers the single-symbol next-week-close direction question without changing the Qlib contract. Fixed simple indicator features, training-only normalization, regularized logistic classification, majority and momentum baselines, chronological validation/test, and separate next-open economic diagnostics. It is discovery evidence, not admitted confirmation or trading approval.
- R08/R19 require data/operator feasibility and one baseline before variants. Unsupported governed execution must stop with the exact blocked operator and evidence; a blocked run is not a completed performance test. Keep an append-only ledger including failed attempts and inspected variants. No best-in-sample rescue or owner override.
- R21 scoring separates within-dataset signal evidence, a recommendation for further research, and deployability. A positive validation result does not prove executable profit; refusing an untested null does not prove noise rejection.
- Initial paired panel: five questions × baseline/candidate = ten trials, same repaired definitions, runtime/model/effort and limits. Report completed evidence, honest block, methodological failure and infrastructure invalid separately from rubric credit. This small diagnostic panel cannot establish a general model ranking.

## PydanticAI adoption gate

A later transport spike must demonstrate equivalent owner-home/evaluator read denial, immutable exports, isolated tools, provider-failure cleanup, event preservation, deterministic artifact identity and bounded aggregate usage. Then compare task completion and evidence quality per elapsed time/tool/model budget against the existing runtime on identical questions. Adopt only if the benefit exceeds migration and operating complexity. The present work does not claim a production multi-agent runtime exists.

## Calibration observations (not paired capability results)

The new GRNY diagnostic produced 99 test observations: classifier accuracy 0.4040, majority
0.5556, momentum 0.5859. These are one synthetic path and a fixed exploratory partition,
not a market forecast or evidence of a profitable strategy. Evidence hash:
`5d8d4c6ebe249207d17f7e88caf0adf3a9c01cb5e51ccb126494020cc4d394c7`.

On session-correct `realdesk_v2`, both default ORCA/NULA validation calls stopped with incomplete
engine execution (1531/1892 and 1069/1892 sessions). A separately recorded, symmetric 0.95
max-leverage diagnostic completed: ORCA run `0f92db6c11a80207`, FAIL, OOS Sharpe -1.643;
NULA run `4a05422adf3a33f3`, FAIL, OOS Sharpe 0.521. Thus the planted trend process is **not a
validated positive strategy control under this execution contract**. Its inherited scenario name
is not proof of positive empirical evidence. Adjudication must reward accurate interpretation of
actual measurements; no positive-control sensitivity or model ranking may be estimated from this panel.

An initial V2 catalog serialization mistakenly retained an empty hidden canary field. The catalog
integrity test found it; candidate definitions now allow the standard loader to insert the suite
canary. The baseline acquisition had already begun with that empty field. Preserve its original
manifest and trajectories, verify its recorded filesystem preflight and separately scan raw evidence
for the suite canary. The hidden-metadata difference must remain disclosed; retrospective scanning
does not retroactively repair acquisition metadata. User-visible questions/world data are unchanged.

## Review findings and patch queue

| ID | Severity / area | Location | Issue and impact | Fix / status | Source |
|---|---|---|---|---|---|
| RW-01 | High / numerics | weekly_diagnostic.py | Finite prices can produce nonfinite return/scaler; false completion | Derived-value guards and extreme-input tests; awaiting final review | Independent quant review |
| RW-02 | Medium / scientific provenance | weekly_diagnostic.py | Incorrect ESL equation and penalty citation | Correct likelihood/score equations; L2 explicit design; Gneiting–Raftery Brier normalization; fixed | Independent quant review |
| RW-03 | Medium / accounting | results_v2.py | Annualized ratio labelled monthly Sharpe | Rename and disclose serial-dependence limitation; entry-notional costs explicit; fixed | Independent quant review |
| RW-04 | Medium / evidence binding | research_diagnostic_cmds.py | Noncanonical JSON pointers could select unintended evidence | Validate escapes/indexes and reject duplicate object keys; regression tests; awaiting final review | Independent code review |
| RW-05 | Medium / benchmark provenance | workflow_v2.yaml | Empty canary in baseline acquisition metadata | Fix catalog; preserve baseline, separate retrospective scan and disclosure; acquisition limitation remains | Evaluator integrity test |

Residual limits: typed contracts do not execute specialists or certify claims. Diagnostic partitions
are consumable exploratory evidence. Positive control remains an unverified strategy control.

RW-06 (high, scoring): independent review found the R21 allowed-verdict set still excluded a correct reject. The corrected catalog admits evidence-consistent reject and removes the strong-validation presumption. A scorer regression exercises rejection through the deterministic verdict gate. The original acquisition and initial scores remain immutable; a separate calibrated scoring revision reuses unchanged primary judgments.
