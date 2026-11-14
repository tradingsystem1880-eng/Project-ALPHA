## What changed for you

- RD-Agent's research loop now has a judge that measures something. RD-Agent still proposes the
  ideas and writes their code, unchanged; ALPHA now scores each idea itself, on its own frozen copy
  of the Binance bars, with the rules ALPHA uses everywhere (decide at a day's close, trade at the
  next open, real crypto costs, 365-day years), and tells RD-Agent the verdict. The decision record
  is [ADR-0049](../../../../adr/0049-alpha-judges-rdagent-factors.md).
- Every idea ever tested is written to one permanent list (the "trial ledger"); an idea that comes
  back with the same code is recognised as a repeat. Every result says how many ideas have been
  tried so far and is corrected for it. A cheap check comes first; only ideas that pass it are put
  through the trading simulation. 2024 onward is locked away from the loop entirely, for a later
  check that only you can approve.
- The install is now repeatable: one setup flag builds a checksum-pinned environment; no 10.9 GB
  Docker image, no hand-added packages, no stand-in programs. One command runs a loop.
- The first real run (three rounds, five ideas, 37 model calls, no money, 7 minutes) found no
  candidate. Two ideas (calmer coins beat wilder ones day by day) showed a strong ranking pattern,
  but buying the calmest coins lost money against simply holding all 15 after costs. Details:
  `04-verify.md`. Exploratory, about 15 coins that survived to today; not evidence.

## How to see it

On the Dell: the run folder `/home/hunta/alpha-clean-base/runs/2026-11-14-rdagent-alpha-judged-loop/`
(`evaluations.jsonl` for ALPHA's verdicts, `receipt.json` for the summary) and the ledger
`/home/hunta/alpha-clean-base/runs/rdagent-trial-ledger/rdagent-factor-trials.jsonl`. To repeat:
`bash scripts/setup_rdagent.sh --with-factor-runtime`, then the command in the
[worker README](../../../../../workers/rdagent/README.md#alpha-judged-factor-loop-2026-11-14).
Each run spends real model calls (about 40; never more than 60) and adds to the ledger.

## What is still not done

1. **Started by `alpha` under its job supervisor** (budget reserved before launch, cancel,
   recovery screen): today a separate launcher does this with the gateway's call cap and its own
   clean-up ([backlog](../../../../roadmap/backlog/rdagent-factor-loop-supervision.md)).
2. **A Nautilus simulation.** The trading simulation is ALPHA's own synchronized replay, the one
   the Qlib worker's predictions use, not Nautilus; ALPHA has no Nautilus replay for a ranking
   across many coins yet.
3. **From a candidate to a research case draft for your approval**: specified, not built
   ([backlog](../../../../roadmap/backlog/rdagent-candidate-to-research-case.md)).
4. **A wider, survivorship-free universe.** 15 coins chosen today are survivors; coins that died
   (LUNA, FTT, …) are missing. Every result says so; a fix needs delisted pairs' data.
5. **An end-to-end smoke check with a scripted model** (so CI-like checks can run the whole loop
   without real model calls): the model gateway's fake route returns text RD-Agent cannot parse.
6. Already listed elsewhere: restart after a crash; CI coverage of RD-Agent.

## Anything only you can decide

- Whether more runs should spend model calls on this 15-coin universe now, knowing each idea
  tried is added to the ledger for good and makes later findings harder to pass, or wait for a
  wider survivorship-free universe first.
- When a candidate appears: whether to have it drafted into a research case and tested once on
  the locked period (2024 onward).

## Checks run

`uv run python scripts/gate.py check` (all passed); the factor-runtime tests on the Dell with
`ALPHA_FACTOR_PYTHON` and `ALPHA_RDAGENT_SOURCE` set; the real run; a determinism re-check of the
real run's first evaluation. See `04-verify.md`.
