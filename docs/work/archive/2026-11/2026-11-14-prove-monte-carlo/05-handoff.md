## What changed for you

- **"Path-risk simulation (Monte Carlo)" is now proven end to end and counts as Working.** A new
  automatic check runs the real `alpha` program: a validation run, the simulation, the report
  and figures, and recomputes every number with independent code.
- **The "regime" simulation now says what it is based on.** On your Alpaca SPY run 97.5% of days
  fell in its "volatile" state (the cut-off is set from calm 2016-2017), so it was in effect the
  plain reshuffle; it now says so and warns.
- **The command prints the headline numbers** (median outcome, bad-case drawdown, chance of a loss
  and of ruin with their ranges), not just grades.

## How to see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_monte_carlo_smoke.py
```

## What I am unsure about

- The Kronos-model simulation is not proven: the model files are not on the Dell.
- Whether the regime cut-off should come from somewhere other than the first training years is a
  research-design question (ADR-0029); only disclosed here.
