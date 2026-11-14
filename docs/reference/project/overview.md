---
owner: project layer
sources:
  - README.md
verified: a925da3ea835
---

# ALPHA: what it is for and how the parts fit

This is the project layer of the file system. It holds what does not change from task to task:
why ALPHA exists, what each major part is for, and what the owner has decided. Read it before you
recommend keeping, changing, shelving or removing any part. Rules for changing code live in
[`invariants/`](../invariants/research-integrity.md); delivery steps live in the
[delivery pipeline](../../../workflow/CONTEXT.md).

## What ALPHA is for

ALPHA is one person's private research platform for trading strategies. "Private" means it is
just for the owner, never sold or made commercial; it is public on GitHub only because the
account is free ([owner decision, 2026-11-14](owner-decisions.md#2026-11-14-private-means-personal)).

Its job is to find out, precisely, whether a market idea really works: on data as it was known at
the time, after costs, out of sample, against other explanations. The strategies it produces are
meant to trade real money one day, so there is no room for error and no silent loss of quality
([owner decision](owner-decisions.md#2026-11-14-precision-and-live-capital)).

## The target shape

Decided on 2026-11-15 ([clean spine](owner-decisions-3.md#2026-11-15-build-the-thin-spine-clean-then-switch-over),
[production grade](owner-decisions-3.md#2026-11-15-what-production-grade-means),
[research partner](owner-decisions-3.md#2026-11-15-the-ai-must-be-a-research-partner-not-an-instruction-follower)).
This is where the project is going; [STATUS.md](../../../STATUS.md) says what works today.

| Layer | What it is | Its job |
|---|---|---|
| Partner | Claude or ChatGPT, in an app or a terminal | Thinks, suggests, interprets, learns; guided by a playbook and tool cards |
| Toolbox | ALPHA, kept thin | Data, backtests with costs, overfit tests, diagnostics, records, lessons |
| Engines | [RD-Agent](components/rd-agent.md), [Qlib](components/qlib.md), [Nautilus](components/nautilus.md) | Called at pinned versions |
| Screens | The [Workstation](components/web-workstation.md) | How the owner sees and understands; never the place the AI is driven from |

One pipeline serves every idea, at any bar timeframe except high-frequency trading:
idea, data, look before testing, backtest with costs, overfit tests, automatic diagnostic pass,
record and show. Integrity appears as labels on results, not as refusals. The only approval
gate is before paper or live trading.

The spine is built clean inside this repository, one golden path at a time. Each path runs from
a plain-English prompt to a result on a screen, and the old lane it replaces is deleted when it
works. At most two streams of work are in flight.

| Golden path | The prompt it must serve | State |
|---|---|---|
| 1. Rule test | "Test this trend rule on these assets" | next |
| 2. Chart setup | "Show every match of this setup and what happened after" | after 1 |
| 3. Factor mining | "Mine factors on this universe", through RD-Agent with memory | after 2 |

## The research loop

The loop below is what the old lanes implement. It stays until the golden paths replace it.

| Step | What happens | Done by |
|---|---|---|
| 1. Question | The owner asks; papers can feed it | [cases](components/research-cases-and-approval.md), [literature](components/literature-worker.md) |
| 2. Data | Exact, frozen, point-in-time data is chosen for the test | [data layer](components/data-layer.md) |
| 3. Propose | An AI model proposes a concrete hypothesis and experiment | [RD-Agent](components/rd-agent.md) |
| 4. Build | Train a model or write a rule | [Qlib](components/qlib.md), [rules](components/strategies-and-signals.md), [Kronos](components/forecasting.md) |
| 5. Backtest | Simulated with costs: decide at a close, fill at the next open | [Nautilus](components/nautilus.md) |
| 6. Judge | Statistics judge it; feedback goes to step 3 | [validation](components/validation-and-evidence.md), [RD-Agent](components/rd-agent.md) |
| 7. Decide | Only the owner admits evidence and promotes a strategy | [cases and approval](components/research-cases-and-approval.md) |
| 8. Trade | Paper trading first; live capital only in a later phase the owner approves | [paper and live trading](components/paper-and-live.md) |

In the owner's words (2026-11-14): "RD-Agent runs the research loop; Qlib supplies research tools
and models; Nautilus runs execution-aware backtests; ALPHA connects and governs them"
([log](owner-decisions.md#2026-11-14-the-architecture-in-one-line)). The 2026-11-15 decisions
above refine this: the AI partner leads, and RD-Agent is one engine it calls.

## How the parts connect

- The `alpha` [command line](components/command-line.md) is the one place that joins the parts.
  The [Workstation](components/web-workstation.md) and the [AI assistants](components/ai-assistants.md)
  ask it to act; they never act on their own.
- RD-Agent, Qlib and the literature tools run as separate worker programs with their own
  installs. ALPHA installs and calls the real upstream packages at fixed versions; it does not
  copy or rebuild them ([owner decision](owner-decisions.md#2026-11-14-install-and-call-real-qlib)).
- The layers and data folders are drawn in [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Phases

Each step needs the owner's approval before the next starts.

1. **Development on the Dell.** The Dell is the main development machine now; the work is to move the
   project forward and make it production ready. Since 2026-11-14 it also downloads free real market
   data (Yahoo, Stooq, crypto exchanges) and results on it are labelled not yet confirmed
   ([owner decision](owner-decisions-2.md#2026-11-14-free-real-data-on-the-dell-now)); the first goal is one
   real RD-Agent loop ([owner decision](owner-decisions-2.md#2026-11-14-first-goal-one-real-rd-agent-loop)).
2. **Confirmation on the Mac, with real data.** The Mac comes later, to confirm with live data
   ([owner decision](owner-decisions.md#2026-11-14-dell-now-mac-later)).
3. **Paper trading**, with no real money.
4. **Live capital**, as a separate phase with its own decision record; today no code path can
   place a live order ([rule](../invariants/research-integrity.md#no-live-capital)).

## Principles

- Precision first. Measure, do not assume. A passing test or a good chart is not proof of an edge.
- The owner decides. Nothing an agent, screen or model says counts as the owner's approval
  ([rule](../invariants/research-integrity.md#owner-authority)).
- Use the real engines. RD-Agent, Qlib and Nautilus are meant to be installed and called at
  pinned versions, never copied or rebuilt; one not yet installed on a machine is work to finish.
- Keep it tidy. The owner wants steady, healthy progress and a project that never becomes a mess
  ([owner decision](owner-decisions.md#2026-11-14-steady-progress-never-a-mess)).
- One home per fact: link to it, never copy it.

## Components

| Component | In one line |
|---|---|
| [RD-Agent](components/rd-agent.md) | The AI research loop: propose, build, run, judge, remember, repeat |
| [Qlib](components/qlib.md) | Microsoft's machine-learning toolkit for stock prediction, run in its own worker |
| [Nautilus](components/nautilus.md) | The backtest engine (NautilusTrader) and ALPHA's harness around it |
| [Data layer](components/data-layer.md) | Downloads, point-in-time storage and frozen snapshots |
| [Strategies and signals](components/strategies-and-signals.md) | Trading rules, chart patterns and indicators |
| [Forecasting](components/forecasting.md) | The Kronos price-forecasting model |
| [Validation and evidence](components/validation-and-evidence.md) | The statistical checks and the reports they produce |
| [Research cases and approval](components/research-cases-and-approval.md) | Research cases, phases and the owner's decisions |
| [Literature worker](components/literature-worker.md) | Finds papers and screens their claims |
| [Command line](components/command-line.md) | The `alpha` command, the control store and the shared core |
| [Web workstation](components/web-workstation.md) | The browser screens |
| [AI assistants](components/ai-assistants.md) | The in-product assistant and the tool server for AI clients |
| [Paper and live trading](components/paper-and-live.md) | The route from research to practice trading to real money |
| [Delivery and agent tooling](components/delivery-and-agent-tooling.md) | How changes are made and checked: the gate, tests, this file system |

## Before you recommend removing anything

Any recommendation to shelve, delete or cut the scope of a part must first cite that part's
component file (its "Why it exists" and "Never" sections) and the
[owner decisions log](owner-decisions.md) (volumes [2](owner-decisions-2.md) and [3](owner-decisions-3.md)). If the two disagree with the recommendation, say so
and ask the owner; do not decide. A part being uninstalled, skipped in tests or unfinished is a
task to finish, not a reason to shelve it.
