---
owner: project layer
sources:
  - apps/alpha-cli/src/alpha_cli/spine/setup_*.py
  - apps/alpha-cli/src/alpha_cli/setup_cmds.py
  - packages/alpha-strategies/CONTEXT.md
  - packages/alpha-patterns/CONTEXT.md
  - packages/alpha-study/CONTEXT.md
verified: 47183be5572b7938
---

# Strategies and signals

Trading rules and the building blocks they are made of: indicators, chart patterns (such as
trendlines or head and shoulders), signals and position sizing. A rule turns past bars into a
decision to buy, sell or hold.

## Why it exists

Many market ideas are rules rather than machine-learning models. ALPHA needs a precise, causal way
to state such a rule, so that the same rule can be backtested, checked statistically and later
traded paper or live without changing its meaning. The owner's own chart setups are ideas of equal
standing with RD-Agent's, judged by the same ledger and statistics
([design brief](../owner-decisions-2.md#2026-11-14-the-retail-traders-fit-is-the-design-brief)).

## Its job in the research loop

Step 4 of the [research loop](../overview.md#the-research-loop): a rule is the experiment that
[Nautilus](nautilus.md) backtests. RD-Agent's daily rule study (see [RD-Agent](rd-agent.md)) runs
one of these rules.

## Intended design

- Indicators and patterns are reported only once they were knowable from the bars seen so far.
- A strategy decides on the close of a bar and fills at the next open, never earlier.
- Rules are saved as specs, so a rule can be reopened and rerun exactly.
- Research comes before strategy: a market idea becomes a research case first
  ([rule](../../invariants/research-integrity.md#research-before-strategy)).

## What is real today

The daily chart-setup lane (`alpha setup find`, `study`, `trade`) is described in [Setup Lab](setup-lab.md).
The older rule language remains for the screens that use it until it is replaced; see
[study invariants](../../invariants/study.md).

Plain long/flat all-in sizing is available beside volatility targeting for moving-average crossover,
Donchian breakout and time-series momentum; it holds entry units until the rule exits.

Two chart questions are answered with the outside library STUMPY (a matrix-profile library) glued in
through one module, `alpha_patterns/lookalike.py`:

- `alpha lookalike` — "has price action like this happened before?": every earlier stretch shaped like
  the latest bars, searched only before them with a threshold fixed in advance, and what followed each
  one. It is a look at outcomes, so each run is recorded in the trial ledger as exploratory.
- `alpha unusual` — "what is unusual right now?": how unlike every earlier stretch the latest bars are.

Both draw one figure with the match count and the label "descriptive, not a forecast". Neither is a
signal or a strategy; a lookalike says nothing about what happens next.

See the capabilities below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `packages/alpha-strategies`, `packages/alpha-patterns`
- **Capabilities:** `rules-and-scans`, `strategy-development`, `price-lookalikes`, `price-novelty`
- Code: `packages/alpha-strategies/src/`, `packages/alpha-patterns/src/`; the `alpha rules`,
  `alpha scan`, `alpha suite`, `alpha lookalike`, `alpha unusual` and `alpha setup` commands in
  `apps/alpha-cli/`.
- How to change it: [packages/alpha-strategies/CONTEXT.md](../../../../packages/alpha-strategies/CONTEXT.md),
  [packages/alpha-patterns/CONTEXT.md](../../../../packages/alpha-patterns/CONTEXT.md).
- Decision records: [ADR-0003](../../../adr/0003-t+1-fill-encoding.md),
  [ADR-0051](../../../adr/0051-glue-rules-for-outside-projects.md) (how STUMPY is glued),
  [ADR-0019](../../../adr/0019-governed-research-cases-before-strategy-development.md).
- **Plan:** [stages 1 and 3](../../../roadmap/production-scope.md#3-look-before-testing) of the
  checklist.

## Decisions and open questions

- Owner decisions: see the [decisions log](../owner-decisions.md). Chart-setup work (find, study, trade) has its own page, [Setup Lab](setup-lab.md).
- Decided 2026-11-18: lookalike search and the chart-pattern and trend-line code are RD-Agent's tools, to be
  wired in and never slimmed away ([log](../owner-decisions-5.md#2026-11-18-kronos-the-four-monte-carlos-lookalike-and-pattern-tools-are-rd-agents-toolbox)).
- Decided 2026-11-14: the owner's own chart setups stand equal to RD-Agent's ideas (design brief, linked above).

## Never

- Never let a rule or pattern use a bar it could not yet have seen.
- Never write strategy code for a market idea that has not been through a research case.
- The rules: [strategy invariants](../../invariants/strategies.md) and
  [pattern invariants](../../invariants/patterns.md).
