# Prove "Quick idea screening" end to end

**Delivery state:** Completed — built, reviewed and verified on branch `m8/prove-quick-screening`; done when its pull request merges.
**Build class:** standard — six files; one screening-accounting fix in alpha-cli, tests and a smoke check; no quant-tier source.

Filed straight into the archive, as `2026-11-14-prove-crypto-data` was: the work-in-progress
ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- A new automatic check runs the real `alpha` program to screen ideas the way you would and
  recomputes every number it shows with independent code. "Quick idea screening" can now count as
  Working.
- Fixed: the screen's "cost-adjusted spread" charged one day's turnover against a 5-, 10- or
  21-day return, so for longer horizons it looked cheaper than it is (on your Yahoo data, 21-day
  turnover is 3 to 7 times the one-day figure). It now charges the turnover between dates one
  horizon apart.
- The plain-text output now shows the results; before, it printed only an identifier.
- Nothing for you to decide here.

```json
{
  "schema_version": 1,
  "title": "Prove Quick idea screening end to end",
  "context": "quick-screening is Partial: only in-process CliRunner tests exist. Run through the installed alpha on free Yahoo (16 symbols, 1990-2026) and Alpaca (15 symbols, 2016-2026) snapshots, every IC mean, t statistic, n_dates and quantile spread matched an independent pandas/SciPy recomputation to 4e-16 (with my own split adjustment of the raw bars). One defect: cost_adjusted_spread subtracts 4 x one-row bucket turnover x cost from an h-row spread; a book that earns the h-row spread is rebalanced every h rows, and the replacement fraction between dates h rows apart is 0.24 vs 0.06 (mom_12_1), 0.75 vs 0.19 (rev_1m) at h=21 on the Yahoo snapshot. Also: text mode prints only the scan id; outcomes are split-adjusted price returns without dividends, which no caveat says.",
  "assumptions": [
    {"statement": "panel.bucket_turnover skips any consecutive row pair with fewer than min_names common names, so interleaving (signal[t], signal[t+h], all-NaN row) triples makes it average exactly the (t, t+h) pairs, and for h=1 it returns the same float as bucket_turnover(signal).", "verified_by": "reading packages/alpha-research/src/alpha_research/panel.py bucket_turnover: mask of both rows finite, n_present < min_names -> continue; mean over the remaining fractions in row order"},
    {"statement": "Equity closes from load_bars are split-adjusted only; dividends are not in the price.", "verified_by": "an independent split-only adjustment of the raw snapshot parquet reproduced every reported statistic on the Yahoo snapshot to 4e-16 (tmp/prove2/scripts/check_screen.py)"},
    {"statement": "seed_store bars are one per calendar day from 2020-01-01 with no corporate actions, so a snapshot of them needs no adjustment in an independent recomputation.", "verified_by": "tests/fixtures/cli_fixtures.py _noisy_bars; ParquetStore write_bars writes no actions"},
    {"statement": "_hypothesis_scan.py and scan_cmds.py are not in DAILY_GUARD_FILES and not quant tier; changing them changes runtime_identity's code hash, so screens recorded before the change no longer replay (replay already demands the original environment).", "verified_by": "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py DAILY_GUARD_FILES; runtime_identity in _hypothesis_scan.py"}
  ],
  "alternatives_considered": [
    "Change panel.cost_adjusted_spread or bucket_turnover in alpha-research: rejected, quant-tier and approval-bound bytes; the defect is in how the screen pairs a one-row turnover with an h-row spread, which is alpha-cli code.",
    "Average bucket_turnover over the h phase-offset subsamples signal[o::h]: rejected, it weights offsets equally rather than pairs, so it is not exactly the mean over (t, t+h) pairs.",
    "Rename the existing turnover field to mean horizon turnover: rejected, it would silently change what an existing field means; a new field horizon_turnover is added and turnover keeps its one-row meaning.",
    "Add an overlap-corrected (Newey-West) t statistic now: deferred to the backlog; there is no reference implementation installed (no statsmodels) to build an oracle against."
  ],
  "pre_mortem": [
    "The interleaved panel makes bucket_turnover raise because no pair has enough names: only possible when fewer than three dates are scorable, which evaluate_spec already refuses earlier; the error is a DataError either way.",
    "The smoke check's independent calculation copies the product code and so proves nothing: it is written with pandas rolling windows and scipy.stats.spearmanr, never imports alpha_research or alpha_cli, and reads the snapshot parquet directly.",
    "Text output changes break a caller that parses it: no code or test parses the text line; JSON output is unchanged apart from the new horizon_turnover field and caveat wording."
  ],
  "slices": [
    {"title": "Horizon-matched turnover, honest caveats, readable text output", "verify": "uv run pytest -q tests/unit/test_hypothesis_scan_signals.py tests/integration/test_hypothesis_scan_cli.py", "expected": "all pass; the new known-answer and oracle tests fail on main", "rollback": "revert _hypothesis_scan.py, scan_cmds.py and the tests", "status": "pending"},
    {"title": "Screening smoke check through the installed alpha", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_screening_smoke.py", "expected": "passed", "rollback": "delete tests/smoke/test_screening_smoke.py", "status": "pending"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/roadmap/capabilities.toml", "STATUS.md", "docs/roadmap/README.md", "docs/roadmap/backlog/screen-overlap-corrected-t.md"],
  "out_of_scope": ["packages/alpha-research/src", "packages/alpha-validation/src", "apps/alpha-cli/src/alpha_cli/_crypto_panel.py", "stored data"],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py",
    "apps/alpha-cli/src/alpha_cli/scan_cmds.py",
    "tests/unit/test_hypothesis_scan_signals.py",
    "tests/integration/test_hypothesis_scan_cli.py",
    "tests/smoke/test_screening_smoke.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [tests workspace](../../../../../tests/CONTEXT.md) | How to change it | always |
| [screening code](../../../../../apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py) | `evaluate_spec` | always |
| [panel statistics](../../../../../packages/alpha-research/src/alpha_research/panel.py) | `bucket_turnover`, `cost_adjusted_spread` | always (read only) |
| [smoke harness](../../../../../tests/smoke/_harness.py) | — | slice 2 |
| [smoke homes](../../../../../tests/smoke/conftest.py) | — | slice 2 |

## Slices

### 1. Horizon-matched turnover, honest caveats, readable text output

In `apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py`:

- New public function `horizon_turnover(signal: np.ndarray, *, horizon: int, quantiles: int,
  min_names: int) -> float`: the mean top-plus-bottom bucket replacement fraction between dates
  `horizon` rows apart. Build a panel of shape `(3 * (T - horizon), N)` whose rows are, for each
  `t` in `range(T - horizon)`, `signal[t]`, `signal[t + horizon]` and an all-NaN row, and return
  `panel.bucket_turnover(that, quantiles=quantiles, min_names=min_names)`. Docstring: why the NaN
  separator rows make it the exact mean over `(t, t + horizon)` pairs, and that `horizon == 1`
  equals `panel.bucket_turnover(signal, ...)`. `horizon < 1` or `horizon >= T` raises `DataError`.
- In `evaluate_spec`, per trial row: compute `turn_h = horizon_turnover(signal, horizon=horizon,
  quantiles=quantiles, min_names=minimum)`; add `"horizon_turnover": turn_h` to the row; compute
  `cost_adjusted_spread` with `turn_h` instead of the one-row `turnover`. The `turnover` field keeps
  its one-row value.
- Caveats: replace "Cost-adjusted spread combines daily turnover with horizon returns; no
  portfolio simulation." with "Cost-adjusted spread charges 4 x horizon_turnover (bucket
  replacement between dates one horizon apart) x the one-way cost against the horizon spread; no
  portfolio simulation." and add "Equity outcomes are split-adjusted price returns; dividends are
  not included." Nothing else in the result changes.

In `apps/alpha-cli/src/alpha_cli/scan_cmds.py`, the text (non `--json`) output of both
`hypotheses` and `replay` becomes, via one shared helper:

```text
exploratory screen <scan_id>: <trials> trials; authority none
signal      h    IC mean   t (plain)  dates   spread     cost-adj   turnover/h
rev_1m      1    +0.0123   +1.23      280     +0.00012   +0.00008   0.200
...
missing from snapshot: ZZZ            (only when result["missing"] is non-empty)
plain t statistics; horizons over 1 overlap and are not corrected; no selection adjustment over <trials> trials
```

A `None` IC mean or t prints `n/a`. Replay's first line stays `replayed <scan_id>; attempt
<attempt_id>; authority none`, followed by the same table and footer. JSON output is unchanged.

Tests first; each must fail on main by assertion or missing attribute:

- `tests/unit/test_hypothesis_scan_signals.py`: a known-answer test of `horizon_turnover` on a
  6-date, 5-name panel whose ranking reverses every row (even rows ascending A..E, odd rows
  descending): `quantiles=5, min_names=5` gives 1.0 at horizon 1 and 0.0 at horizon 2; horizon 1
  equals `panel.bucket_turnover` on any random finite 40 x 7 panel exactly; a NaN-heavy row is
  skipped as `bucket_turnover` would. In the frozen-equities run (`request()` with
  `cost_bps=2.0`), every row has `cost_adjusted_spread == spread - 4 * horizon_turnover * 2e-4`
  and the horizon-1 row has `horizon_turnover == turnover`.
- `tests/integration/test_hypothesis_scan_cli.py`: the text output of `scan hypotheses` (no
  `--json`) on the frozen equities contains the header, one line per trial naming `rev_1m`, and the
  footer; with a symbol absent from the snapshot it prints `missing from snapshot:` and the name.
- Written by the orchestrator, not the builder (`tests/oracles/` is a guarded path):
  `tests/oracles/test_differential_hypothesis_screen.py` (new, `pytestmark = pytest.mark.oracle`):
  seed 7 names with `seed_store(n=330, seed=i, sigma=0.01 + 0.003 * i, drift=0.0005 * (i - 3))`,
  snapshot them, run `run_hypotheses` for all five equity signals at horizons 1, 5, 21 with
  `min_names=5, quantiles=5, cost_bps=7.5`, and recompute every row independently with pandas and
  `scipy.stats.spearmanr` only (no `alpha_research`, no `alpha_cli` helpers): signals from the
  documented recipes (`mom_12_1 = P.shift(21)/P.shift(252) - 1`, `mom_6_1 = P.shift(21)/P.shift(126) - 1`,
  `rev_1m = -(P/P.shift(21) - 1)`, `vol_63 = 63-row sample std of daily returns`, `range_52w =
  (P - min252)/(max252 - min252)` where the range is non-zero), forward return `P.shift(-h)/P - 1`,
  per-date Spearman over names with both finite and at least 5 of them, mean, sample-std t times
  sqrt(n), bucket width `n // 5` over a stable argsort, spread of the top minus bottom bucket means,
  turnover between dates 1 and h rows apart as set differences of the top and bottom buckets
  ranked on the common names, and the cost-adjusted spread. Absolute tolerance 1e-12 (n_dates
  exactly). Docstring states it is a differential oracle and what it does not cover (crypto lane,
  memberships).

### 2. Screening smoke check through the installed alpha

`tests/smoke/test_screening_smoke.py` (new; `pytestmark = [pytest.mark.smoke,
pytest.mark.usefixtures("owned_test_process")]`; uses `tests.smoke._harness.alpha` only, every
step a new process). One function-scoped home under `tmp_path`: `seed_store(home / "data",
symbol=s, n=300, seed=i, sigma=0.01 + 0.002 * i, drift=0.0004 * (i - 2))` for six symbols
`AAA`..`FFF` (the same labelled synthetic bars `tests/smoke/conftest.py` uses, documented there),
then `alpha data snapshot screen-v1 AAA BBB CCC DDD EEE FFF` and `alpha data verify screen-v1`.

1. `test_screen_is_recorded_replayed_and_recomputes_independently`:
   - `alpha scan hypotheses --symbols AAA,BBB,CCC,DDD,EEE,FFF --snapshot screen-v1 --as-of
     2020-12-31 --signals rev_1m,vol_63 --horizons 1,5 --cost-bps 10 --json`: `trials == 4`,
     `authority == "none"`, `execution_authority is False`, `missing == []`, 4 result rows.
   - Under `data/scans/hypotheses/attempts/<attempt_id>/`: `started.json`, `resolved.json`,
     `result.json`, `finished.json` with status `completed` and the same `result_digest`, and 8
     trial receipts; `data/scans/hypotheses/specs/<scan_id>.json` exists; `data/runs` and
     `data/control` do not exist (no governed run, no research authority).
   - Independent recomputation in the test (pandas and SciPy, reading
     `data/snapshots/screen-v1/bars/<symbol>.parquet` directly): for each row, IC mean, t,
     n_dates, quantile spread, `turnover`, `horizon_turnover` and `cost_adjusted_spread` agree to
     1e-12 (bucket width `6 // 5 = 1`).
   - `alpha scan replay <scan_id> --json`: same `result_digest`, a different `attempt_id`.
   - Text mode, same arguments without `--json`: stdout has the header line and a `rev_1m` and a
     `vol_63` row, and the footer.
2. `test_screen_without_a_snapshot_is_refused_and_recorded`: `alpha scan hypotheses --symbols
   AAA,BBB,CCC,DDD,EEE --as-of 2020-12-31` exits 2 with `snapshot` in the output, and exactly one
   attempt has a `finished.json` with status `failed`.

Do not change product code in this slice. If the installed program does not behave as listed,
stop and report the exact output instead of adjusting the expectation.

## Test plan

Slice 1's tests fail on main. Slice 2 is the end-to-end proof; it starts the installed program, so
run it outside any sandbox if a sandbox blocks subprocesses. Existing screening tests must pass.

## Look-ahead, determinism and import impact

No read path changes; `horizon_turnover` reads only signal rows at or before `t + horizon`, the
same rows the outcome already spans. Deterministic: no randomness. Imports unchanged in product
code; the tests import pandas and SciPy, already installed.
