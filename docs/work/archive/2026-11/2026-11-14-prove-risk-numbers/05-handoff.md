## What changed for you

- **"Risk numbers" is now proven end to end and counts as Working.** A new automatic check runs
  the real `alpha` program and the Workstation: it computes the stress figures for a backtest and
  a validation run, recomputes all 30 with independent code, checks what they say they are based
  on, and sees a tampered result file refused.
- **Fixed:** for a validation run the risk figures said they came from no snapshot; they now name it.
- **The text output explains the stress rows:** the "-3σ" and "-5σ" shocks are one bad day added
  at the end, so they rarely change the worst drawdown (a better stress test is in the backlog).
- Four old risk plans are closed with this, and the work-in-progress ceiling drops from 34 to 30.

## How to see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_risk_smoke.py
```

## What I am unsure about

- The shock rows are weak stress tests; changing them touches the quant tier (backlog
  `risk-shock-placement`).
