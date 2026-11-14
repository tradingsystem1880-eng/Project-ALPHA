# Prove "Quick idea screening" end to end

## What the owner wants

From the owner's direction of 2026-11-14, passed on by the orchestrating session: "All 31
unproven features. Prove, built, implement, improve all of them. 1 by 1." For this capability
(`quick-screening` in `docs/roadmap/capabilities.toml`, state Partial, "tested in-process only; no
end-to-end smoke check yet"): run `alpha scan hypotheses` and `alpha scan replay` from start to
finish through the installed program, on synthetic and on free real data, check every number it
reports against an independent calculation, fix what that finds, and add the end-to-end smoke
check that lets its state honestly become Working.

## What done looks like

- A smoke check runs the installed `alpha` in a throwaway home: seeds labelled synthetic bars,
  freezes a snapshot with `alpha data snapshot`, screens it, replays it, and recomputes the
  reported IC, t statistic, quantile spread, turnover and cost-adjusted spread independently
  (pandas and SciPy, not `alpha_research`).
- The cost-adjusted spread charges the turnover of the horizon it is measured over, not the
  one-day turnover (the defect found on real data, below).
- The text output shows the numbers, not only an identifier.
- The real runs on the Dell are written down with exact commands and results.

## How they will see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_screening_smoke.py
ALPHA_DATA_DIR=<copy of data> uv run alpha scan hypotheses --symbols AAPL,MSFT,... --snapshot free-yfinance-stocks-2026-11-14 --as-of 2026-11-13
```

## Out of scope

The crypto lane on real data (it needs Bybit funding and open-interest datasets, which the Dell
does not have); an overlap-corrected t statistic (filed in the backlog); `packages/alpha-research`
(its panel statistics already match an independent calculation exactly).
