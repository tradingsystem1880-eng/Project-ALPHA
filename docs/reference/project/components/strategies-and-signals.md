---
owner: project layer
sources:
  - packages/alpha-strategies/CONTEXT.md
  - packages/alpha-patterns/CONTEXT.md
verified: a79d832d
---

# Strategies and signals

Trading rules and the building blocks they are made of: indicators, chart patterns (such as
trendlines or head and shoulders), signals and position sizing. A rule turns past bars into a
decision to buy, sell or hold.

## Why it exists

Many market ideas are rules rather than machine-learning models. ALPHA needs a precise, causal way
to state such a rule, so that the same rule can be backtested, checked statistically and later
traded paper or live without changing its meaning.

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

See the capabilities below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `packages/alpha-strategies`, `packages/alpha-patterns`
- **Capabilities:** `rules-and-scans`, `strategy-development`
- Code: `packages/alpha-strategies/src/`, `packages/alpha-patterns/src/`; the `alpha rules`,
  `alpha scan` and `alpha suite` commands in `apps/alpha-cli/`.
- How to change it: [packages/alpha-strategies/CONTEXT.md](../../../../packages/alpha-strategies/CONTEXT.md),
  [packages/alpha-patterns/CONTEXT.md](../../../../packages/alpha-patterns/CONTEXT.md).
- Decision records: [ADR-0003](../../../adr/0003-t+1-fill-encoding.md),
  [ADR-0019](../../../adr/0019-governed-research-cases-before-strategy-development.md).

## Decisions and open questions

- No owner decision about this part is in the [owner decisions log](../owner-decisions.md) yet.

## Never

- Never let a rule or pattern use a bar it could not yet have seen.
- Never write strategy code for a market idea that has not been through a research case.
- The rules: [strategy invariants](../../invariants/strategies.md) and
  [pattern invariants](../../invariants/patterns.md).
