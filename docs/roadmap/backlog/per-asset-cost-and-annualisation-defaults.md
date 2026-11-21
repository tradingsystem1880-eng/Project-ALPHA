# Per-asset-class cost and annualisation defaults

**Status:** Scoped
**Rough size:** S

## Progress

M71 built the class table, the costs line and `costs = "class-default"`. A spec without costs keeps the flat default:
[cost classes](../../reference/invariants/cli-cost-classes.md).

## Problem / why

Found on 2026-11-15. `alpha backtest run` uses the same defaults for every asset class: fee 1 bp
and slippage 2 bp per side. That is near a commission-free US broker for liquid ETFs, but Binance
spot taker fees are about 10 bp. Daily crypto runs also annualise with 252 periods by default,
although crypto trades 365 days a year (intraday runs take bars per year from the bar size and
session: [backtest invariants](../../reference/invariants/backtest.md)). A run made with defaults is therefore optimistic for crypto, and its Sharpe is scaled as if it
traded on stock days, with nothing on the run saying so.

## What "done" looks like

- Defaults chosen by asset class (stock/ETF vs crypto venue), stated in the run manifest and the
  report, and overridable as today.
- Daily crypto runs annualise with 365 (a run-identity change, recorded in the change).

## Dependencies

None.
