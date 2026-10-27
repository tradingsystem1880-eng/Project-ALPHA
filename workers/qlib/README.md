# Project ALPHA isolated Qlib worker

This project is deliberately outside ALPHA's root uv workspace. It is the only environment that
contains Qlib or LightGBM. The root CLI exchanges canonical JSON/Parquet files with this process;
no model pickle or executable worker object crosses the boundary.

Pinned runtime:

- `pyqlib==0.9.7` (MIT), CPython 3.12 wheel;
- `lightgbm==4.6.0` (MIT), deterministic CPU execution only;
- `catboost==1.2.10` and `xgboost==3.4.1` / `xgboost-cpu==3.4.1` (Apache-2.0), CPU execution;
- `numpy==2.2.6`, `pandas==2.3.3`, and `polars==1.41.2` as worker-local data edges.

`uv.lock` resolves the complete 217-package worker and development graph. Qlib brings a large
diagnostic stack (including MLflow, Jupyter, CVXPY, and their transitive dependencies); none enters
the ALPHA root lock. The directly used upstream notices are preserved in
`THIRD_PARTY_NOTICES.md`. Project ALPHA still has no declared distribution license, so packaging or
redistributing the worker remains blocked on the repository-wide owner decision and a generated
full transitive notice bundle.

## Run

```bash
uv sync --project workers/qlib --locked
uv run alpha ml train EXCHANGE --mode real --no-sync --json
```

The worker builds a causal 158-column Alpha158-style matrix from the verified in-memory panel and
fits preprocessing statistics on each training fold only. Contract v1 retains the original Qlib
`LGBModel` recipe unchanged. Additive contract v2 selects `rank_ensemble_v1`: the same LightGBM
member and a Qlib ridge `LinearModel` (`alpha=1.0`, fixed) are combined by an equal-weight
cross-sectional percentile-rank average. Ensemble weights and ridge regularization are not tuned.
The canonical `score` remains in `predictions.parquet`; member scores, ranks, model hashes, and
disagreement are published separately as `ensemble_diagnostics.parquet`. Qlib Recorder data and
fitted model objects stay inside an ephemeral worker directory and are deleted when the process
exits.

### Additive tabular contract v3

Schema v3 selects `lightgbm`, `linear`, `catboost`, `xgboost`, or `double_ensemble` while
retaining the same Alpha158 inputs, one-session open-to-open target, close availability,
fold boundaries, purge/embargo, and canonical prediction fields. V1/v2 remain unchanged.
The Linear adapter supports `estimator: ols|ridge|lasso|nnls`: ridge alpha 1.0 is the default;
Lasso uses the fixed design preset alpha 0.01 when omitted, and OLS/NNLS require alpha zero.
These are explicit presets, not outcome-tuned or numerically/economically qualified choices.
Nonconverged linear fits fail; native linear algebra is limited to one thread. Numeric parameters
are bounded by
`schemas/request-v3.schema.json`. Device, seed, executable classes, arbitrary model arguments,
validation inclusion, and thread counts above eight cannot be supplied by requests.

`alpha-qlib-worker capabilities` reports installed dependency availability, versions and exact
failure reasons without network access or training. `available` means the locked dependency can
be imported; it does not establish data readiness, numerical qualification, economic evaluation,
or promotion eligibility. The accepted local stack remains Qlib 0.9.7, LightGBM 4.6.0 and
scikit-learn 1.9.0. The additive worker lock includes CatBoost 1.2.10 and XGBoost 3.4.1,
Graphviz Python 0.21 and Plotly 7.1.0 while preserving all 212 prior package versions. On Darwin
the XGBoost distribution is `xgboost`; Linux and Windows use `xgboost-cpu` to avoid CUDA/NCCL
dependencies. Installing both distributions is rejected as ambiguous. Missing, unqualified,
unsupported-platform and native import failures remain explicit; there is no model fallback.

The new registry packages have a persistent `tool.uv.no-build-package` guard: ordinary sync/run
commands cannot fall back to source compilation. CatBoost wheels cover macOS 11+ universal2,
Linux x86_64/aarch64 and Windows x86_64. XGBoost's macOS ARM wheel requires macOS 12+ (Intel
10.15+); its Linux CPU wheels require glibc 2.28+. Windows CPU wheels also support ARM64, but
CatBoost has no Windows ARM64 wheel. Architecture markers are not binary/OS qualification;
unsupported runtimes fail without a source build. CatBoost's standard Linux wheel bundles GPU
algorithms internally; this worker forces `task_type=CPU` and installs no CUDA/NCCL packages.

These versions were checked against official release/API/PyPI metadata on 2026-10-26.
CatBoost 1.2.10 includes NumPy 2 support and the later scikit-learn >=1.8 compatibility fixes.
XGBoost 3.4.1 is the latest published PyPI wheel: the newer GitHub 3.4.2 tag reports only Python
3.11 support changes, and its PyPI package endpoints were absent at inspection. No accepted
Qlib/NumPy/pandas/LightGBM/SciPy/scikit-learn version was upgraded.

Each schema-v3 fit uses the shared train-only imputation/normalization and a fresh Qlib model.
DoubleEnsemble keeps upstream sample reweighting and feature selection, fixes `decay=1.0`, seeds
and restores NumPy's random state, and orders the selected feature set by original feature order.
The CatBoost adapter confines Qlib's automatic GPU probe to CPU. XGBoost's fitted booster is
sliced to the validation-selected rounds before prediction, hashing, importance and reload. For
CatBoost/XGBoost schema-v3 diagnostics, `best_iteration` is the selected round count; the raw
`native_best_iteration_index` remains explicitly zero-based beside `selected_tree_count` and
`trained_round_count`. Native model text/JSON state is
roundtripped inside the worker and predictions must match at rtol/atol `1e-12`; no model pickle
crosses the exchange. Persistent model reuse remains unsupported: state is ephemeral.
CatBoost predictions pass the resolved native thread count explicitly. Both original and
reloaded XGBoost boosters and their prediction matrices receive the same explicit CPU/thread
settings; LightGBM-family reload predictions also receive the resolved thread count.

Portable diagnostics identify the selected recipe, resolved parameters, dependency versions,
installed upstream source hash, adapter source fingerprint, fold fits and roundtrip status.
Linear coefficients and CatBoost PredictionValuesChange are not represented as tree gain/split
importance. Schema-v3 signal
diagnostics contain IC/RankIC and conditional quantile returns; tied-score cross-sections are
excluded from quantile groups, with an explicit diagnostic state and empty groups for constant
scores. Portfolio economics require the canonical costed multi-asset `alpha ml replay` path. Unscheduled point-in-time membership remains
unsupported and current-membership warnings remain permanent. This is an adapter implementation,
not a full Qlib product, counterfactual gauntlet, or promotion qualification.

Daily panel rows and predictions are availability-stamped at the canonical session close
(`session_ts + 23h`), never at midnight. After import, `alpha ml replay EXCHANGE` validates the
complete exchange and executes one synchronized, long-only, top-quintile/equal-weight portfolio
across the frozen universe through ALPHA's canonical multi-asset replay engine with declared costs.
The resulting ALPHA metrics, decisions, orders, fills, portfolio state, and tear sheet are
authoritative for that replay; Qlib's own Recorder/backtest diagnostics are not.

This is still labeled `OOS replay validated — model not recomputed under counterfactual`. ALPHA does
not yet retrain every fold on randomized/counterfactual paths, so the replay is not a full ML
gauntlet and is not promotion-eligible. Single-asset ML equivalence is also not claimed.

## Gate

The [W11 engineering packet](../../docs/superpowers/plans/2026-10-26-qlib-w11-refit.md)
adds observed schema3 component provenance: raw fold scopes and label clocks, actual normalization
inputs/state, and native Linear/DoubleEnsemble fit, selection and reweighting links. Other recipes
are explicitly outside the initial W11 reference protocol. `tests/refit_harness.py` is a private,
closed synthetic-fixture diagnostic; it reuses the real worker and cannot admit research.
`alpha ml refit-plan` and `refit-status` verify frozen input/source identities without dispatching.
Execution traces, completed fits, renamed artifacts and verified reuse do not establish independent
observations, scientific acceptance or a component-fit allowance. Native/W06 source exists, but
Qlib-specific admission, charging units, ancestry/reuse and consumer runtime remain unqualified.
The reviewed statistical source is still unavailable. Counterfactual/promotion flags remain false.
See the dated packet for exact executed tests, protocol ceilings, evidence and remaining decisions.

```bash
cd workers/qlib
uv lock --check
uv sync --locked
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src tests
uv run pytest -q
```

Removal is bounded: delete `workers/qlib`, remove the root `alpha ml` projections, and delete
worker exchanges/control links. No root package dependency or run artifact needs migration.
