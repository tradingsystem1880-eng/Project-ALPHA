# Four-family Monte Carlo: purposes and interpretation

ALPHA retains **all four families**. Use this overview to choose which explanation to read and
which assumption to inspect, not which family to omit. They ask complementary questions about
scenario/path risk. None establishes an edge, repairs selection bias, or grants trading authority.

The authoritative stage and review policy is
[ADR-0029](../../adr/0029-four-family-monte-carlo-validation.md); the
[four-family specification](../../superpowers/specs/2026-08-12-four-family-monte-carlo-validation.md)
defines the implementation contract. These pages explain the current single-symbol daily lane;
they do not extend it to intraday, Qlib promotion, or joint multi-asset scenarios.

## Start with the question

| Family guide | Question answered | Object simulated | Main assumption to inspect |
| --- | --- | --- | --- |
| [IID empirical](iid-empirical.md) | What happens if observed account-return outcomes recur in different sequences and frequencies? | OOS account returns sampled with replacement | Observed marginal outcomes remain representative; dependence is discarded |
| [Causal-volatility Markov](causal-markov.md) | How does persistence in calm/volatile conditions change path risk? | State-conditioned account returns and a two-state chain | The observed-state transition/emission model remains useful |
| [Student-t log returns](student-t.md) | How sensitive are outcomes to parametric tails beyond the finite observed sample? | IID fitted log-account returns, then exponentiated | The fitted tail model is appropriate and numerical outputs remain usable |
| [Kronos market paths](kronos-replay.md) | How does the unchanged strategy execute on model-generated OHLCV? | Synthetic market tails followed by fresh strategy/engine execution | The generator, conditioning context and execution model describe useful scenarios |

The three classical families use the completed validation run's exact OOS **account** returns,
not a list of trade profits or raw market returns. Observed sizing, exposure, costs, dividends and
mark-to-market effects are already embedded. Resampling those returns does not recompute those
effects for a new market. Kronos instead regenerates market inputs and recomputes strategy behavior.
Fitting a scenario distribution to completed OOS observations does not create another independent
out-of-sample test.

## Read the outputs

All four use the [same path metrics](../../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py#L268):

| Output | Meaning and units |
| --- | --- |
| Terminal return q05/q50/q95 | Final normalized equity minus 1; decimal total return over the path, not annualized return or currency |
| Maximum drawdown q50/q95 | Positive decimal peak-to-trough depth, measured from normalized starting equity 1 |
| Longest loss streak q95 | Consecutive strictly negative account-return periods; zero breaks a streak; these are not losing trades |
| Loss probability | Fraction of simulated paths with terminal return below zero |
| Ruin probability | Fraction reaching at least 50% drawdown in the current CLI lane; this is not necessarily bankruptcy |
| Wilson interval | Finite simulated-event counting uncertainty, conditional on the fitted generator |

For example, a decimal drawdown depth of `0.20` means 20%. This is a unit illustration, not a
measured strategy result. The terminal q05–q95 band contains the central **90%** of simulated
outcomes; it is not a 95% confidence interval. Classical `--confidence` defaults to 0.95 and
controls Wilson intervals, not the fixed quantile levels. Those intervals do not include parameter
uncertainty, structural model error, or establish real-world probability calibration. The summary
does not report expected wealth, Sharpe, CAGR or expected shortfall.

Each family receives its own risk grade and status. The stage does not majority-vote. Missing,
invalid or non-estimable required evidence fails; valid warnings require the exact-evidence review
described in ADR-0029. Monte Carlo diagnostics can exist after failed robustness without making
robustness pass. A favorable path-risk summary cannot replace randomized-price no-edge tests,
governed confirmation, or sealed holdout requirements.

## Run and reproduce

```text
alpha monte-carlo classical --from-run VALIDATION_RUN_ID
alpha monte-carlo kronos --from-run VALIDATION_RUN_ID --forecast-eval-run EVALUATION_RUN_ID
alpha suite run PROJECT EXPERIMENT monte_carlo
```

These are command forms, not commands executed by reading this guide. The classical command
publishes three families together; Kronos remains a separate heavyweight run. Defaults are 10,000
paths per classical family and 128 Kronos paths. Prefer the canonical suite for the linked source
validation and evaluation selection.

Reproduction requires the exact source validation/snapshot, cutoff, normalized configuration,
semantic seeds and generator/dependency versions, not just a master seed. Kronos adds model and
tokenizer identities/revisions, device, sampling controls and forecast-evaluation hashes. Preserve
immutable manifests and raw artifacts. Figures are derived views, not replacement evidence.

## Evidence versus an unexecuted claim

The linked source and public tests make implementation behavior inspectable. Synthetic test inputs,
mocked failures and the FakeForecaster integration are identified on each family page. They do not
establish a real strategy's edge or the quality of real Kronos weights. This guide reports no
measured real-market performance or newly executed real-model experiment.

For observed results, inspect the selected run's `observed_oos.parquet`, `paths.parquet`,
`path_metrics.parquet`, manifest and report; inspect regime or model diagnostics as applicable.
The [artifact contract](../../../apps/alpha-cli/src/alpha_cli/_artifacts.py#L170) enumerates required
files. Confirm hashes, execution status, fitted period and disclosed assumptions before citing a
number. A family name, generated figure or command example is not an execution receipt.

Useful shared checks are
[path summaries and invalid-input tests](../../../tests/unit/test_path_montecarlo.py),
[classical publication and fake-Kronos engine integration](../../../tests/integration/test_monte_carlo_cli.py),
and [causality/projection guards](../../../tests/bias_guards/test_monte_carlo_causality.py).
