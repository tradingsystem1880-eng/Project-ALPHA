# Capability trace: the capability map against the checklist

Links each workflow in the [capability map](capabilities.toml) (what [STATUS.md](../../STATUS.md) shows)
to the [checklist](production-scope.md) row it serves, so neither list can drift from the other.
`tests/unit/test_filesystem_contract.py` fails when a capability id is missing here, when a row
named here is not in the checklist word for word, or when a Working checklist row is in neither
table. A capability may serve several rows; a row may be served by several capabilities.

## Capability to row

| Capability | Checklist row |
|---|---|
| `workstation` | The Workstation opens in a browser |
| `price-charts` | Dense multi-panel price charts, full screen, trade markers, two chart styles |
| `market-overview` | Dense multi-panel price charts, full screen, trade markers, two chart styles |
| `stock-data` | Daily stock and ETF bars from a free source, frozen and verified |
| `stock-data` | Results on free data labelled not yet confirmed |
| `intraday-bars` | Any bar size from one minute up; the daily-only refusal removed |
| `crypto-data` | Daily crypto bars: download, resume, freeze into a snapshot, verify |
| `crypto-backfill` | Daily crypto bars: download, resume, freeze into a snapshot, verify |
| `download-bookkeeping` | Download receipts and quota bookkeeping |
| `crypto-derivatives-context` | Crypto context: funding rates, open interest, listings |
| `filing-events` | Event calendar: central-bank meetings, inflation releases, an earnings-date proxy |
| `positioning-short-volume-context` | Macro series as first published: rates, inflation, jobs, credit, volatility index |
| `setup-find` | Every match of a setup on the chart, rejected ones greyed, before any rule is fixed |
| `setup-trade` | Short selling in setup trades with assumed borrow or funding costs |
| `setup-trade` | Which came first after each match, target or stop, with still-open trades counted |
| `setup-trade` | The same study against random dates and plain market drift |
| `setup-study` | What happened after each match (event study) |
| `setup-study` | The same study against random dates and plain market drift |
| `price-lookalikes` | "Has this happened before?": every earlier stretch shaped like the latest bars, and what followed, on one figure |
| `price-novelty` | "What is unusual right now?": the latest bars scored against every earlier stretch, known on the day |
| `afml-labels-and-weights` | Textbook labels and overlap weights from two pinned libraries that must agree |
| `afml-labels-and-weights` | Labels with a target, a stop and a time limit |
| `afml-factor-importance` | Factor importance on purged folds (MDI, MDA, SFI), a report for RD-Agent's factors |
| `afml-purged-cv` | Purged splits by label end time, with embargo, backtest paths and a leak checker |
| `afml-fracdiff` | Fractional differencing with d chosen on training data only |
| `afml-stats-second-opinion` | Second opinions on PSR, DSR, PBO; minimum track record; strategy risk |
| `retained-coverage` | Completeness check on downloaded bars |
| `data-health` | Completeness check on downloaded bars |
| `data-health-on-runs` | Completeness check on downloaded bars |
| `crypto-snapshots` | Reads see only what was known then; snapshots and receipts never change |
| `backtest` | One-asset rule backtest with costs: decide at a close, fill at the next open |
| `backtest` | Rank many assets by a factor and replay the basket with costs |
| `backtest` | Nautilus as the pinned backtest engine |
| `run-reports` | Reopen any stored run with its report |
| `rules-and-scans` | Simple rule language ("close above X and Y"), saved and rerun exactly |
| `strategy-development` | Strategy development workspace (fixed approved steps) |
| `inverted-signal-control` | Inverted-signal control: the opposite trade must lose, or the edge is a data artefact |
| `price-noise` | Robustness to noise added to the price series, re-running the rule on perturbed prices |
| `implausibly-good` | A "too good to be true" label for results far above what a retail swing book plausibly earns after costs |
| `walk-forward-efficiency` | Walk-forward efficiency (out-of-sample over in-sample result), labelled as a rule of thumb |
| `validation-gauntlet` | Walk-forward testing with gaps between train and test |
| `validation-gauntlet` | Luck-adjusted scores: deflated Sharpe, overfitting probability, combinatorial splits |
| `validation-gauntlet` | Random-price and shuffled-bar comparisons |
| `validation-gauntlet` | Bootstrap ranges (block resampling) around results |
| `validation-gauntlet` | Drawdown episodes listed and dated |
| `idea-card` | Four clocks on each idea: signal lookback, decision pace, holding period, execution delay |
| `idea-workspace` | The Workstation opens in a browser |
| `idea-library` | Verified source library: papers, books and tools checked to exist, grouped by topic, rules of thumb traced to their origin |
| `published-factor-reference` | Verified source library: papers, books and tools checked to exist, grouped by topic, rules of thumb traced to their origin |
| `front-door` | Every test, tool and variant counted in one ledger; the count printed on each result |
| `forward-follow` | Paper trading: local crypto practice account or a broker practice account |
| `portfolio-book` | Paper trading: local crypto practice account or a broker practice account |
| `follow-today-screen` | Paper trading: local crypto practice account or a broker practice account |
| `nightly-run` | Every test, tool and variant counted in one ledger; the count printed on each result |
| `monte-carlo` | Path-risk simulation in three families (a fourth, Kronos paths, runs on a stand-in) |
| `risk-numbers` | Risk figures that state their basis (value at risk, expected shortfall) |
| `prop-firm-check` | Prop-firm challenge check, as an optional tool and never the goal |
| `price-forecasts` | Kronos forecast ranges as an exploratory view |
| `research-cases` | Staged research cases with an approval at each stage (the old lane) |
| `quick-screening` | Quick recorded first look at many ideas |
| `literature` | Find papers, screen their claims, tie a claim to its test, keep the PDF |
| `paper-to-experiment` | Find papers, screen their claims, tie a claim to its test, keep the PDF |
| `ai-investigations` | Ask an in-product assistant about a recorded run |
| `ai-tools-connection` | Tool server so Claude or Codex can call ALPHA, cut down to the nine verbs |
| `providers-and-jobs` | Provider checks and a job list for long downloads |
| `paper-trading` | Paper trading: local crypto practice account or a broker practice account |
| `ml-lab` | Machine-learning models trained by Qlib and replayed with costs |
| `alpha158-v2` | Qlib's upstream price features (Alpha158) |
| `alpha158-v3` | Qlib's upstream price features (Alpha158) |
| `qlib-refit` | Qlib's full model list, with retraining fold by fold |
| `qlib-in-research-cases` | Staged research cases with an approval at each stage (the old lane) |
| `native-engine-demos` | Chat panels and demo views folded away once their content shows elsewhere |
| `ai-stock-research` | RD-Agent's factor loop with a real model on real bars, judged by ALPHA |
| `ai-stock-research` | Trial ledger for RD-Agent's factors, failures kept |
| `one-trial-ledger` | Every test, tool and variant counted in one ledger; the count printed on each result |
| `ai-stock-research` | Call and dollar caps on RD-Agent's model use |
| `rdagent-run-viewer` | RD-Agent's own report reader and run viewer used instead of rebuilt |
| `native-job-result` | RD-Agent results readable in the Workstation |
| `rdagent-idea-journey` | One judged factor idea in seven steps with its stored evidence pictures |
| `rdagent-workstation-panel` | RD-Agent results readable in the Workstation |
| `daily-rule-study` | Say an idea in plain English to Claude or ChatGPT and the whole pipeline runs it |
| `ai-research-team` | Small autonomous research team around RD-Agent |
| `mac-real-data` | Confirmation on the Mac with a paid, authoritative data source |
| `macro-context` | Macro series as first published: rates, inflation, jobs, credit, volatility index |
| `options-data` | Confirmation on the Mac with a paid, authoritative data source |
| `rule-test` | The same backtest on real free data, shown on a screen |
| `rule-test` | Plain rules tested as written, with no hidden sizing or rebalancing defaults |
| `rule-test` | Integrity as labels on results, not refusals (exploratory, free data, trial count) |
| `result-diagnostics` | Automatic diagnostic pass after every test: facts and flags in plain sentences |
| `result-diagnostics` | Cheap stress re-runs: double costs, enter one bar late |
| `investigation-tools` | Regime detection and change points on a run: causal regime labels, in-sample model labelled, change points labelled hindsight |
| `investigation-tools` | Exposure to the market or one chosen asset, such as SPY or Bitcoin: beta, leftover return, up and down beta |
| `answer-check` | A drafted answer's tagged numbers and run labels checked against the stored records and flags (`alpha results check`; not the reasoning) |
| `honesty-selftest` | Planted honest and dishonest answers prove the checker catches invented numbers (`alpha partner selftest`) |
| `answer-check` | Runs compared side by side, differences computed by code (`alpha results compare`) |
| `family-deflated-sharpe` | Variants of one idea counted as one family, with the effective number of tests shown |

## Working rows that are not a workflow

| Checklist row | Why no capability |
|---|---|
| Weekly automatic health check that opens small clean-up pull requests | a scheduled task, not an `alpha` workflow |
| One gate for every change: look-ahead guards, statistical oracles, repeatable runs | the delivery check (`scripts/gate.py`) |
| File system that says what each part is for, updated with every change | documentation, checked by the contract test |
| Generated status page of what works | generated from the capability map itself |
| Never high-frequency trading: nothing built for ticks, order books or speed | a scope rule |
| Every capability traced to a checklist row, every command to a capability | this page and its test |
