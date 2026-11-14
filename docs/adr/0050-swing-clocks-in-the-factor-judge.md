# ADR-0050: The factor judge tests every idea at swing holding periods; only a swing pass is a candidate

**Status:** Accepted
**Date:** 2026-11-15
**Deciders:** AI build agents, under the owner's standing rules of 2026-11-14 ("never high
frequency ... we focus on swing trading mostly and some intraday"; thin ALPHA around RD-Agent and
Qlib, exploration needs no approval)
**Amends:** [ADR-0049](0049-alpha-judges-rdagent-factors.md), decision points 2, 5, 6 and 8

## Context

ADR-0049's judge asks one question of every RD-Agent factor: does its rank at today's close
predict the return from tomorrow's open to the open after (a one-day hold), and does a top-third
book rebalanced every day make money after costs? Two real loops on 15 Binance coins
(2026-11-14; 14 trials) proposed fast daily signals. Every factor that passed the screen failed
the replay because it traded 19%-79% of the portfolio per day. At 10 bps fee plus 6 bps slippage
on each side, turning over half the book every day costs about 29% a year.

The owner trades swing (days to weeks), never high frequency. The owner's research handoff
(Appendix A, an audited summary of the Rick material) says to keep four clocks distinct: signal
lookback, decision frequency, holding period and execution latency. "Changing any of these
changes the tested proposition." So a one-day-hold judge tests a proposition the owner will not
trade, and it rewards exactly the ideas the owner rules out.

## Decision

1. **Three pre-stated clocks.** Every new factor is judged at `daily` (1-day hold, rebalanced
   daily), `weekly` (7-day hold, rebalanced every 7 days) and `monthly` (28-day hold, rebalanced
   every 28 days). Crypto trades every calendar day, so these are calendar days. Decisions are
   made at the close and filled at the next open, at every clock. The phase is fixed at the first
   exploration day (2021-01-01).
2. **Screen at clock h.** Decision days are h days apart. The outcome is the open-to-open return
   over the h days after the fill, so consecutive observations share no return day. Inference
   uses these **non-overlapping** windows. A daily sample of h-day returns would overlap and be
   mechanically autocorrelated for h-1 lags. Non-overlapping windows remove that by construction.
   Any remaining serial correlation is handled as in ADR-0049, by the autocorrelation-adjusted
   effective sample size and the stationary block bootstrap on the clock's own series. This
   inference is valid because each observation's outcome window is disjoint from every other's.
   The cost is fewer observations: about 1,090 daily, 155 weekly and 38 monthly in the
   exploration window. A clock with fewer than 20 valid observations is still computed and
   carries a `low_sample` warning (owner, 2026-11-15: prefer labels and warnings over refusals).
   Every
   forward window ends on or before 2023-12-31; 2024 onward stays locked.
3. **Replay at clock h.** The same canonical engine and costs as ADR-0049. The top third is
   chosen only on decision days. On the days between, the targets are the holdings' drifted
   weights, so the book keeps its units; small residual trades from fill-price and fee
   differences are executed and charged. Turnover and annual cost are reported per clock.
4. **Honest multiple testing.** Each factor × clock is one trial. The BH family is every trial in
   the ledger: each earlier single-clock row counts once, each new factor counts three times.
   Rows also report the number of distinct factors. The Deflated Sharpe trials are every replayed
   factor × clock. These remain screening values over an adaptive family; no error rate is
   claimed (ADR-0049 point 5).
5. **The rule.** A factor is a `CANDIDATE` only when it passed the look-ahead check and, **at the
   weekly or the monthly clock**, passed the screen (BH q < 0.10) and had positive net excess
   return in that clock's replay. A pass only at the daily clock is recorded as `FAST_ONLY` and is
   never a candidate. RD-Agent carries an experiment forward (`decision = True`) only when it has
   a candidate. A candidate is still exploratory, not admitted and not confirmed. It is not
   approved or promoted. The owner's single approval gate before paper or live trading is
   unchanged.
6. **What RD-Agent is told.** Through the supported proposer setting (`QLIB_FACTOR_HYPOTHESIS_GEN`,
   ADR-0049 point 8; no RD-Agent file is edited), every proposal round sees a short brief:
   - a retail swing trader, holding days to weeks, never high frequency;
   - the three clocks, and that only a weekly or monthly pass counts;
   - low turnover is wanted;
   - an economic or behavioural mechanism and a falsifier must be stated;
   - the costs charged;
   - what failed already, and why: daily turnover ate the edge.

## Options considered

| Option | Verdict |
|---|---|
| Keep the daily judge and ask RD-Agent for slower ideas | Rejected: a slow idea would still be scored on a one-day hold and charged daily turnover |
| Overlapping daily-sampled h-day returns with a Newey-West or Hansen-Hodrick correction | Rejected for now: uses more data, but needs a lag choice and is fragile with 15 names and short samples; non-overlapping windows need no correction for the overlap |
| Average over all h phases | Not now: more robust to the phase choice, but it hides h-fold dependence; a fixed phase is simpler and stated |
| One clock only (weekly) | Rejected: the owner trades days to weeks, and monthly is where slow mechanisms (trend, carry-like effects) live; the extra clock is counted honestly |
| **Daily, weekly and monthly, non-overlapping, every pair a trial, candidate only at a swing clock** | **Chosen** |

## Consequences

- Fast ideas can still be found, measured and recorded, but they cannot steer the loop as
  candidates.
- The family grows three times faster, so each new idea faces a stricter q. This is intended.
- The monthly clock has only about 38 observations, so it can detect only large effects. Nulls
  there say "not detectable", not "absent".
- Ledger rows from this change are schema V3: one row per factor, with a `clocks` object. V1 and
  V2 rows stay valid.

## Implementation anchors

- `apps/alpha-cli/src/alpha_cli/rdagent_factor_eval.py` (and `_rdagent_clocks.py`): clocks,
  screen, replay, family and status.
- `workers/rdagent/alpha_factor_judge.py`: `SWING_BRIEF`, the scenario text, the ledger summary.
- Tests: `tests/unit/test_rdagent_factor_clocks.py`: a planted slow signal detected at the monthly
  clock; a fast-only signal never promoted; a noise calibration at each clock; determinism; the
  locked period refused.
