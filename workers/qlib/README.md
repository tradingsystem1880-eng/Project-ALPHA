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

## Inert W09 planning contracts

The CLI-owned [planning API](../../apps/alpha-cli/src/alpha_cli/ml_native_plan.py)
binds declared project/experiment/contract and request/panel/snapshot references to
`W09ProtocolV1` and an exact `W09ManifestV1` operation graph. V1 describes existing
LightGBM computation; v2 additionally describes the train-only ridge member and fixed
rank assembly. Assembly is not a learned fit, and operation counts are not approved
resource units or independent trials. These are declared references, not record lookups
or verified panels. The planning API adds no CLI command, native registry entry or dispatch.

The fingerprint covers the supported first-party worker package, schemas, project and
lock, including rank-ensemble code. Source reads are bounded and mutation-checked; this
does not qualify installed binaries or the native runtime. Readiness remains `BLOCKED`,
with execution/reuse/fitted-state verification false and observed work unknown. The
[bounded plan](../../docs/work/archive/2026-11/2026-11-01-w09-planning-contracts.md)
records limits and qualification requirements. This does not extend the separate W11
ridge/DoubleEnsemble reference protocol or change existing v1/v2 outputs/computations.

## W09 invocation observations

The existing private `run_real(..., _observation=FitInvocation())` diagnostic seam also
observes retained v1/v2 calls. Normalization, label transforms, LightGBM and train-only
ridge fitting retain their computations; prediction and fixed rank assembly are distinct
operations. Fits close only after returned state is observed, before prediction begins,
so later prediction/assembly failures retain genuine earlier observations. An absent
booster has no completed state observation. Original exceptions propagate. Later-fold or
publication errors still fail the invocation; existing per-artifact publication is not
an atomic transaction.

Explicit legacy observation requires canonical request bytes and rechecks request/panel/
lock identity before publication. V1/v2 serialized results and artifact sets are unchanged;
the detached `FitInvocation.snapshot()` stays in memory unless a caller separately saves
its diagnostics. It is not a new worker exchange artifact or durable accounting record.
The existing declarative diagnostic `fit_count` is not observed spend or a fit allowance.

`ml_native_plan.bind_worker_observations` joins complete diagnostic call sequences to
declared W09 component IDs. It checks request/fold/lock bindings, preprocessing and model
state links, train-only ridge inputs and current first-party dependency identity. Polars
member/prediction/diagnostic frames are hashed through their JSON representation, including
columns, row order, keys, lineage and scores. Assembly remains deterministic computation,
not another learned fit. Failure/partial snapshots remain inspectable but cannot pass the
complete structural binding check. Planned identities alone cannot pass it either.

Structural matching is not authentication or proof that calls occurred. Current-file
fingerprinting is distinct from the source/binaries actually used by a past invocation;
runtime identity remains `UNVERIFIED`. The older W11 source fingerprint has a different
domain and is not treated as the W09 dependency identity. Binding reports keep fitted-state
verification, durable accounting, execution, reuse and promotion false, with no approved
resource units or independent-trial count. ControlStore remains the durable authority;
there is no native registration, resource-policy change, retry/refund/reuse authorization
or research dispatch here. V3/W11 computation and reference graph classification stay
unchanged. See the [bounded observation plan](../../docs/work/archive/2026-11/2026-11-02-w09-component-observations.md).

## Durable diagnostic associations

The private `FitInvocation(checkpoint=..., checkpoint_scope=...)` option emits
canonical JSON checkpoints synchronously before and after observed v1/v2 calls.
The scope names one job, reservation, manifest and invocation. A caller must persist
the checkpoint before acknowledging it; missing entry acknowledgement prevents the
call. A lost completion acknowledgement preserves the completed observation and
stops continuation. Checkpoint delivery for unsupported/unbound invocations,
including v3, fails before fitted calls; ordinary v3 behavior remains unchanged.

`ControlStore.record_w09_diagnostic` associates these diagnostics with an existing
inert D1 reservation in the existing job journal. It rejects rule/native-owner jobs,
cross-scope records and conflicting or regressive deliveries. Exact duplicates are
idempotent. Delta writes and the job cursor commit together. `read_w09_diagnostic`
can recover the declared manifest from the initial journal entry without worker
files; incomplete calls stay unknown, and earlier completions survive later failure.
Planned IDs alone have no observed state. Existing attempt/run references remain
explicitly unverified; no run artifact verification follows from the association.

This is a local trusted-writer diagnostic mechanism, not execution authentication,
Qlib admission or proof that the reservation covers these fits. It creates no attempt,
changes no charge/refund/retry/reuse policy, and enables no native dispatch. The
current slice has isolated synthetic engineering tests. Its bounded delivery has an
absence-only private-suite exception: private coverage stays UNVERIFIED, while all
public checks, the 93% floor and independent final-tree review remain mandatory. See the [durable diagnostic plan](../../docs/work/archive/2026-11/2026-11-02-w09-durable-observations.md).

## Gate

The [W11 engineering packet](../../docs/work/2026-10-26-qlib-w11-refit/02-plan.md)
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

## Opt-in partial Alpha158 feature correction

Feature recipe version **1 remains the default**, with unchanged formulas and default request
bytes. Set `stage_config.ml.feature_recipe_version` to `2` when preparing a new experiment, or
use `{"name":"alpha158","version":2,"parameters":{}}` in a new exchange request. This is
independent of request envelope versions 1/2/3, which select model families. Older readers reject
v2 rather than downgrade it. Fake-worker output remains synthetic transport, not feature validation.

V2 is an **Alpha158-style 40-column correction**, not full native Alpha158 equivalence. Actual pinned
Qlib 0.9.7 operators compute MA, STD, VSTD, RANK, IMAX, IMIN, IMXD and WVMA at 5/10/20/30/60
sessions, including upstream partial-window behavior. The other 118 columns retain legacy formulas
and warm-up. VWAP0 remains the explicitly disclosed typical-price proxy; input has no vendor VWAP
or pre-panel history. Undefined NaNs remain missing. Source/dependency mismatches fail closed.
No provider initialization is needed for this feature calculation.

The full recipe is already in `config_hash`, which prediction readers enforce. Preserve request/
config and worker-lock identity alongside model hashes; do not reuse a model solely because its
feature names match. New worker-code fingerprints are genuine new implementations, including for
v1 executions, not changes to recipe-1 meaning. Historical results and frozen-source protocols are
not rewritten. See the [scope and verification plan](../../docs/work/2026-11-09-alpha158-versioned-correction/02-plan.md).

Service compatibility is narrower than data compatibility: upgrade the worker and typed web API
together for the new capability fields and v2 diagnostics. An old strict web service is not
qualified to consume a new worker's capability response. Updated web projections accept old
responses; the new correction field is omitted from legacy v1 tear-sheet JSON. Frozen
legacy seven-file worker inventories remain plannable only for feature v1; v2 requires both new
modules in the complete fingerprint-bound inventory. Current-worker code does not satisfy an old
frozen-code hash merely because the recipe version is still 1.

Operator checks compare the same supplied row-indexed series. They do not establish Qlib
provider/calendar/corporate-action or full-handler parity. Existing input alignment is unchanged.
