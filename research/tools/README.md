---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/spine/*.py
  - apps/alpha-cli/src/alpha_cli/results_cmds.py
  - apps/alpha-cli/src/alpha_cli/test_cmds.py
  - apps/alpha-cli/src/alpha_cli/context_cmds.py
  - apps/alpha-cli/src/alpha_cli/context_sources_cmds.py
verified: f069f9ff4286d851
---

# Research tools, by symptom

Start from the symptom. Each card gives a tool's command, how to read it, its limits and what to try next ([playbook](../PLAYBOOK.md)).

| What you see or need | Open |
|---|---|
| Stored daily bars may have a missing split, gaps or bad timestamps | [daily data health](data-health.md) |
| "Which check fits my situation?" | [toolbox by situation](toolbox-by-situation.md), or `alpha tool find "<words>"` |
| An idea to test (write the [idea card](idea-card.md) first; [library](library.md) has published ones) | [rule test](rule-test.md), then [follow](follow.md) |
| "Does the whole pipeline still work on real data?" | [nightly run](nightly-run.md) |
| A chart setup: "show me every time this happened" | [setup find](setup-find.md), [with a context condition](setup-context.md) |
| What followed each separate setup occurrence | [setup study](setup-study.md) |
| A setup traded with stops, targets and a time limit | [setup trade](setup-trade.md) |
| "Did we test this?", "what was the number?", "do two runs move together?" | [results and cite](results-and-cite.md), [portfolio book](portfolio-book.md) |
| The result looks too good | [diagnose and audit](diagnose-and-audit.md), then [random-price null](random-price-null.md) |
| The result looks too good after many tries | [deflated Sharpe and trials](deflated-sharpe-and-trials.md) |
| Big drawdown in a short period | [benchmark and drawdowns](benchmark-and-drawdowns.md), then the macro row below |
| Works in some years only | [benchmark and drawdowns](benchmark-and-drawdowns.md) (`by_year`), [walk-forward](walk-forward.md) |
| Few trades | [diagnose and audit](diagnose-and-audit.md) (`enough-trades`), [rule test](rule-test.md) on more assets |
| Profit from a handful of trades | [diagnose and audit](diagnose-and-audit.md) (`concentrated-profit`), [trade streaks and profit](run-level-checks.md) |
| Would a slightly different data feed change the answer? | [price-noise robustness](price-noise.md) |
| Fragile to costs, to a one-bar delay or to nearby settings | [sensitivity](sensitivity.md), [break-even cost](run-level-checks.md) |
| "Is this just the market going up?" | [inverted-signal control](inverted-signal-control.md) |
| "Does it hold up out of sample?" | [walk-forward efficiency](walk-forward.md) |
| "Is it just the market?", "a known published factor?" | [benchmark and drawdowns](benchmark-and-drawdowns.md), [published factors](published-factors.md) |
| Market beta, calm or turbulent regimes, "when did it change?" | [attribution, regimes and change points](attribution-regimes-changepoints.md) |
| How wide is the return range, or how deep the drop? | [resampling](resampling-checks.md), [fat tails](montecarlo-checks.md), [path risk](path-risk.md) |
| Why a judged RD-Agent idea stopped | [one idea’s journey](rdagent-journey.md) |
| A picture for the owner | [charts](charts.md) (`trade_pnl` for profit by trade) |
| Need the macro picture | [macro](macro-context.md), [positioning](positioning-short-volume-context.md), `macro_window` ([diagnose](diagnose-and-audit.md)) |
| Crypto funding or open interest as known | `alpha context show-bybit --symbol BTCUSDT --kind funding --as-of 2024-03-12 --json` |

## Not available yet

Say "not available yet" and name the gap; never invent the output. Planned, not built:

- regime detection with models refitted only on the past (today's regime parameters are fitted in sample),
  and change-point detection known on the day (today's change points are hindsight);
- factor attribution beyond the fixed published set; capacity and size-aware costs (flat basis points today);
- an event calendar (scheduled releases and earnings dates); a lessons search and counted variants;
- short selling, position sizing and intraday bars in the rule test (long or flat, all-in, daily bars);
- the planned plain verbs that would wrap these tools (get, idea, vary, learn, promote): none is a
  command yet, so never type one; use the cards above.

## How to change it

A card is at most 40 lines and names only commands that exist: `tests/unit/test_research_playbook.py`
checks every command, option, metric, flag and audit name against the program. Add a card when a
tool starts to work; move a line out of "Not available yet" in the same change.
