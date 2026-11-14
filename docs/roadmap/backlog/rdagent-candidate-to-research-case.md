# From an RD-Agent candidate factor to a research case draft

**Status:** Scoped
**Rough size:** M

## Problem / why

The ALPHA-judged factor loop ([ADR-0049](../../adr/0049-alpha-judges-rdagent-factors.md)) can
mark a factor `CANDIDATE`: it passed the look-ahead check, the rank-IC screen over the whole trial
ledger and a cost-aware replay, all on the exploration window (2021–2023) of 15 coins that are
today's survivors. That is a lead, not a finding. Nothing yet turns a candidate into something the
owner can approve, and nothing may test it on the locked period (2024 onward) except a formal
research case.

## What "done" looks like

- A command (proposed: `alpha research draft-factor <trial-id>`) that reads one `CANDIDATE` line
  of the trial ledger and writes a research case **draft** in the existing research-case
  workflow (`research/CONTEXT.md`, idea and data stages), never approved: the factor's `factor.py`
  bytes and sha256, the panel identity, the exploration-window result with its disclosures, the
  ledger's trial count at the time and the fixed confirmation plan (one test on the locked period:
  the same screen statistic, the same replay, a threshold fixed in the draft, a family of one or
  of the candidates the owner names).
- The draft states the survivorship limit and proposes a survivorship-free universe (coins that
  existed at each date, including the later delisted) as a data requirement.
- The owner's approval, the locked-period run and any admission use the research lane's existing
  approval and admission steps; the loop and the draft command grant none of them.

## Dependencies

- The research lane's approval-bound files (`packages/alpha-research/src/**`, `research_*.py`)
  must not change while another study awaits the owner's approval; coordinate with that work.
- A survivorship-free crypto universe is a data task (delisted Binance pairs).

## Sources

- [ADR-0049](../../adr/0049-alpha-judges-rdagent-factors.md) points 5 and 6
- [How a research case is worked](../../reference/research-method.md)
