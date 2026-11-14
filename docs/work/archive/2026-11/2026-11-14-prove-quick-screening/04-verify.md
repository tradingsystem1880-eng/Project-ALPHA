# Verification: "Quick idea screening" end to end

Run on the Dell on 2026-11-14 (UTC), branch `m8/prove-quick-screening`.

## Offline, through the installed program (the smoke check)

`uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_screening_smoke.py`:
2 passed, 13 s. Six labelled synthetic symbols are frozen with `alpha data snapshot` and
`alpha data verify`, screened with `alpha scan hypotheses --json` (2 signals x 2 horizons), and
every reported IC mean, t, date count, spread, one-row and horizon turnover and cost-adjusted
spread is recomputed with pandas and SciPy from the snapshot parquet (agreement 1e-12). The four
attempt receipts and eight trial receipts are on disk, no run or control folder is created, the
replay gives the same result digest under a new attempt id, the text output shows the table, and
a screen without a snapshot exits 2 and leaves a `failed` receipt.

New differential oracle `tests/oracles/test_differential_hypothesis_screen.py` does the same for
all five equity signals at horizons 1, 5 and 21 on seven names (15 rows).

## For real, on free data (not yet confirmed)

On copies under `tmp/prove2/` of the Yahoo snapshot `free-yfinance-stocks-2026-11-14` (16
symbols, 9,286 dates, 1990-01-02 to 2026-11-13) and the Alpaca snapshot
`alpaca-starter-2026-11-14` (15 symbols, 2,733 dates, 2016-01-04 to 2026-11-13):

```text
alpha scan hypotheses --symbols <all 16> --snapshot free-yfinance-stocks-2026-11-14 --as-of 2026-11-13 --cost-bps 5 --json
  -> 20 trials, 30 s, missing []
alpha scan replay <scan_id> --json -> same result_digest
```

Independent check (`tmp/prove2/scripts/check_screen.py`: raw snapshot parquet, my own split
adjustment from the actions files, pandas windows, `scipy.stats.spearmanr`): every IC mean, t,
n_dates and quantile spread agreed to 4.1e-16 (Yahoo) and 3.5e-16 (Alpaca). This also showed the
closes are split-adjusted only; dividends are not in the outcomes.

Defect found: the cost-adjusted spread charged the one-row bucket turnover against an h-row spread.
Turnover between dates h rows apart on the Yahoo snapshot:

| signal | 1 row | 5 rows | 10 rows | 21 rows |
|---|---|---|---|---|
| mom_12_1 | 0.062 | 0.127 | 0.174 | 0.244 |
| mom_6_1 | 0.083 | 0.179 | 0.245 | 0.345 |
| range_52w | 0.151 | 0.280 | 0.349 | 0.439 |
| rev_1m | 0.193 | 0.393 | 0.535 | 0.749 |
| vol_63 | 0.020 | 0.057 | 0.086 | 0.134 |

After the fix the 21-row cost-adjusted spread at 5 bp one way is, for example, rev_1m -0.00716
(was -0.00604) and mom_6_1 +0.00735 (was +0.00788). One-row figures are unchanged.

Other findings, not changed: a symbol with no bars yet at the cutoff (NVDA at 1990-01-05) fails
the whole screen loudly instead of being listed as missing; a 21-row plain t of +22 is inflated by
the overlap (backlog `screen-overlap-corrected-t`); the crypto lane needs Bybit funding and open
interest datasets the Dell does not have, so it was not run on real data or end to end.

## Checks

- New unit, integration and oracle tests: 12 fail on `origin/main`, all 48 pass here.
- `uv run python scripts/gate.py check --base origin/main`: passed (see the pull request).
