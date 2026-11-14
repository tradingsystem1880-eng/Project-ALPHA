# Risk stress scenarios that can move the drawdown

**Status:** Idea
**Rough size:** S

## Problem / why

`alpha risk scenario` (and the Workstation's Risk tab) shows "-3σ shock" and "-5σ shock" rows.
Each appends one bad day after the last recorded return, so the worst drawdown changes only if
the series happens to end near a peak. On the free Alpaca SPY validation run (2026-11-14) both
shock rows showed the same maximum drawdown as the base (-0.2601) and the same VaR, which reads
as "robust to a crash" when the scenario barely tested it. The text output now says how the
shocks are built, but the figures themselves are still weak stress tests. Also, "vol +50%" scales
every return around the mean, so a flat (out-of-market) day becomes a small loss of half the mean.

## What "done" looks like

Shock rows that test the path: for example the shock day inserted at the start of the deepest
drawdown (or at the worst point by search), labelled as such, with a metamorphic oracle (a shock
can only deepen the drawdown it is inserted into) and an option to leave flat days flat under
volatility scaling. A versioned change to the scenario panel's contract and the Risk tab.

## Dependencies

`packages/alpha-validation/src/alpha_validation/scenario.py` is quant tier and feeds the
validation gauntlet's risk figures, so the change needs its own pull request with the quant job
and the mutation gate; schedule it after the first real study is approved.

## Sources

- Task record: pull request #174 (its `04-verify.md`)
