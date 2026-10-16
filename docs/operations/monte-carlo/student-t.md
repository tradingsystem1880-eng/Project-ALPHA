# Student-t log-account-return simulation

[Four-family overview](README.md) · [outputs and units](README.md#read-the-outputs)

## Purpose and question

Ask: **how sensitive is account path risk to heavy-tailed outcomes beyond the observed sample?**
Unlike empirical resampling, this parametric family can generate previously unseen magnitudes.
It is fitted scenario analysis, not a zero-drift/no-edge null or evidence of profitability.

## Inputs, fitted period and mechanism

The complete source validation OOS account-return stream is transformed with `log1p`.
Location is its sample log-return mean; scale matches log-return sample standard deviation
(`ddof=1`) through unit-variance Student-t draws. Degrees of freedom use a sample excess-kurtosis
heuristic: `clip(4 + 6 / excess, 5, 250)` when excess is positive, otherwise 250. This is not
maximum-likelihood estimation. Nothing is fitted exclusively on the training prefix.

The generator draws IID log returns and maps them back with `expm1`. Default output is 10,000
paths with the source OOS return horizon. Fitted log-return moments do not imply preservation of
the simple-return mean. Serial dependence, volatility clustering and skewed log tails are not
modeled by this symmetric IID Student-t assumption.

## Outputs, units and interpretation

`student_t` supplies decimal terminal-return and drawdown quantiles, period-count loss streaks,
and Wilson loss/ruin intervals. Compare these conditional scenario summaries with the empirical
families to expose dependence on tail assumptions. Neither finite path counts nor a favorable
median validates the distribution's real-world tails.

**Exponential-moment caveat:** a nondegenerate Student-t log return with finite degrees of freedom
has no finite positive exponential moment. Its polynomial positive tail is overwhelmed by the
exponential wealth transformation. Consequently, this model does not have finite population
expected terminal wealth, even when its log-return mean and variance exist. The zero-scale
degenerate case is an exception. Finite simulation quantiles and event proportions are distinct
from a population mean; a finite Monte Carlo average would not establish finite expected wealth.
The current common summary does not report that expectation. The mathematical inference follows
from the [Student-t density](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html).

## Numerical limits and failure modes

Mathematically `expm1(y) > -1` for finite `y`; this is not an unconditional floating-point guarantee.
Very large draws can overflow `expm1`; the wrapper checks nonfinite transformed returns, but a
runtime warning can surface first under warnings-as-errors. Very negative draws can round to
exactly −1 and be rejected by downstream return validation.

Even finite valid step returns can overflow compounded equity. `path_metric_arrays` has input
validation but no dedicated post-`cumprod` finiteness check. Do not treat finite inputs as a
numerical certificate, interpret unusable derived statistics as tail estimates, or silently clip,
drop or redraw extreme paths to obtain a favorable report. Preserve failures for diagnosis.
See [NumPy's transformation definition](https://numpy.org/doc/stable/reference/generated/numpy.expm1.html).

## Reproducibility and evidence

Retain OOS input/configuration hashes, horizon, path count, versions and master seed; the derived
namespace is `monte_carlo.student_t`. Use the classical command in the
[overview](README.md#run-and-reproduce).

Implementation: [`student_t_return_paths`](../../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py#L107),
[`_infer_df` and `student_t_paths`](../../../packages/alpha-validation/src/alpha_validation/montecarlo.py#L109),
and [compounding](../../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py#L268).
Public [path tests](../../../tests/unit/test_path_montecarlo.py) include
`test_student_t_account_return_paths_are_seeded_and_match_source_horizon` and
`test_student_t_wrapper_rejects_non_finite_generator_output`. The latter injects infinity; it does
not test every finite-input exponential or compounding overflow. The generic heavier-tail test
uses explicit `df=4.5`, not the wrapper's inferred floor of 5.

These controlled tests are not a fitted real-market tail assessment. This page reports no newly
executed strategy performance or validated population expected wealth.
