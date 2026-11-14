# An RD-Agent loop that ALPHA judges

## What the owner wants

The architecture the owner stated: "RD-Agent runs the research loop; Qlib supplies research tools
and models; Nautilus runs execution-aware backtests; ALPHA connects and governs them". The first
real loop ([record](../2026-11-14-rdagent-first-real-loop/04-verify.md)) ran end to end, but its
backtest, RD-Agent's built-in Qlib model tuned for Chinese stocks, gave every coin the same score,
so the loop judged noise. Its setup was also built by hand in a run folder.

In one sentence: RD-Agent keeps proposing and coding factors, unmodified; ALPHA measures them with
its own point-in-time data, statistics and execution-aware replay under crypto conventions, and
that measurement, with its disclosures, is what RD-Agent's feedback step sees.

## What done looks like

- A decision record: [ADR-0049](../../../../adr/0049-alpha-judges-rdagent-factors.md).
- A repeatable install and launch: hash-pinned packages, no Qlib image, no conda stand-in, one
  documented command that starts the model gateway with its budget caps and the loop;
  `scripts/gate.py doctor` names what is missing.
- The ALPHA-judged loop with offline tests: a planted signal is detected and noise is not, the
  evaluation is deterministic, and look-ahead is caught.
- One real loop of two to three iterations on the 15 coins, within 60 model calls, reported
  honestly, nulls included.

## How they will see it

The run's `evaluations.jsonl` and this task's `04-verify.md`; the roadmap page
[RD-Agent in ALPHA](../../../../roadmap/rd-agent-in-alpha.md).

## Out of scope

Editing RD-Agent; admitting, approving or promoting anything; evaluating the reserved window
(2024 onward); the paid model route; research-lane approval-bound files
(`packages/alpha-research/src/**`, `research_*.py`), which are only imported.
