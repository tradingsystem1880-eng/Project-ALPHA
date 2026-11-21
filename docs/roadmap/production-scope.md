---
owner: status page and roadmap
sources:
  - docs/reference/project/owner-decisions-3.md
verified: b3f783176e95487d
---

# Production-ready scope: the one checklist

Every capability the owner has asked for, discussed or planned, in one place, so nothing is lost
while ALPHA is thinned and rebuilt. ALPHA is production ready when each row below is Working,
shown on a screen, or carries an owner decision that drops it. "Production grade" in the owner's
words is in the [decisions log][grade]; what works today is on [STATUS.md][status]. This file
changes no capability state: the [capability map](capabilities.toml) stays the source for those.
Stages 5 to 9 are in [part 2](production-scope-2.md); stages 10 to 12, the lost-feature check
and the questions put to the owner are in [part 3](production-scope-3.md).

## How to read a row

- **State.** *Working*: run from start to finish through the installed program (often still on
  made-up data). *Unproven*: built, but never run end to end, or shelved, or waiting in an open
  pull request; instructions for the AI that exist only as text stay Unproven until a check
  shows an AI following them. *Missing*: not built. *Rebuild*: removed in the thin-out, to be
  rebuilt slimmer. *Dropped*: dropped by an owner decision once its replacement works.
- **Where.** The package, folder or screen that holds it, or will. "backlog" means an item in
  [the backlog](README.md); "new" means no home exists yet.
- **By.** *Now*: already there. *Path 1, 2, 3*: the golden path that delivers it (below).
  *Later*: after the three paths. *Phase*: the paper, live or Mac phase.
- **Source.** A link to the owner decision, or one of: *private* (the owner's research, kept
  outside git and restated here in plain words only); [status] (the status page);
  [partner], [rd-all], [spine] (owner decisions of 2026-11-15 on the research partner, on using
  everything RD-Agent has with memory first, and on the clean spine, in [volume 3][spine] of the log).
  Rows added by the file-system audit of 2026-11-16 restate private research ideas; their purpose,
  reasoning and home are in the linked [backlog](README.md) notes.

## The three golden paths

Each path runs from a plain-English prompt to a result on a screen, on real free data, and the
old lane it replaces is deleted when it works ([decision][spine]).

| Path | The prompt it must serve | Pipeline stages it proves |
|---|---|---|
| 1. Rule test | "Test this trend rule on these assets" | 1, 2, 4, 5, 6, 7, 8, 10 |
| 2. Chart setup | "Show every match of this setup and what happened after" | 1, 2, 3, 10 |
| 3. Factor mining | "Mine factors on this universe", through RD-Agent with memory | 7, 8, 9, 10 |

Standing scope for every row: swing trading mostly, some intraday, never high-frequency
([rule][no-hft]); any bar size ([rule][any-bar]); large names and coins as well as products
funds cannot trade ([brief][retail]); integrity shown as labels, not refusals; one approval
gate, before paper or live trading ([decision][thin]).

## Where things stand

225 capabilities: 51 working, 67 built but unproven, 105 missing, 1 to rebuild,
1 dropped by decision. Setup short selling and rule-test short selling have separate rows.

| Stage | Working | Unproven | Missing | Rebuild | Dropped |
|---|---|---|---|---|---|
| 1. Idea | 2 | 6 | 9 | 0 | 0 |
| 2. Data and context | 3 | 12 | 10 | 0 | 0 |
| 3. Look before testing | 5 | 5 | 6 | 0 | 0 |
| 4. Backtest | 4 | 3 | 10 | 0 | 0 |
| 5. Overfit tests | 10 | 9 | 3 | 0 | 0 |
| 6. Diagnostics | 8 | 6 | 11 | 0 | 0 |
| 7. Records and memory | 3 | 6 | 9 | 0 | 1 |
| 8. AI partner | 3 | 8 | 5 | 1 | 0 |
| 9. RD-Agent and Qlib engines | 5 | 6 | 16 | 0 | 0 |
| 10. Screens | 1 | 3 | 15 | 0 | 0 |
| 11. Paper and live | 0 | 3 | 4 | 0 | 0 |
| 12. Health and hygiene | 7 | 0 | 7 | 0 | 0 |
| **All** | **51** | **67** | **105** | **1** | **1** |

## 1. Idea

How a question, a chart observation or a paper becomes something testable.

| Capability | State | Where | By | Source |
|---|---|---|---|---|
| Say an idea in plain English to Claude or ChatGPT and the whole pipeline runs it | Unproven | playbook and `alpha test`: three rule kinds | Path 1 | [grade] |
| Any idea may proceed: no stop for an unknown idea type, no approval before a research run | Unproven | `research/` route: text only | Path 1 | [thin] |
| Simple rule language ("close above X and Y"), saved and rerun exactly | Unproven | `alpha-strategies` | Path 1 | [status] |
| Plain rules tested as written, with no hidden sizing or rebalancing defaults | Working | `alpha test`, all-in sizing | Path 1 | [precise] |
| Setup spec: event, context, reference, label, eligibility, trigger, exit, sizing, sessions | Unproven | `alpha-study` setup: daily event, filters, trigger, references; exits parsed, not run | Path 2 | private |
| Four clocks on each idea: signal lookback, decision pace, holding period, execution delay | Missing | idea spec | Path 1 | private |
| Source card and translation card: the original paper beside the adapted rule | Missing | idea folder | Path 1 | private |
| Find papers, screen their claims, tie a claim to its test, keep the PDF | Unproven | `workers/literature` | Later | [papers] |
| Papers feed RD-Agent's proposal step through a thin feeder (its own reader tried first) | Missing | `workers/rdagent` | Path 3 | [papers] |
| One judged factor idea in seven steps with its stored evidence pictures | Unproven | `alpha ledger journey`, [screen design](backlog/research-loop-screen.md) | Path 3 | private |
| Quick recorded first look at many ideas | Working | `alpha scan hypotheses` | Now | [status] |
| Dated log of expectations and catalysts: rumour, fact, interpretation, action kept apart | Missing | new | Later | private |
| The owner's market views logged as dated hypotheses with rival explanations | Missing | idea trail | Path 1 | private |
| The AI frames a loose question: the decision it serves, horizon, baseline, kind of method | Missing | playbook; [practice](backlog/practitioner-research-ideas.md) | Path 1 | private |
| Data that cannot answer a question reported as a gap, never as a failed idea | Missing | `research/` route; [practice](backlog/practitioner-research-ideas.md) | Path 1 | private |
| Verified source library: papers, books and tools checked to exist, grouped by topic, rules of thumb traced to their origin | Missing | `research/` source cards; [note](backlog/rescued-research-ideas.md) | Later | private |
| A paper's edge checked on the stretch after its publication date, apart from the stretch before | Missing | literature claim model; [note](backlog/rescued-research-ideas.md) | Later | private |

## 2. Data and context

Prices, the universe, and the context a trader needs around them.

| Capability | State | Where | By | Source |
|---|---|---|---|---|
| Daily crypto bars: download, resume, freeze into a snapshot, verify | Working | `alpha-data` | Now | [status] |
| Completeness check on downloaded bars | Working | `alpha-data` | Now | [status] |
| Check a whole history and freeze a date range in one step each | Missing | backlog | Path 1 | [status] |
| Daily stock and ETF bars from a free source, frozen and verified | Unproven | `alpha-data` | Path 1 | [free] |
| Any bar size from one minute up; the daily-only refusal removed | Unproven | `alpha-data`, `alpha-backtest`; PRs #185, #189, #194 (merged) | Path 1 | [any-bar] |
| Year length taken from the calendar (crypto trades 365 days), not fixed at 252 | Unproven | `alpha test`; intraday backtests from bar size and session; daily backtests still 252 | Path 1 | [precise] |
| Intraday bars on disk: crypto hourly and 5-minute first, stocks after | Unproven | `data-intraday` folder: BTC/ETH 1h and 5m, SPY/AAPL 5m and 1h (2026-11-14) | Path 2 | [any-bar] |
| Universe as it was on each date, delisted coins included; survivor bias labelled | Missing | `alpha-data` | Path 3 | private |
| Reads see only what was known then; snapshots and receipts never change | Working | `alpha-data` | Now | [precise] |
| Large names and coins, and products funds cannot trade, both in scope | Unproven | `alpha-data` | Path 3 | [retail] |
| One price series per source kept apart automatically; differences shown as a label | Unproven | `alpha-data` | Path 1 | [thin] |
| Benchmarks and sector funds stored for comparison (market, size, sectors, BTC, a basket) | Unproven | `alpha-data` | Path 1 | [partner] |
| Macro series as first published: rates, inflation, jobs, credit, volatility index | Unproven | `alpha-data` `context/` | Later | [partner] |
| Event calendar: central-bank meetings, inflation releases, an earnings-date proxy | Unproven | `alpha context pull-edgar` (8-K item 2.02) | Later | [partner] |
| Crypto context: funding rates, open interest, listings | Unproven | `alpha context pull-binance` | Later | [triage] |
| Company fundamentals by filing date, for value-plus-quant ideas | Missing | backlog; Qlib | Later | private |
| Fund and coin flow data with honest accounting (flows are not asset growth) | Missing | none yet | Later | private |
| News and social text as dated, sourced evidence | Missing | none yet | Later | private |
| Options quotes for payoff and expectation work | Missing | backlog | Later | private |
| Bring in prices or the owner's own trades from a local file | Missing | backlog | Later | [grade] |
| Provider checks and a job list for long downloads | Unproven | `alpha-cli` | Path 1 | [status] |
| Free positioning data: futures positioning and short interest, dated when published | Missing | [register](../reference/project/outside-projects.md#judged-in-the-november-follow-up-studies) | Later | private |
| On-chain and sentiment context as research inputs: network value ratios, exchange flows, dominance, a fear index | Missing | `alpha-data` `context/`; [note](backlog/rescued-research-ideas.md) | Later | private |
| Mechanical data-handling checks: keyed alignment, join counts, time-bin edges, daylight-saving gaps, reshape round trips | Missing | tests; [note](backlog/rescued-test-fixtures.md) | Later | private |

## 3. Look before testing

Seeing what a setup looks like, and what followed, before any rule is fixed.

| Capability | State | Where | By | Source |
|---|---|---|---|---|
| Every match of a setup on the chart, rejected ones greyed, before any rule is fixed | Working | `alpha setup find` contact sheets; the Workstation chart view later | Path 2 | private |
| "Has this happened before?": every earlier stretch shaped like the latest bars, and what followed, on one figure | Working | `alpha lookalike` (STUMPY); no screen yet | Now | private |
| Pattern and indicator detectors that use only bars already seen | Unproven | `alpha-patterns` | Path 2 | [status] |
| Scan many markets for a rule | Unproven | `alpha scan` | Path 2 | [status] |
| What happened after each match (event study) | Working | `alpha setup study` event-study figure; no screen yet | Path 2 | private |
| The same study against random dates and plain market drift | Working | `alpha setup study` (2,000 spaced random-date draws, asset drift) | Path 2 | private |
| Follow-up battery: move size, weekday, trend state, other assets, crypto against stocks | Unproven | `alpha-research` | Path 2 | private |
| Event-based sampling compared with fixed-time sampling | Missing | `alpha-research` | Later | private |
| Descriptive first looks: gaps, distributions, seasonality | Unproven | `alpha-research` | Path 2 | [status] |
| Dense multi-panel price charts, full screen, trade markers, two chart styles | Unproven | `alpha-web` charts | Path 2 | [ui] |
| Near misses and ordinary periods, picked without seeing outcomes, kept beside the matches | Missing | new Setup Lab | Path 2 | private |
| Which came first after each match, target or stop, with still-open trades counted | Working | `alpha setup trade` (stop, target, time exit; same-exit controls) | Path 2 | private |
| The owner's own named chart setups kept as ready-made setup specs, to run on any asset | Missing | `alpha-study` setup specs; from the owner's private research, described here in plain words only | Later | private |
| A daily "what is setting up today" scan over a watchlist, listing the live matches, exportable | Missing | `alpha setup find` over a watchlist; new | Later | private |
| A pattern detector checked against a hand-labelled set of examples before it is trusted | Missing | new Setup Lab; [note](backlog/rescued-test-fixtures.md) | Path 2 | private |
| What winners and losers looked like before entry, beside a random-date control | Missing | `alpha-research`; [note](backlog/rescued-research-ideas.md) | Path 2 | private |

## 4. Backtest

Simulating the idea with costs, against the right comparison.

| Capability | State | Where | By | Source |
|---|---|---|---|---|
| One-asset rule backtest with costs: decide at a close, fill at the next open | Working | `alpha-backtest` | Now | [status] |
| The same backtest on real free data, shown on a screen | Unproven | `alpha test` report in `alpha-web` | Path 1 | [grade] |
| Rank many assets by a factor and replay the basket with costs | Working | `alpha-cli` judge | Now | [status] |
| One portfolio engine per kind of test; duplicates retired after a side-by-side check | Missing | `alpha-backtest` | Path 3 | [slim] |
| Short selling in setup trades with assumed borrow or funding costs | Working | `alpha setup trade`, Setup Lab | Path 1 | private |
| Short selling in rule tests | Missing | `alpha-backtest`, `alpha-cli` spine | Path 1 | private |
| Risk-per-trade position sizing in rule tests and setup trades (setup trades report R, currency sizing remains missing) | Missing | `alpha-backtest`, `alpha-cli` spine | Path 1 | private |
| Costs that grow with trade size, and a capacity view at the owner's size | Missing | `alpha-validation` | Path 1 | private |
| Benchmark on a total-return basis: dividends, cash yield, real terms, every rolling window | Missing | run report | Path 1 | private |
| Plain answer to "is this mostly the market?" beside every result | Unproven | rule-test report: buy-and-hold table and drawdown flag | Path 1 | [partner] |
| Twins of a test: sizing changed only, or one filter removed | Missing | new `alpha vary` | Path 1 | private |
| Variants compared at the same capital and risk | Missing | `alpha-backtest` | Later | private |
| Daily decision with intraday entry timing | Missing | `align_as_known` exists (PR #189); not yet usable from rules or strategies | Path 2 | [any-bar] |
| Machine-learning models trained by Qlib and replayed with costs | Working | `workers/qlib` | Now | [status] |
| Strategy development workspace (fixed approved steps) | Unproven | `alpha-strategies` | Later | [status] |
| A new method compared with a plain baseline at the same data and trial budget | Missing | `alpha-validation`; [journey check](backlog/platform-journey-check.md) | Later | private |
| An idea judged together with current holdings against an equal-weight basket | Missing | `alpha-backtest` | Later | private |

[any-bar]: ../reference/project/owner-decisions-3.md#2026-11-15-no-daily-only-rule-fewer-strict-rules
[free]: ../reference/project/owner-decisions-2.md#2026-11-14-free-real-data-on-the-dell-now
[grade]: ../reference/project/owner-decisions-3.md#2026-11-15-what-production-grade-means
[no-hft]: ../reference/project/owner-decisions-2.md#2026-11-14-never-high-frequency-trading
[papers]: ../reference/project/owner-decisions.md#2026-11-14-literature-strengthens-rd-agents-proposal-step
[partner]: ../reference/project/owner-decisions-3.md#2026-11-15-the-ai-must-be-a-research-partner-not-an-instruction-follower
[precise]: ../reference/project/owner-decisions.md#2026-11-14-precision-and-live-capital
[rd-all]: ../reference/project/owner-decisions-3.md#2026-11-15-adopt-everything-rd-agent-has-memory-first
[retail]: ../reference/project/owner-decisions-2.md#2026-11-14-the-retail-traders-fit-is-the-design-brief
[slim]: ../reference/project/owner-decisions-3.md#2026-11-15-always-slimmer
[spine]: ../reference/project/owner-decisions-3.md#2026-11-15-build-the-thin-spine-clean-then-switch-over
[status]: ../../STATUS.md
[thin]: ../reference/project/owner-decisions-2.md#2026-11-14-thin-alpha-dramatically-rd-agent-and-qlib-are-the-proven-core
[triage]: triage-2026-11.md
[ui]: ../reference/project/owner-decisions-2.md#2026-11-14-keep-the-user-interface
