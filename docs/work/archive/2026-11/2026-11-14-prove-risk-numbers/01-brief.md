# Prove "Risk numbers that state what they are based on" end to end

## What the owner wants

From the owner's direction of 2026-11-14, passed on by the orchestrating session: "All 31
unproven features. Prove, built, implement, improve all of them. 1 by 1." For this capability
(`risk-numbers` in `docs/roadmap/capabilities.toml`, state Partial, "tested in-process and in a
browser against a test server; no end-to-end smoke check yet"): run `alpha risk scenario` and the
Workstation route `GET /api/risk/scenario` start to finish through the installed programs, on
synthetic and free real data, check every figure against an independent calculation, fix what
that finds, and add the smoke check that lets it become Working.

## What done looks like

- A smoke check runs the installed `alpha` and `alpha-web` in a throwaway home on a backtest run
  and on a validation run, recomputes all 30 figures (5 scenarios x 6 metrics) independently,
  checks what the provenance says they are based on, sees the web route return the same payload,
  and sees bad equity data refused.
- The provenance names the snapshot a validation run used (it said `null`).
- The text output says how the shock scenarios are built, so an unchanged drawdown under a
  "-5 sigma shock" is not misread as robustness.

## How they will see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_risk_smoke.py
uv run alpha risk scenario --from-run <run id> --json --include-metric-basis
```

## Out of scope

Where the shock day is placed and how flat days are scaled (`packages/alpha-validation`, filed in
the backlog); the browser panel (its Playwright journeys exist and run in CI).
