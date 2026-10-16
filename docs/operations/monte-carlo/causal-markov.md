# Causal-volatility Markov bootstrap

[Four-family overview](README.md) · [outputs and units](README.md#read-the-outputs)

## Purpose and question

Ask: **how would persistent calm/volatile conditions change account path risk?** The family adds a
two-state dependence model to empirical return resampling. It is an **observed-state Markov
bootstrap, not an HMM**: no hidden-state estimation, EM/Baum–Welch fitting, Viterbi decoding or
posterior latent-state probabilities are used.

## Inputs, fitted periods and mechanism

The inputs are the exact OOS account returns plus market bars aligned to their timestamps.
Two different estimation periods matter:

1. The classifier computes trailing market close-return volatility, defaulting to 63 sessions,
   using only returns known before the classified bar. Its calm/volatile boundary is the median
   available volatility inside the first training prefix and stays frozen. Volatility strictly
   above the boundary is volatile; equality is calm.
2. Emission pools, the 2×2 transition matrix and initial-state prevalence are estimated from the
   **complete observed OOS** return/state sequence. They are not training-fitted parameters.

Adjacent state counts include self-transitions; each row is normalized without smoothing.
Simulated initial states follow OOS state prevalence, not the final observed state. A simulated
chain then chooses a state each period and draws an account return with replacement from that
state's empirical pool. Draws within a state are IID. Defaults are 10,000 paths over the observed
OOS return horizon.

## Outputs and interpretation

`regime_switching` supplies the common decimal terminal-return/drawdown summaries, period-count
loss streaks and Wilson loss/ruin intervals. Classical artifacts also retain emissions, state
support and transition diagnostics. Compare them with IID to investigate sensitivity to this
particular persistence model, not to identify the true economic market regime.

## Assumptions, limitations and failure modes

The chain is first-order, two-state and fixed over each simulation. It cannot represent every
regime, structural break or within-state dependence; empirical emissions cannot invent unseen
magnitudes. “Causal” refers to the prior-known volatility labels, not causal identification or a
forward-calibrated distribution. Fitting OOS transitions remains retrospective path-risk analysis.

By default, **each state** needs 20 OOS emissions and 10 total outbound transitions. This is not
10 transitions in every matrix cell. Insufficient support produces `not_estimable`, zero regime
paths and unavailable statistics. Other classical outputs remain available, but the run fails;
omitting this family is not a remedy. Missing causal history or timestamp alignment also fails.

## Reproducibility and evidence

Retain source bars/equity hashes, training size, volatility window, frozen threshold, support
floors, OOS labels, matrix, path count and versions. The CLI derives `monte_carlo.regime` from the
master seed. Use the classical command in the [overview](README.md#run-and-reproduce).

Implementation: [`_causal_regime_states`](../../../apps/alpha-cli/src/alpha_cli/monte_carlo_cmds.py#L216)
and [`regime_switching_return_paths`](../../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py#L129).
Representative public tests:

- [`test_regime_paths_recover_persistent_state_emissions`](../../../tests/unit/test_path_montecarlo.py#L35): constructed states and emissions, not inferred economic regimes.
- [`test_future_bars_cannot_change_frozen_regime_labels_or_threshold`](../../../tests/bias_guards/test_monte_carlo_causality.py#L33): future-poison protection.
- [`test_classical_non_estimable_regime_publishes_fail_contract`](../../../tests/integration/test_monte_carlo_cli.py#L120): published failure rather than a silently missing family.

These are controlled behavioral checks, not evidence that two states describe a real market.
Observed outcomes require the run's verified diagnostics; this page supplies no executed market
result or evidence of edge.
