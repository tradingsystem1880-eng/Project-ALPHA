# IID empirical account-return bootstrap

[Four-family overview](README.md) · [outputs and units](README.md#read-the-outputs)

## Purpose and question

Ask: **if outcomes like the observed OOS account returns recur, how sensitive is the account to
their sequence and frequency?** This is the simplest reference for the other path-risk families.
It preserves the finite observed return values, not their original dependence or order.

## Inputs, fitted period and mechanism

The CLI converts the source validation's exact OOS equity series into simple account returns.
The complete observed OOS stream supplies the empirical distribution; there is no training-only
fit or new held-out sample. The CLI requires at least 20 OOS returns. Each path independently draws
uniformly **with replacement**, defaulting to 10,000 paths with the observed return-count horizon.

This is not just shuffling a fixed list. Repeated draws and omitted observations change return
frequencies and therefore terminal wealth. A pure permutation of the same simple-return multiset
would leave its compounded terminal wealth unchanged, although its drawdown could change.

## Outputs and interpretation

`iid_empirical` appears in the classical run's raw paths, per-path metrics, summary and report.
Terminal returns and positive drawdown depths are decimal fractions; streaks count account-return
periods. Loss and drawdown-ruin proportions have Wilson intervals; see the shared output definitions.

Inspect downside quantiles, drawdown depth and loss streaks rather than treating a favorable
median as a profitability test. The observed OOS path is a comparator, not a promised future path.

## Assumptions, limitations and failure modes

- Draws are IID. Serial correlation, volatility clustering and state persistence are removed.
- The finite sample cannot supply unseen return magnitudes. A short or selected OOS history can
  understate risks; more paths reduce simulation counting noise, not this sampling limitation.
- Resampled net account returns retain previously realized costs and exposure effects. Signals,
  fills, position sizing and costs are not recomputed against a new market.
- Nonfinite returns, returns at or below −100%, malformed arrays and invalid simulation controls
  are rejected. Extreme compounding can still exceed floating-point range.

This family measures conditional scenario risk, not edge or a no-edge null.

## Reproducibility and evidence

Retain the source equity/snapshot hashes, return horizon, path count, dependency/generator versions
and master seed. The CLI derives the distinct `monte_carlo.iid` semantic seed. Run the classical
command from the [overview](README.md#run-and-reproduce); do not substitute trade returns.

Implementation: [`empirical_return_paths`](../../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py#L88)
and [`classical`](../../../apps/alpha-cli/src/alpha_cli/monte_carlo_cmds.py#L355).
Representative public tests:

- [`test_empirical_paths_are_seeded_draws_with_replacement`](../../../tests/unit/test_path_montecarlo.py#L23): controlled return values and repeated seed, not market forecasting.
- [`test_classical_monte_carlo_publishes_three_auditable_families`](../../../tests/integration/test_monte_carlo_cli.py#L25): generated test data and auditable publication.
- [`test_classical_monte_carlo_is_byte_stable`](../../../tests/integration/test_monte_carlo_cli.py#L86): repeatability in the tested environment.

These tests describe executable coverage. Actual strategy outcomes require the selected run's
verified artifacts; this page supplies no executed real-market result.
