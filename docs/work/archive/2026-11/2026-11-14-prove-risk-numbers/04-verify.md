# Verification: "Risk numbers that state what they are based on" end to end

Run on the Dell on 2026-11-14 (UTC), branch `m8/prove-risk-numbers`.

## Offline, through the installed programs (the smoke check)

`uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_risk_smoke.py`:
4 passed, 33 s. On the smoke homes (synthetic SPY, snapshot `smoke-v1`):

1. A backtest run: all 30 figures (5 scenarios x Sharpe, volatility, drawdown, VaR, CVaR, total
   return) equal a numpy recomputation from `equity_curve.parquet` (1e-12), also at 99%
   confidence; the provenance names the command, snapshot, snapshot hash, the equity file's
   SHA-256, the as-of time and the anchor; the legacy JSON equals the disclosed one without the
   basis; the text output has the scenarios, the anchor and the new notes; `--include-metric-basis`
   without `--json` exits 2.
2. The installed `alpha-web` serves the identical payload at `/api/risk/scenario`; an unknown run
   gives 404 and confidence 1.2 gives 422.
3. A validation run: the provenance names its snapshot (the fix) and the base figures equal the
   validation's own `oos_metrics`.
4. A rewritten equity file (a repeated timestamp, then an infinite value) is refused by the
   artifact contract (`size mismatch`) before any figure is printed. The planned assertion
   ("strictly increasing") was wrong: the integrity check runs first, so the order and finiteness
   checks behind it are proven in-process only (`tests/integration/test_risk_equity_clocks.py`).
   The smoke test was changed to assert the refusal the installed program really gives.

## For real, on free data (not yet confirmed)

On a copy of the Alpaca folder (`tmp/prove2/mc/real`), validation run `415f2b81ae0ec262` over
SPY 2016-2026 (2,205 OOS returns):

```text
alpha risk scenario --from-run 415f2b81ae0ec262 --json --include-metric-basis
  base       sharpe 0.6145  vol 0.1141  maxdd -0.2601  VaR 0.01056  CVaR 0.01911  total +0.7441
  vol +50%   sharpe 0.4097  vol 0.1712  maxdd -0.3707  VaR 0.01599  CVaR 0.02880  total +0.6230
  vol +100%  sharpe 0.3073  vol 0.2282  maxdd -0.4679  VaR 0.02141  CVaR 0.03849  total +0.4667
  -3σ shock  sharpe 0.5916  vol 0.1143  maxdd -0.2601  VaR 0.01062  CVaR 0.01920  total +0.7065
  -5σ shock  sharpe 0.5751  vol 0.1147  maxdd -0.2601  VaR 0.01062  CVaR 0.01933  total +0.6815
GET /api/risk/scenario?run_id=415f2b81ae0ec262&include_metric_basis=true  -> identical JSON
```

Independent check (`tmp/prove2/scripts/check_risk.py`, numpy only): all 30 figures agreed exactly
(difference 0.0). The base figures equal the validation's `oos_metrics`.

Defect found and fixed: `provenance.snapshot_id` was `null` for this validation run although it
used snapshot `alpaca-starter-2026-11-14` (the command read a top-level field that validation
manifests keep under `metadata`); it now names it, on the command line and the web route.

Rough edges, disclosed in the text output and filed (`risk-shock-placement`): both shock rows keep
the base drawdown because the shock day is appended after the last return; volatility scaling
turns flat days into small losses.

## Checks

- New integration tests: 2 fail on `origin/main`; the risk CLI and web tests pass (64).
- `uv run python scripts/gate.py check --base origin/main`: passed (see the pull request).
