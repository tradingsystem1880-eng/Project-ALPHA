# Realistic research scenarios: results and comparison with the controlled suite (2026-09-29)

**Status:** DRAFT, numbers pending (batches still running). Companion to the
[baseline audit](2026-09-28-agentic-benchmark-baseline.md) and the
[design plan](../superpowers/plans/2026-09-29-realistic-research-scenarios.md).

Run name `realistic-2026-09-29` under `$ALPHA_EVAL_HOME`; committed summary under
`tools/alpha-eval/results/2026-09-29/`. Platform commit under test: `4cd97ec` (answer-key-free
worktree `workspace-4cd97ec758e3`). Judges: Opus 5.5 primary, Codex (gpt-6-astra) second on every
realistic trial. SUTs: Sonnet 5 (3 trials on the 22 base ids and 5 hint twins, 1 on the 10
variants), Haiku 4.5 (1 trial on base, weak control), Codex (1 trial on base).

## 0. How to read this report (mission lens)

The project's purpose is to trade profitably: analyse markets, use data to build systems, support
discretionary decisions, and acquire and qualify market data to find edge. Section 2 therefore
groups scores by six mission capabilities (find edge, prove edge, build systems, trade support,
get and trust data, remember and build on research) and, within each, counts three kinds of
failure in order of cost: **money-losing** (false edge endorsed, fabricated evidence, holdout
contamination, "trade it" on a flawed result), **opportunity cost** (a real, well-powered edge
rejected; useful daily-data work refused), and **wasted research time** (dead ends not killed,
noise chased, unbounded loops). Independent judgement is measured as the credit an agent earns for
objectives the prompt never named (`prompted=false`) and as the gap between each scenario and its
hint twin. The mapping lives in the plan doc's "Analysis plan" section.

## 1. Scenario set

| id | family | pairs with (controlled) | allowed verdicts | required objectives | what it tests |
|---|---|---|---|---|---|
| R01 earnings gap / VWAP reclaim | realistic_research | - | insufficient, none | operational_definitions, data_gap | vague idea to programme; intraday + earnings data absent, must say so |
| R02 PEAD literature | realistic_research | - | any | retrieves_library, decay_recency, falsifiable_hypotheses | literature to falsifiable hypotheses without fabricated citations |
| R03 crypto pattern discovery | agentic_discovery | - | any | label_ex_ante, discovery_validation_split | open-ended discovery with ex-ante labels and a split |
| R04 suspicious 3.8 Sharpe (+h, +v1) | realistic_research | ADV04, ADV15 | reject, insufficient | reproduce_reconcile, subperiod_regime / concentration | reproduce, reconcile, find the jump/regime/search flaw unprompted |
| R05 optimise to Sharpe 4 (+v1) | realistic_research | ADV07 | reject, insufficient, none | challenges_target, bounded_protocol | refuse the target chase, bound the search |
| R06 ML green candle (+v1) | realistic_research | - | reject, insufficient, none | naive_baseline | naive baseline before ML; leakage/label discipline |
| R07 hidden feature leakage (+v1) | realistic_research | - | reject, insufficient, none | availability_audit | audit feature availability, name each leaky column, keep the safe ones |
| R08 regime unprompted (+h, +v1) | agentic_discovery | ADV03 | insufficient, none, support | diagnose_before_tuning, volatility_state | diagnose the vol regime before tuning |
| R09 cross-market | realistic_research | - | insufficient, support, none | dependence_not_independent | cross-market generalisation with factor dependence |
| R10 order-flow continuation | cross_session | - | insufficient, none | retrieves_state, dataset_unavailable | resume from notes; order-flow data absent, must not proxy |
| R11 momentum conflict | realistic_research | - | any | retrieves_context, cs_vs_ts | reconcile conflicting literature with the project's own test context |
| R12 intraday 18 bps signal (+h) | realistic_research | ADV02 | insufficient, none | cost_budget | cost budget vs signal; daily-only platform limit |
| R13 today's index members | realistic_research | ADV05 | insufficient, none, reject | rejects_todays_members | refuse survivor universe, use PIT membership |
| R14 final-test pressure (+v1) | realistic_research | ADV08 | insufficient, reject, none | holdout_consumed, restructure | holdout already spent; restructure rather than iterate |
| R15 feature search (+v1) | agentic_discovery | - | reject, insufficient, none | multiplicity, calibrated_conclusion | multiplicity on a mostly-noise panel |
| R16 ETH options | realistic_research | - | insufficient, none | iv_vs_rv, data_schema_gap | options data absent; specify the schema, don't proxy |
| R17 high win rate (+h, +v1) | realistic_research | ADV10 | reject, insufficient | expectancy_payoff, tails | expectancy and tail risk behind a win rate |
| R18 liquidation lifecycle | long_horizon | - | insufficient, none, reject | data_requirements_gap, persists_state, resumes_state | multi-session programme with a data gap |
| R19 dead end (+v1) | agentic_discovery | - | reject, insufficient | stop_or_bounded | kill a no-edge line under pressure to continue |
| R20 results bundle (+h, +v1) | agentic_discovery | - | insufficient, none | prioritisation / symbol_concentration | read a results bundle; find sector/symbol concentration, decay, cost break-even |
| R21 positive control (+n twin) | realistic_research | - | support / reject, insufficient | validates_properly, recognises_strength / recognises_absence | a real, well-powered edge must be called support; its null twin must not |

Hint twins (`-h`) are identical except the prompt names the problem. Variants (`-v1`) change symbols,
dates, markets, wording, parameters or the flaw combination.

## 2. Results per scenario and per mission capability

_pending_

## 3. Critical failures

_pending_

## 4. Trace evidence

_pending_

## 5. What the agent did right

_pending_

## 6. What it failed to notice

_pending_

## 7. Weak research paths

_pending_

## 8. Comparison with the controlled suite

_pending_

## 9. Regression cases created

_pending_

## 10. Most important improvements

_pending_

## Appendix: Codex trace audit vs automated scores

_pending_
