# Acceptance tests

Visible behaviour tests of the statistics and gauntlet contracts in `CLAUDE.md`. Each test
states a documented rule as behaviour, not as an implementation detail, so a change that
relaxes a threshold or flips a comparison fails here:

- `test_holdout_gauntlet_gates.py`: gauntlet gates (walk-forward needs a finite Sharpe, the
  null gate is conservative across tiers, a flagged low-fidelity Tier-1 is advisory, the
  bar-permutation tier is never rescued, the bootstrap CI needs a strictly positive lower
  bound) and the verdict bands.
- `test_holdout_thresholds_and_execution.py`: DSR and PBO pass thresholds, walk-forward
  embargo geometry, decide at close t and fill at the open of t+1, fees as notional × bps / 10⁴.
- `test_holdout_benchmark_defects.py`: a non-finite close fails loud with a typed data error;
  cash-affordability rejections are disclosed in the validation manifest.

They run in every normal test run, in the fast tier, and in every `scripts/gate.py check`.
Anyone may read and extend them. The file names and the `holdout` marker are from their first
home, a hidden suite that was never activated; see
[ADR-0041](../../docs/adr/0041-no-hidden-test-suite.md).
