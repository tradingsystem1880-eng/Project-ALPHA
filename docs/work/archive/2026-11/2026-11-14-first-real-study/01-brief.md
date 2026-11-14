# First real study: bring one research case on real data to the owner's approval

## What the owner wants

The owner, 2026-11-14: "Create a study or whatever is needed to be done to run end to end use of
the project and I will approve it". The orchestrating session turned that into: take ALPHA's real
research workflow from idea to the point where only the owner's approval is missing, on the real
Binance daily bars in `/home/hunta/alpha-clean-base/data`, through the installed `alpha` program;
fix every product defect met on the way; hand the owner a short approval packet.

Two candidates were named: (A) a new, simple hypothesis on the 15 Binance coins, and (B) the
already-specified daily trading-rule study ("Packet 3": 20-day momentum against the same BTC held
throughout, Binance BTC/USDT daily bars 2020-2022, run by RD-Agent's loop).

## What done looks like

- Every stage was walked with the installed program; each command and result is recorded in
  [verification](04-verify.md).
- Every defect met is fixed at its root in a small draft pull request, or recorded with the reason
  it is not fixed here.
- The owner gets one approval packet ([handoff](05-handoff.md)): what is approved, what happens
  after, how long it takes, what it can and cannot conclude, the exact steps, and the files the
  approval is bound to.
- Nothing is approved, admitted, confirmed or promoted by an agent.

## Candidate A, pre-registered before any look at the data

Written 2026-11-14 before any return, chart or backtest of this hypothesis was computed. Only file
lists, month coverage and row counts of the stored data were read.

- **Question.** Among the 15 Binance spot USDT coins on the Dell (BTC, ETH, BNB, LTC, ADA, XRP,
  TRX, XLM, LINK, ATOM, DOGE, BCH, SOL, DOT, AVAX), do the coins with the highest past 3-week
  (21-day) return beat the coins with the lowest over the following week, after costs?
  (Cross-sectional crypto momentum; reported in published work on larger coin sets.)
- **Data and dates.** Daily bars, decided on the close of day t, filled at the open of day t+1.
  A coin is eligible from its first full month on Binance plus 21 days of history. Discovery
  (D1): 2019-01-01 to 2022-12-31. Sealed one-shot confirmation (D2): 2023-01-01 to 2024-12-31.
  Final holdout (D3, never read by research): 2025-01-01 to 2026-10-31.
- **Primary measure.** Mean weekly return of an equal-weight long top-3, short bottom-3 portfolio
  rebalanced every 7 days, net of 10 bps commission plus 7 bps spread and slippage per side on
  each traded leg. Control: the same portfolio built from a random ranking (permutation null, the
  same costs); a secondary control is the equal-weight basket of all eligible coins.
- **Support / contradiction.** Supported if the D2 mean net weekly return is above zero with a
  one-sided block-bootstrap p-value below 0.05 and at least 0.25% a week; contradicted if the D2
  mean is at or below zero; otherwise inconclusive. One primary claim, no tuning on D2.
- **Known weakness, disclosed now.** The 15 coins were chosen in 2026 because they still trade:
  survivorship bias favours both legs being "winners"; short selling spot coins is not possible,
  so the short leg is a research construct, not a tradable position.
- **Budget.** One D0 pilot, one D1 run, one D2 run; no parameter grid beyond lookbacks of 2, 3 and
  4 weeks as a frozen sensitivity family on D1 only.

Result of walking it (details in [verification](04-verify.md)): ALPHA cannot run this case
today. `alpha research capture` accepts it, then stops it at stage 01 with
`RESEARCH_OPERATOR_UNAVAILABLE`: no registered research operator covers a cross-sectional or
daily-bar idea other than the double bottom, the Bybit crowding reversal and the fixed Packet 3
rule. That gap is the backlog item [daily research operators](../../../../roadmap/backlog/daily-research-operators.md)
(rough size L, needs an ADR); building it is not part of this task.

## Out of scope

Approving, admitting, confirming or promoting anything; running either study's real outcome;
deleting or rewriting any stored data; the daily price reader and the daily-rule binding list
(another agent's change, `wt-daily`); the RD-Agent worker; a new research operator for candidate A.
