---
owner: project layer
sources:
  - README.md
verified: aa600e57932d
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

## The research loop

The intended loop, step by step, and the part that does each step. Today only parts of it run
end to end, and only on made-up data; see [STATUS.md](../../../STATUS.md) for what works.

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

Today a human-run case walks these steps through the six stages of the
[research pipeline](../../../research/CONTEXT.md); changing ALPHA itself walks the
[delivery pipeline](../../../workflow/CONTEXT.md). RD-Agent (Microsoft's open-source AI research
agent) is meant to run steps 3 to 6 over and over. ALPHA keeps
the budget, the data, the backtests, the statistics and the owner's approvals. The fullest account
of this split is [RD-Agent in ALPHA](../../roadmap/rd-agent-in-alpha.md).

In the owner's words: "RD-Agent runs the research loop; Qlib supplies research tools and models;
Nautilus runs execution-aware backtests; ALPHA connects and governs them." ALPHA is more than a
shell: it owns budgets, data rules, experiment records, validation and approvals. Not every
experiment needs Qlib. This is the intended architecture; the complete model-connected, real-data
loop is not yet qualified ([log](owner-decisions.md#2026-11-14-the-architecture-in-one-line)).

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
[owner decisions log](owner-decisions.md) (volume 2: [owner-decisions-2.md](owner-decisions-2.md)). If the two disagree with the recommendation, say so
and ask the owner; do not decide. A part being uninstalled, skipped in tests or unfinished is a
task to finish, not a reason to shelve it.
