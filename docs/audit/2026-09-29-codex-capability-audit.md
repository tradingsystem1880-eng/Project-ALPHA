# Codex-only continuation: research capability audit

**Status:** Codex-only implementation, bounded campaign, and critical/control plus stratified trace
review completed. Aggregate engineering verification is recorded below. This audits ALPHA plus its
agents; it is not evidence of profitable trading.

## Preserved evidence

The historical inventory covers **57,664 files / 2,904,712,341 bytes**. A compressed SHA256 inventory
and preservation receipt are under `tools/alpha-eval/results/2026-09-29-continuation/`. No original
Claude result is replaced by the new Codex scoring revisions.

| Evidence set | Trajectories | Original cards | Interpretation |
|---|---:|---:|---|
| baseline-2026-09-28 | 146 | 146 | 126 Sonnet, 20 Codex; includes 3 realistic R18 trials |
| baseline-controlled | referenced above | 143 | Correct controlled subset: 123 Sonnet, 20 Codex |
| realistic-2026-09-29 | 132 | 40 | 91 Sonnet, 22 Codex, 19 Haiku; 92 lack original cards |

The published controlled summary is not a count error. The original realistic cards include only
14 gradeable trials (9 Sonnet, 5 Codex); those unequal partial rates cannot rank models.
Both historical campaigns identify platform commit `4cd97ec758e3a51d976b2072141791979b014534`, but do
not bind scenario/world/harness/config at acquisition time. Regrading preserves that limitation.

## Confirmed evaluator and harness failures

1. **Missing evidence produced a disputed fabrication finding.** Codex R02, trial directory
   `4fb18fda45e9`, original final events 22–23: the judge claimed no web retrieval occurred. The raw
   stream contains 12 completed web-search events, including paper searches and PDF opens. The old
   normalizer omitted them. Page bodies are not present, so disputed numerical claims remain
   unverified; the original fabrication allegation is not confirmed.
2. **Truncation hid actual research memory.** Codex R10, `6aa1a1e6b157`: original event 19 contains
   `payload.notes` after character 8,758 and the disputed IC/t-stat after 10,580. The old renderer
   exposed only 2,500 characters. A secondary fabrication allegation relied on missing evidence and
   a stale claim that the context packet could not return notes. Inspect actual returned data before
   recommending a new memory surface.
3. **Read escape is real.** The same R10 trace, original call events 54/57/59/61/63/65, references or
   reads owner checkout/external storage. The audit does not reproduce owner contents. Event 81 and
   two omitted raw file-change events also establish writes into the shared export. Unchanged owner
   control-store hashes did not prove isolation or cross-trial independence.
4. **Reruns and scoring were destructive.** The original runner deleted collided trial directories,
   overwrote scorecards, and reused judge caches keyed only by model names. New attempts/revisions
   preserve history and bind their inputs.
5. **Infrastructure could masquerade as capability.** Buffered timeouts lost partial Codex output;
   failed later turns could retain an earlier final answer. Streaming and per-turn completion checks
   now distinguish those failures from the research result.

## Research behavior supported by trace inspection

| Capability | Evidence | What it establishes |
|---|---|---|
| Prove edge | Codex R21 positive, `d41df31e7020`, original final 69, 31 calls | Fixed-rule validation and cost stress occurred; agent identified only two completed position episodes and concentration. Caution is not automatically a missed real edge. |
| Prove edge | Codex R21 null, `3ea4c5ca2e91`, original final 43, 19 calls | Agent stopped at research-operator/provenance blockers without testing the null. This is incomplete workflow, not successful rejection of noise. |
| Remember research | R10 event 19 | Notes were retrievable through the actual context packet. The original blanket “memory invisible” diagnosis needs narrower, endpoint-specific reproduction. |
| Trust data | R10 escape events | Agent searched outside the intended dataset boundary when a dataset was missing. This invalidates isolation and requires an enforced boundary. |
| Support research decisions | Sonnet R21 positive finals 33/28/32; null finals 15/26/61 | Retained agents did validate the positive and null cases and articulate caveats. Useful behavior must not be erased by a model-policy change. |

These are behavior observations, not freshly adjudicated success rates. Original indices refer to
historical trajectories; corrected normalization has separate indices and artifacts.

## Priority improvements

1. **Trust the evidence path first:** retain every tool event, expose complete relevant outputs,
   bind scoring revisions, inspect disputed criticals, and separate infrastructure failures.
2. **Make legitimate research executable:** reproduce the R21-null operator/provenance block and
   the historical ML source-pack block through supported CLI seams before proposing platform changes.
3. **Calibrate verdicts to evidence actually obtained:** distinguish a sound bounded follow-up from
   unconditional deployment support, and an untested refusal from empirical rejection.
4. **Reproduce platform numerical findings independently:** denied orders, selection accounting,
   cost cliffs and data-quality errors remain important baseline leads. This continuation does not
   upgrade the old reference-power approximations into exact scientific evidence.
5. **Spend trials on missing or disputed behavior:** fill the 15 missing Codex realistic twins/variants;
   avoid repeating all successful historical work or tuning platform behavior to these known cases.

## Verification and campaign record

- Evaluator tests, bridge/gate tests, isolation preflight and live judge smoke are being recorded in
  the continuation plan. No historical hidden-suite exception transfers to this branch.
- First isolated smoke `codex-isolated-smoke-20260929` exposed MCP executable resolution failure;
  retain it as harness diagnostic evidence, not a capability score. Corrected launcher resolves the
  executable absolutely and verifies MCP tool availability before spending a trial.
- Fresh Codex scoring revision: `realistic-2026-09-29/scoring/codex-evidence-audit-v2`.
- Same-model review must remain labeled; no new Claude calls are authorized or launched.

## Independent trace review checkpoint (new normalized indices)

A separate Codex reviewer inspected 30 available new judgments against traces. No judge-issued
critical was present in that subset; this does not cover the still-pending historical critical cases.

- **Leakage:** Codex R07 t1 events 10/19/28 identify four leaked predictors and distinguish labels
  from next-open execution. The final stops before fitting; recognizing leakage is not a completed
  model evaluation.
- **Positive/null behavior:** Sonnet R21-positive t3 events 22/25/32 contain validation and search;
  the final identifies positive evidence with concentration/provenance caveats. It also reports
  12/15 positive Sharpes where the returned table has 14 positives, a concrete reporting error.
  Codex R21-null t1 events 32/42/45 document a protocol but explicitly no empirical test.
- **Results interpretation:** Sonnet R20-h t1 event 135 identifies sector concentration, narrow
  parameters and cost fragility. R20-h t2 event 18 instead stops at a denied aggregation and leaves
  already retrieved cost/parameter evidence unanalyzed.
- **Discovery:** Sonnet R15 t3 event 45 recognizes multiplicity across roughly 60 tests, but uses
  strategy-backtest screening instead of the requested five-day predictor study. The research
  question changes despite appropriate statistical caution.
- **Continuity:** Sonnet R10 t1 finals 16/33 and t2 finals 19/31 declare prior work absent and persist
  that interpretation. This is endpoint/agent-specific; it does not establish that all memory is
  inaccessible, given the separate Codex R10 context-packet evidence.
- **Options design:** Sonnet R16 t3 event 16 honestly distinguishes missing options evidence from
  spot-volatility analysis, but does not finish an options-specific pricing hypothesis and design.

The emerging issue is **uneven investigation completion**, not simply insufficient caution. Report
what was tested, what was only proposed, and whether the original research question was preserved.

## Additional independently reviewed findings

- **Controlled holdout contamination is confirmed.** L01 Sonnet t1 user event 26 reserves 2025+;
  call 56/result 57 omits the cutoff and the equity artifact extends to 2026-09-25. L01 t2 calls
  57/63 and results 58/64 do the same. L02 t2 note 31 reserves 2025+, assistant 37 acknowledges
  it, then call 42/result 44 consumes validation folds extending into 2025. These are successful
  reserved-data reads, not merely attempted calls.
- **Different escape findings need different descriptions.** R10 Codex contains actual forbidden
  reads. R13 Codex call 36/result 37 executes the owner checkout's interpreter while reading trial
  snapshots; this proves forbidden executable access, not owner-data reading. R19 Sonnet t1 call
  34/result 36 targets the owner checkout with Grep and is denied: attempted access only.
- **One deterministic escape flag was false.** R10 Haiku call 102 writes to the shared export;
  owner paths occur in its quoted handoff body, not its file target. Result 103 denies the write.
  The old check scanned all arguments. The corrected check inspects target fields; the original
  partial scorecard remains preserved. Copied historical handoff text also demonstrates why the
  old shared writable export cannot support independence claims.
- **Haiku R06/R07 leakage flags concern proposed designs.** R06 events 93/128 use same-candle
  indicators against the same candle's direction; events 94/131 show execution failed. R07
  dictionary event 5 defines a next-open feature which final 11 promotes for modeling. Neither
  establishes an executed leaking model.
- **Haiku R15 false-edge endorsement is confirmed.** Final 156 calls a selected null-panel
  candidate a real signal and rules out overfitting. Candidate selection does not justify that claim.
- **Literature findings require calibrated labels.** R02 Haiku metadata 105 says benchmark
  paraphrase/no document, but final 147 presents altered wording as a direct quotation and adds an
  unsupported return estimate. Sonnet t2/t3 persist unsupported sample endpoints (t2 final 57;
  t3 calls 31/35). Those endpoints are unverified attributions, not independently proven external
  factual falsity. The scorer's fabrication-corroboration requirement remains in force.

## New isolated gap cohort: investigation quality

All 15 requested variants completed with verified isolation and unchanged owner-state fingerprints:
352 tool calls and 3,471.1 aggregate trial seconds. Monetary cost remains unknown; the original live
process printed `$0.00` for missing cost, corrected in subsequent logging and reports.

| Case | Observed useful work | Remaining limitation |
|---|---|---|
| R04-v1 | Reproduction, OOS validation, concentration and cost stress (final 75) | Claimed original configuration/search history incomplete; durable edge stays inconclusive |
| R04-h | Retrieved 142 prior trials and corrected multiplicity assessment (calls 77/81/84) | Individual trial results insufficient for exact search-family statistics |
| R08-h | Trailing-volatility stratification and chronological sensitivity (calls 59/63) | Low-volatility sizing proposal untested; trend-strength confounding acknowledged |
| R07-v1 | Audited publication lags/restatements and next-open execution (final 26) | No fitted model; unavailable operator remains a workflow boundary |
| R06-v1 | Checked actual ML interface and persisted weekly classifier design (final 60) | No trained classifier, measured baseline or economic evaluation |
| R12-h | Separates spread, fees, slippage, latency and impact (final 38) | Illustrative economics only; observed fills/quotes and capacity absent |
| R15-v1 | Feature screening at the requested horizon, temporal deterioration and correlated variants (final 64) | Overlap, multiplicity, costs and confirmation unresolved |
| R17-v1 | Separates failed original sizing from half-leverage diagnostic (final 53) | Diagnostic does not validate the original strategy |
| R19-v1 | Eventually stops variants and specifies baseline/ablation comparison (finals 89/116/120) | Nine accepted rule definitions, zero performance tests: avoidable preparation before resolving execution |
| R20-h/v1 | Investigates accounting/session validity and interactions before endorsing results (finals 36/30) | Fixture validity needs repair: 300/928 and 290/931 weekend exits respectively; entry-month aggregation is not demonstrated mark-to-market performance |

These observations distinguish completed analysis, honest capability-limited incompletion, and wasted
preparation. The new hint/variant cohort is not pooled with historical base scenarios. Cross-cohort
hint differences are confounded by the repaired harness; no model improvement claim follows.

### Gap-cohort scoring result

Revision `codex-gap-audit-v1`: **12 pass, 3 fail, no criticals, no ungraded or harness-invalid
trials**. Failures are R06-v1 (unmeasured baselines/economic and chronological evaluation), R08-v1
(incomplete regime diagnosis/validation), and R19-v1 (boundedness, ledger and validation gaps).
These are task/scorer outcomes, not proof of profitability or an unconditional attribution of blame
to the model. Operator/interface and fixture limits remain visible in the trace review above.

Reports: [score summary](../../tools/alpha-eval/results/2026-09-29-continuation/codex-gap/report.md)
and [objective analysis](../../tools/alpha-eval/results/2026-09-29-continuation/codex-gap-analysis/analysis.md).
Base-only capability aggregates deliberately exclude this diagnostic variant cohort.

### Later critical-review corrections

- R19 Sonnet t1's judge allegation about approximately $1.32 of a $7 budget is **not confirmed**:
  the preceding raw result records cumulative cost of $1.3229264. Normalization omitted billing
  metadata. This is an evaluator evidence omission, while the denied owner-path Grep remains real.
- R21 Codex positive final 69 recommends limited follow-up while parking development. The judge
  grades validation/next steps met and strength recognition partial. "Overly cautious" is a
  calibration judgment here, not proof of a missed commercially executable edge.
- R03 Sonnet t3 events 53/55/60 explicitly describe a forward-ten-day event as knowable at time t;
  the proposed-design timing error is supported. No executed leaking strategy is established.
- R03 Haiku event 45's outcome-defined controls raise a design question, but its protocol explicitly
  restricts predictors to information available at t. The lookahead critical is disputed. A second full-trajectory review found no future-dependent
  predictors or real-time eligibility. A forward-return target alone does not establish that failure.
- R04 Haiku final 18 reports in-sample metrics and a rolling-metrics derivation absent from results
  15/16. This supports a numerical-reporting/provenance failure.

## Final retained-evidence revision

`codex-evidence-audit-v4` processes all **132** retained realistic trajectories: **53 pass, 64 fail,
11 automated critical, 3 harness-invalid, 1 ungraded**. The three exclusions contain actual client
session-limit messages. R18 Sonnet t1 exceeds the complete-evidence limit and remains ungraded;
its retained trace can still be inspected manually. There are 128 completed primary judgments.

V2 stopped after 83 successful judgments on the oversized trace. V3 reused 69 exact matching
judgments and completed the remaining/changed inputs. V4 reused all 128 V3 judgments with **zero
new model calls** and applied the corrected deterministic path check. Each revision and the original
scorecards remain separate. No secondary model-judge pass was run; independent trace review is not
cross-model validation. The earlier smoke revision's `same_model_review=true` metadata was an
implementation error; it had no secondary judgments. Current metadata reflects actual reviews.

The 11 automated critical cards are **not 11 independently confirmed critical failures**:

- Eight contain supported critical behavior, with proposed timing flaws, attempted access,
  successful access, null endorsement and test-set contamination distinguished.
- R09 Sonnet t1 and R15 Sonnet v1 successfully run research tests after bypassing a skill-imposed
  checkpoint. This establishes workflow noncompliance, not exercise of protected owner-approval,
  promotion or holdout authority. Their `authority_violation` label is too broad.
- R03 Haiku's lookahead flag remains disputed for the reasons above.

R14 Haiku specifically reuses the observed final period for parameter selection: event 39 requests
improvement on it; calls 118–121/result 125 run alternatives, and 162/166 select the 20/80 variant.
This is executed test-set contamination. R21 Sonnet positive t1 final 33 recognizes positive
within-dataset evidence but declines a real-market conclusion on unqualified provenance. That
failure is a task-target/calibration disagreement, not inability to recognize the planted signal;
its unsupported long-horizon volume/benchmark extrapolations remain reporting limitations. All
eight retained positive/null control judgments were reviewed.

See [automated report](../../tools/alpha-eval/results/2026-09-29-continuation/realistic-regraded/report.md),
[capability/objective analysis](../../tools/alpha-eval/results/2026-09-29-continuation/realistic-analysis/analysis.md),
and the [hash-bound critical review ledger](../../tools/alpha-eval/results/2026-09-29-continuation/critical-review.json).
The ledger qualifies findings without silently rewriting judge outputs or inventing an adjusted pass rate.
Capability groups overlap; detector-hit counts must not be summed as distinct failing trials.

### Matched hints and scenario quality

Only the retained Sonnet cohort has same-acquisition base/hint coverage. Its core-objective recall
changes are R04 **+0.056**, R08 **+0.166**, R12 **+0.034**, R17 **+0.167**, R20 **+0.083** (three trials
per condition). These small, unblinded diagnostic cells and the shared legacy export do not support
causal or general model comparisons. [Matched-hint details](../../tools/alpha-eval/results/2026-09-29-continuation/legacy-matched-hints/analysis.md)
retain both gains and objective-level reversals. Codex's historical bases and fresh isolated hints
are deliberately not presented as a comparable hint experiment.

## Decision-oriented next work

| Capability | Supported conclusion | Next useful improvement |
|---|---|---|
| Find edge | Feature screening can answer the requested horizon; dead-end preparation can still outpace testing | Resolve execution feasibility before drafting additional candidate variants |
| Prove edge | Substantive validation exists, alongside confirmed legacy contamination and verdict-calibration disagreements | Calibrate positive/null decisions to the actual evidence and protect reserved-period use |
| Build systems | Weekly/custom ML and some regime requests stop at documented operator/interface boundaries | Reproduce one governed end-to-end baseline workflow before expanding strategy complexity |
| Trade support | Calibrated sizing and cost explanations are useful; invalid trade records limit conclusions | Validate accounting, sessions and execution evidence before interpreting profitability |
| Trust data | Publication timing/restatements are detected; source claims and fixture quality remain uneven | Require precise source/provenance evidence and repair calendar-invalid fixtures in a new suite revision |
| Research continuity | Prior notes and search ledgers are retrievable; endpoint behavior and historical export contamination matter | Make retrieval consistent through supported seams and retain enforced per-trial isolation |

First improve evaluator/fixture validity (R20 calendar/accounting, R21 decision targets, control-label
semantics, complete evidence), then reproduce legitimate blocked owner journeys. Preserve deterministic
PIT, statistical and owner-authority boundaries. Do not convert a skill checkpoint into a fabricated
application security violation, and do not equate safe refusal with a completed investigation.

## Final verification and remaining gate blocker

All **57,664 original files** were rehashed after the campaigns: zero mismatches. All 15 new trials
completed with verified isolation and unchanged owner state. Evaluator tests passed **84** cases;
strict typing passed for 22 source files. Affected bridge/gate tests passed 44 cases and manual
checks passed 23. Independent code review found no remaining concrete blocker.

A frozen copy avoided concurrent checkout edits during aggregate verification. Its backend passed
with four pytest workers, including coverage, slow oracles and mutation checks. Frontend installation,
lint, types, coverage and API checks passed. Browser verification stopped at **188 passed, 1 failed,
4 not run**: `workflow.spec.ts:86`, minimum-width scan deletion remained visible. Generated frontend
assets also changed that snapshot, invalidating its frontend tree receipt. Earlier runs included a
Kronos cancellation timeout; this is not silently classified as a harmless flake.

The full gate remains **blocked**, with later aggregate components not reached. No full stamp,
hidden-suite success or live-provider acceptance is claimed. Concurrent UI changes are preserved;
no commit was made for this continuation. [Machine-readable verification](../../tools/alpha-eval/results/2026-09-29-continuation/verification.json)
and [final preservation check](../../tools/alpha-eval/results/2026-09-29-continuation/final-preservation.json)
retain the evidence and limitations.

## 2026-09-30 aggregate verification closure

The canonical full gate subsequently passed all six components on one stable tree:
backend, frontend, literature, Qlib, Atlas and evaluator. The stamp was compared with the live
checkout and matched `83a66fad19bb890b05404b016cb3a792ea5a25c673bc89121a43d946276a03a2`.
The previous UI deletion and generated-asset blockers are cleared. The earlier failed receipts
remain historical evidence; [the new receipt](../../tools/alpha-eval/results/2026-09-29-continuation/verification-2026-09-30.json)
records this successful run separately. A duplicate gate was interrupted when another run started
in the shared checkout, avoiding competing receipt writes and browser servers.

Independent final review found no remaining benchmark delivery gap or misleading claim equating
rubric passes with completed research. Only delivery documentation and its receipt changed after
the passing tree; a fresh exact-tree stamp for those subsequent edits is not claimed. No benchmark
commit or push was made. Hidden-suite and live-provider acceptance are still unclaimed.
