## What changed for you

- **"Quick idea screening" is now proven end to end and counts as Working.** A new automatic
  check runs the real `alpha` program: it freezes made-up prices, screens them, replays the screen
  and recomputes every number with independent code.
- **Fixed: costs for longer horizons were understated.** The "cost-adjusted spread" charged one
  day's turnover against a 5-, 10- or 21-day return. On your Yahoo data the 21-day turnover is 3
  to 7 times the one-day figure; the screen now charges it.
- **The plain-text output shows the results** (a table per signal and horizon), not only an id.
- Run on your free Yahoo and Alpaca data: every number matched an independent calculation.

## How to see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_screening_smoke.py
```

## What I am unsure about

- The t statistics for horizons over one day are inflated by overlapping returns (21-day t of
  +22 on Yahoo); a corrected figure is a backlog item.
- The crypto screening lane needs Bybit funding and open-interest data; not run end to end.
