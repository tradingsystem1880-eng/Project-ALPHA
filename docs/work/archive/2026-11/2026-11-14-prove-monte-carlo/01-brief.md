# Prove "Path-risk simulation (Monte Carlo)" end to end

## What the owner wants

From the owner's direction of 2026-11-14, passed on by the orchestrating session: "All 31
unproven features. Prove, built, implement, improve all of them. 1 by 1." For this capability
(`monte-carlo` in `docs/roadmap/capabilities.toml`, state Partial, "tested in-process only; no
end-to-end smoke check yet"): run `alpha monte-carlo classical` start to finish through the
installed program on synthetic and free real data, check every number it reports against an
independent calculation, fix what that finds, and add the smoke check that lets it become Working.

## What done looks like

- A smoke check runs the installed `alpha`: a validation run, then the classical Monte Carlo on
  it, then `alpha report` and `alpha figures render`; it recomputes every family summary
  (terminal-return and drawdown quantiles, loss streak, loss and ruin probabilities with Wilson
  intervals) independently from the published paths, and checks determinism.
- The regime family says how its two states are populated, and warns when one state is nearly
  empty (on Alpaca SPY 2016-2026 only 55 of 2,205 OOS days fell in the "calm" state, so that family
  was in effect the IID one).
- The command's own output shows the headline numbers, not only grades.

## How they will see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_monte_carlo_smoke.py
uv run alpha monte-carlo classical --from-run <validate run id>
```

## Out of scope

`alpha monte-carlo kronos` with the real Kronos model (its model files are not on the Dell; it ran
only with the stand-in model, which proves nothing); `packages/alpha-validation` (its numbers
already match an independent calculation exactly).
