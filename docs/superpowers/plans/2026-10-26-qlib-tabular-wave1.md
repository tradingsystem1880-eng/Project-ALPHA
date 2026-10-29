# Qlib tabular research, first wave

**Delivery state:** Completed local implementation and bounded runtime checks — delivery integration and acceptance pending; final review/full-gate outcome is recorded separately below.

Baseline: `integration/project-alpha-pr81-88-qualified-20261024`, exact commit
`bc5b58351cc334d36112167c9463a80184411cc6`. Candidate branch:
`codex/qlib-tabular-wave1-20261026`. The primary checkout is dirty and read-only for this task.

The user-approved wave comprises LightGBM, Linear, CatBoost, XGBoost and DoubleEnsemble.
The local source authority is [ADR-0016](../../adr/0016-isolated-qlib-worker.md), the
[existing worker spec](../specs/2026-07-19-workstation-v3-qlib-worker-design.md), and the
explicit task instruction. Initially no expanded tabular plan or downloaded reviewed patch
was found in the tracked context/planning routes. The parent subsequently supplied verified
planning evidence from Library `libfile_52e745af42b48191b032a5eeea0a23d7`, version 1,
section 9, page 9 of 21: the first wave requires extending the bridge and declaring Linear
OLS/ridge/lasso/NNLS, devices and target semantics. The complete document has **not** been
materialized locally; this supplied passage closes the first-wave scope-authority gap only.
It does not establish upstream compatibility or scientific qualification. Qlib remains pinned at `0.9.7`;
upstream inspection is pinned separately to `da920b7f954f48ab1bb64117c976710de198373e`.
All five CPU backends now execute locally on tiny synthetic fixtures, including all four Linear variants. This is bounded local engineering evidence; data/discovery approval, numerical transportability, empirical economics and promotion remain unqualified. The full inventory denominator remains frozen to upstream
`54355232463878d2eebb91fe0ee5fa7fa1f5976c` and its enumerated official recipes;
unavailable/incompatible entries remain visible blockers. The existing fixed rank ensemble
with ridge is separate from upstream DoubleEnsemble.

```json
{
  "schema_version": 1,
  "title": "Qlib tabular research first wave",
  "context": "Extend the isolated Qlib exchange workflow from v1 LightGBM and v2 fixed rank ensemble to additive v3 tabular model selection, preserving historical readers, membership guards and canonical engine economics.",
  "assumptions": [
    {
      "statement": "The delivery baseline is bc5b58351cc334d36112167c9463a80184411cc6, not main or the dirty primary checkout.",
      "verified_by": "Authorized source fetch and isolated worktree HEAD verification on 2026-10-26."
    },
    {
      "statement": "Qlib 0.9.7 and LightGBM 4.6.0 are the worker pins; CatBoost and XGBoost were absent at the delivery baseline; the additive follow-up preserves every old pin while adding the declared optional runtime versions.",
      "verified_by": "workers/qlib/pyproject.toml, uv.lock and installed distribution metadata."
    },
    {
      "statement": "No current request carries a point-in-time membership schedule.",
      "verified_by": "Existing strict request field sets and 2026-10-23 membership guard plan."
    },
    {
      "statement": "The first wave includes Linear OLS/ridge/lasso/NNLS, devices and target semantics; the complete inventory denominator is upstream54355232463878d2eebb91fe0ee5fa7fa1f5976c.",
      "verified_by": "Parent-verified supplied planning evidence: Library libfile_52e745af42b48191b032a5eeea0a23d7 v1 section9 page9/21; full document not materialized."
    }
  ],
  "alternatives_considered": [
    "Add schema3 rather than reinterpret historical schema1 or schema2 models.",
    "Reuse Qlib adapters and existing causal feature/fold pipeline rather than introduce a parallel model framework or backtester.",
    "Expose missing optional dependency states rather than install incompatible stacks or count mocks as model coverage."
  ],
  "pre_mortem": [
    "An upstream adapter can concatenate validation into training or choose GPU; inspect exact pinned APIs and enforce the declared bounded CPU recipe.",
    "A comparison can silently mix panels, folds, seeds or cost assumptions; require one frozen comparison identity and identical prediction keys.",
    "A new schema can bypass unscheduled membership guards or hide behind a narrow web response union; test ingress, worker and existing response serialization.",
    "Disk pressure and existing macOS uv sandbox crashes can prevent aggregate checks; preserve exact failures and report unverified gates."
  ],
  "slices": [
    {
      "title": "Versioned model contracts and capability states",
      "verify": "Root contract and worker parameter/capability tests",
      "expected": "v1/v2 unchanged; v3 validates bounded backend-specific parameters; missing/unsupported backends fail explicitly",
      "rollback": "Revert only the task diff; preserve all historical exchanges",
      "status": "done"
    },
    {
      "title": "Fold-local real adapters",
      "verify": "Worker real synthetic tests, determinism and temporal/normalization boundary checks",
      "expected": "Available models really fit and predict through Qlib with hashes and resolved parameters; unavailable optional models remain unverified",
      "rollback": "Revert adapter changes only; no artifact rewrite",
      "status": "done"
    },
    {
      "title": "CLI selection, comparison and existing web hooks",
      "verify": "Focused CLI comparison and web serialization regression tests plus API generation/types",
      "expected": "Model selection produces a new immutable request; comparable predictive diagnostics bind exact input/result lineage; schema3 renders through existing result paths",
      "rollback": "Revert additive commands/response variants; preserve existing APIs",
      "status": "done"
    },
    {
      "title": "Independent review, fixes and final evidence",
      "verify": "Astra review, focused regression, lint/types/import and canonical full gate",
      "expected": "Fix and retest findings; record exact tested candidate and failures without claiming acceptance",
      "rollback": "Leave local candidate and evidence available for review; no push/PR/merge",
      "status": "done"
    },
    {
      "title": "Qualify compatible optional backends without changing existing pins",
      "verify": "Zero-upgrade copied lock resolution; actual CatBoost/XGBoost two-fold causality, reload, determinism, resource/failure tests; final review and aggregate receipts are separately linked below.",
      "expected": "All five backends execute on tiny local fixtures; CPU-only package markers; no original dependency version changes; remaining scientific/platform qualification stays explicit",
      "rollback": "Preserve qualified checkpoint and new failed evidence; remove only additive optional runtime changes if they fail acceptance",
      "status": "done"
    }
  ],
  "tier_impact": [
    "determinism",
    "bias"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/context/README.md",
    "docs/context/alpha-quant-platform.md",
    "workers/qlib/README.md",
    "docs/superpowers/plans/2026-10-26-qlib-tabular-wave1.md"
  ],
  "out_of_scope": [
    "RD-Agent and control-store admission/accounting",
    "real market acquisition and D2/D3 data",
    "provider/LLM calls",
    "paper/live orders",
    "dependency upgrades",
    "alternate economics engine",
    "GitHub push/PR/merge/deployment"
  ],
  "files": [
    "workers/qlib",
    "apps/alpha-cli/src/alpha_cli/ml_contract.py",
    "apps/alpha-cli/src/alpha_cli/ml_cmds.py",
    "apps/alpha-cli/src/alpha_cli/ml_compare.py",
    "apps/alpha-web/src/alpha_web/api/ml.py",
    "tests/unit/test_ml_contract.py",
    "tests/unit/test_ml_compare.py",
    "tests/integration/test_ml_cli.py",
    "tests/unit/test_web_ml.py",
    "workers/qlib/pyproject.toml",
    "workers/qlib/uv.lock",
    "workers/qlib/tests/test_optional_backends.py",
    ".claude/rules/alpha-cli.md",
    "docs/ARCHITECTURE.md"
  ]
}
```

The import DAG is unchanged: models and pandas stay inside the isolated worker. Existing
causal trailing features, session-close availability, label-boundary gaps, train-only
preprocessing and fresh models per fold apply to every new recipe. Seeds and CPU budgets
are bounded and recorded. Comparisons are predictive diagnostics, not model selection
authorization or evidence of net profitability; economics continue through canonical ALPHA
replay with explicit costs. Discovery-period approval remains pending.

The existing [context index](../../context/README.md) and
[Software Team map](../../context/software-team.md) remain the handoff routes. No new
documentation hierarchy is introduced. Source handoff downloads that have not materialized
are not integrated source. Planned, implemented, tested, integrated and accepted remain
separate states; final receipts and remaining work will be appended here.

Qualification for each first-wave recipe records source/module/lock, inputs, target/horizon,
temporal semantics and data requirements, train/predict/reload lifecycle, device, measured
peak memory, determinism/tolerance policy and tests. The states **listed**, **adapter implemented**,
**runtime executable**, **data ready**, **numerically qualified**, **economically evaluated**
and **promotion eligible** are separate. Tiny synthetic folds can establish bounded runtime
behavior, never market-data readiness or economic/promotion qualification. Tests cover finite
aligned predictions, train-only transforms, unavailable-outcome perturbations, complete-horizon
split gaps, state/reload parity where supported, artifact lineage, cancellation and resources.
Process-cumulative RSS must be labeled as such, not presented as an isolated per-model peak.
IC, turnover, concentration and net canonical replay retain distinct meanings.

## Recipe record and qualification ledger

All eight entries below are **listed** and have a selectable adapter in this local candidate.
None is integrated or accepted by this record. All share worker lock
[`workers/qlib/uv.lock`](../../../workers/qlib/uv.lock), causal Alpha158-style OHLCV inputs
(20–512 aligned symbols, at least 756 sessions), and the exact target
`open(t+2) / open(t+1) - 1`, cross-sectionally normalized for fitting. Prediction origin is
close t (`session_ts + 23h`), entry target is open t+1 and the label finishes at open t+2.
The final target without its exit open is omitted; train/validation boundary gaps preserve
the entire outcome horizon. Membership remains current-membership with a permanent warning;
unscheduled point-in-time membership is rejected. Discovery-period approval and real data
readiness remain pending for **every** entry.

| Recipe | Runtime module/class in Qlib 0.9.7 | Device | Runtime evidence | Data ready | Numerically qualified | Economically evaluated | Promotion eligible |
|---|---|---|---|---|---|---|---|
| LightGBM | `qlib.contrib.model.gbdt.LGBModel` | bounded CPU | real synthetic folds | synthetic only | bounded checks; broader qualification pending | no | no |
| Linear OLS | `qlib.contrib.model.linear.LinearModel`, `estimator=ols` | CPU, native thread limit 1 | real synthetic fit | synthetic only | bounded checks; broader qualification pending | no | no |
| Linear ridge | same, `estimator=ridge`, default alpha 1 | CPU, native thread limit 1 | real synthetic folds | synthetic only | bounded checks; broader qualification pending | no | no |
| Linear lasso | same, `estimator=lasso`, fixed default alpha 0.01 | CPU, native thread limit 1 | real synthetic fit; convergence failure guard | synthetic only | bounded checks; broader qualification pending | no | no |
| Linear NNLS | same, `estimator=nnls` | CPU, native thread limit 1 | real synthetic fit | synthetic only | bounded checks; broader qualification pending | no | no |
| CatBoost | `qlib.contrib.model.catboost_model.CatBoostModel`, native1.2.10 | bounded CPU | real macOS ARM synthetic folds/reload | synthetic only | bounded checks; broader qualification pending | synthetic canonical replay only | no |
| XGBoost | `qlib.contrib.model.xgboost.XGBModel`, native3.4.1 | bounded CPU | real macOS ARM synthetic folds/reload | synthetic only | bounded checks; broader qualification pending | synthetic canonical replay only | no |
| DoubleEnsemble | `qlib.contrib.model.double_ensemble.DEnsembleModel` | bounded CPU | real synthetic member fits | synthetic only | bounded checks; broader qualification pending | no | no |

Source links are the official [Linear inventory implementation](https://github.com/microsoft/qlib/blob/54355232463878d2eebb91fe0ee5fa7fa1f5976c/qlib/contrib/model/linear.py)
and runtime-reference [LightGBM](https://github.com/microsoft/qlib/blob/da920b7f954f48ab1bb64117c976710de198373e/qlib/contrib/model/gbdt.py),
[Linear](https://github.com/microsoft/qlib/blob/da920b7f954f48ab1bb64117c976710de198373e/qlib/contrib/model/linear.py),
[CatBoost](https://github.com/microsoft/qlib/blob/da920b7f954f48ab1bb64117c976710de198373e/qlib/contrib/model/catboost_model.py),
[XGBoost](https://github.com/microsoft/qlib/blob/da920b7f954f48ab1bb64117c976710de198373e/qlib/contrib/model/xgboost.py)
and [DoubleEnsemble](https://github.com/microsoft/qlib/blob/da920b7f954f48ab1bb64117c976710de198373e/qlib/contrib/model/double_ensemble.py).
The installed distribution/module SHA-256 and adapter source fingerprint are recorded by
capabilities/results; an upstream reference is not a claim that wheel bytes match a different
inventory revision. The official full inventory denominator is unchanged, not reduced to
these eight local recipes.

Lifecycle for executable entries: fresh Qlib model per fold → finite index-aligned OOS
prediction → native JSON/model-text state roundtrip inside the worker → portable hashed
JSON/Parquet exchange. Reload parity uses `rtol=atol=1e-12`; reproducible repeats compare
exact scores/model hashes on this locked CPU environment. Persistent fitted-model reuse is
unsupported; model objects never cross the process boundary. CatBoost/XGBoost lifecycle paths are now exercised locally after the bounded additive lock review; Linux/Windows execution remains unverified. Per-recipe peak RSS
and subprocess duration are local runtime evidence, not deterministic artifacts or universal
memory guarantees. Linux BLAS/device behavior remains a separate qualification lane.

## Use and evidence route

```sh
alpha ml capabilities --json
alpha ml prepare SPEC.json PANEL.parquet NEW_EXCHANGE --model linear --parameters-json '{"estimator":"ridge","alpha":1}' --worker-lock workers/qlib/uv.lock --json
alpha ml train NEW_EXCHANGE --mode real --no-sync --json
alpha ml import NEW_EXCHANGE --json
alpha ml compare EXCHANGE_A EXCHANGE_B --output NEW_COMPARISON.json --json
```

Comparisons require the same frozen panel, snapshot, folds, seed, costs, membership, exact
prediction keys and worker source/version lineage. They bind the captured request/result/
prediction hashes, recheck source stability, and publish atomically; identical retries verify
existing bytes. Fake results remain labeled fake and cannot be mixed with real results.
Score units differ across recipes; comparison output selects no winner and grants no authority.
The existing ML Research selector and result/tear-sheet views relay the same CLI contracts.

Local reproducibility evidence is retained under
[`.alpha/state/qlib-tabular-wave1/`](../../../.alpha/state/qlib-tabular-wave1/), including
initial failures, synthetic exchanges, comparison bytes and final check logs. These ignored
local receipts are supporting evidence, not committed release artifacts. The canonical gate
retains its own component receipts under `.alpha/state/`; final response names the final
tested tree and all remaining gates. Source index → this plan → code/tests/evidence is the
handoff path. Update the recipe states only from executed evidence, then complete optional
dependency acceptance, numerical/data qualification and canonical economic evaluation as
separate next actions; acceptance never follows from a capability listing.


## First-checkpoint bounded evidence, 2026-10-26 (preserved history)

The final focused root ML regression passed **269 tests** (30.90 s), covering contracts,
selection/comparison, exporter/boundary/isolation, canonical CLI replay, future-poison guards,
web responses and public seams. The isolated worker suite passed **48 tests** (30 upstream
warnings retained); frontend unit coverage passed **420 tests**, and the canonical focused
ML browser replay passed **24 cases** across minimum/reference/wide viewports. The two changed
macOS ML screenshots were visually inspected and replayed; corresponding Linux screenshots
remain unverified and require their own regeneration/qualification lane. Ruff, focused mypy,
13 import contracts, API generation/freshness, generated authority inventory and plan/manual
checks passed in their recorded scopes. These are bounded checks, not a full acceptance stamp.

Six separate frozen-source worker processes each fit the 15,120-row synthetic fixture and
published **2,420 finite aligned predictions**. Every state roundtrip passed. The comparison
artifact has identity `a8151afbf33ab6c183d12ec6c3532d0c2e53c9e80dc2c7a55586d65bdd1114fd`
and six candidates sharing source fingerprint
`3c562b258ba164cbbd7d98e5d064edafb6b4489af6478eac0edb67e0fd858635`.

| Recipe process | Peak RSS bytes (includes imports and fitting) | Duration seconds |
|---|---:|---:|
| LightGBM | 609402880 | 6.16 |
| Linear OLS | 621166592 | 4.24 |
| Linear ridge | 621707264 | 4.32 |
| Linear lasso | 621576192 | 4.31 |
| Linear NNLS | 620183552 | 4.30 |
| DoubleEnsemble | 655228928 | 5.40 |

The existing canonical multi-asset engine replayed the synthetic ridge exchange for 121 OOS
periods with the frozen 1 bps fee and 2 bps slippage. Run `76c5908940f6e9a5` records finite
returns and reconciled execution, with `counterfactual_refit=false`, null validation not run,
and `promotion_eligible=false`. This is synthetic integration evidence, not an empirical
profitability result or qualification of other recipes. No discovery approval or D2/D3 data
was consumed. The other five real smoke recipes were not economically evaluated.

Independent Astra review reproduced and required correction of:

- **AR-001, high:** comparison validation/hashing race. Capture hashes, bind canonical returned
  objects, recheck every input artifact and require real-v3 provenance; replacement regression passes.
- **AR-002, high:** finite Lasso scores could hide nonconvergence. Convergence warnings now fail
  the fit; the real ill-conditioned regression passes.
- **AR-003, medium:** Lasso's shared alpha 1 default produced a degenerate ranking. Its declared
  preset is now 0.01; tied cross-sections are excluded from quantile bins and the exact reason/counts
  reach the existing UI. This fixed preset was not selected by optimizing fixture performance.
- **Source stability:** capture adapter sources before fitting and recheck before publication;
  injected source drift fails without publishing completion.
- **Resources:** set native worker thread limits before import and use a one-thread native context
  for Linear. Hardware-specific Linux behavior remains unqualified.

The reviewer independently reran the closure tests. Its final tree-bound record and the canonical
full-gate attempt are retained in the local evidence directory. Until those receipts are checked,
this plan does not claim full-gate acceptance. Initial failing tests and environment failures are
preserved there. No authentic private engineering suite has been established; seed tests are not
private coverage and no waiver is claimed.

Next cohesive work: qualify this exact local tree through the remaining aggregate/Linux lanes,
then accept one compatible optional backend lock at a time and execute its real lifecycle,
resource and numerical qualification. Data/discovery approval, empirical economics and promotion
remain later independent gates. No GitHub push, PR, merge or deployment was performed.


## Optional runtime adoption proposal after the qualified checkpoint

The first canonical full gate passed all six components on Git tree
`73daaeae84dc2a4a3fd5e8127dd1a3ad25e20582` (gate digest
`cf3c7ee65cec02b627dab23ef3f34943c52bff67264361eb016ff604ee720177`). Backend took383.9s,
including351.8s pytest/coverage; frontend took751.4s, including739.0s browser checks.
Astra approved that exact scoped candidate with no open findings. Its complete source patch,
manifest, receipts, review and verification summary are preserved under
`.alpha/state/qlib-tabular-wave1/checkpoints/73daaeae84dc2a4a3fd5e8127dd1a3ad25e20582/`.
Those bytes will remain unchanged; subsequent source edits require new review and a new full gate.

Read-only dependency investigation found a bounded route for the two missing backends.
Adoption of these compatible, isolated pins is ordinary work within the approved tabular wave;
no new human authorization is needed provided all212 existing worker package versions remain
unchanged and the resolution adds no GPU runtime dependencies. A Qlib/NumPy/accepted-stack upgrade,
unsupported-platform source build, or materially broader download would require a separate decision.
No optional dependency is credited as executed before the actual tests below are performed.

The ADR-0011 evidence packet, recorded before dependency/code changes:

1. **Capability gap:** CatBoost/XGBoost adapters currently cannot fit because their native
   dependencies are absent. Existing ALPHA models do not implement these requested algorithms.
   Keep the existing isolated worker and schema3; add no root SDK, backtester, protocol or authority.
2. **Smallest boundary:** extend only the worker manifest/lock, capability distribution mapping
   and real adapter tests. Keep CPU-only parameters, fixed target/horizon, fold-local transforms,
   native JSON/model-text roundtrip and portable artifacts. CatBoost PredictionValuesChange
   must not be labeled tree gain; omit it from the shared gain table unless separately typed.
3. **Maintenance/API/provenance/security:** current published PyPI candidates are CatBoost1.2.10
   and XGBoost/xgboost-cpu3.4.1. CatBoost1.2.8 introduced NumPy2 support; later maintenance releases
   include relevant sklearn/NumPy fixes. Tagged APIs retain Qlib0.9.7's fit/eval/early-stopping and
   native serialization calls. XGBoost3.4.2 appears in upstream material but its PyPI release
   endpoints were absent during inspection; do not invent an installable pin. XGBoost's security
   policy covers the latest release and warns about hostile models/arrays; only freshly created
   internal model state is reloaded, with no external pickle, distributed TCP or secrets.
   This investigation does not assert that either package is free of vulnerabilities.
4. **Exact dependency impact:** propose `catboost==1.2.10`, `xgboost==3.4.1` on Darwin,
   and `xgboost-cpu==3.4.1` on supported Linux/Windows platforms. Current CPU-package artifacts
   include Linux ARM64 as well as x86-64 despite older descriptive prose. Never select plain
   latest XGBoost on Linux, which would add NCCL. CatBoost adds `graphviz==0.21` and
   `plotly==7.1.0`; existing `narwhals==2.24.0` and `packaging==26.2` satisfy Plotly.
   Expected universal graph:217 packages, with all212 existing(name,version) pairs identical.
   Keep pyqlib0.9.7, numpy2.2.6, pandas2.3.3, LightGBM4.6.0, scipy1.18.0 and sklearn1.9.0.
   Resolve a copied manifest/lock first, compare every old pin and reject CUDA/NCCL/cuDNN additions.
5. **Licenses/distribution:** CatBoost and XGBoost are Apache2.0; Python Graphviz and Plotly
   are MIT. Record notices. Install no system Graphviz executable. Existing project-license and
   full transitive-notice requirements still block distribution; this task is local research only.
6. **Offline/failure behavior:** fitting/prediction uses no runtime network, provider or LLM.
   Keep credential-free worker environments, deterministic seeds/thread limits, explicit missing/
   incompatible/import failures and no fallback. Reject simultaneous plain/CPU XGBoost distributions
   as ambiguous. Test absence by deterministic injection after optional packages are installed.
7. **Exit path:** remove the five additive lock entries or mark either capability unavailable
   without rewriting request/result/prediction/replay callers. Preserve all historical exchanges
   and the first qualified checkpoint; old exchanges remain inspectable with their own lock hashes.
8. **Acceptance:** only after zero-upgrade/CPU-only resolution, sync the isolated worker. Execute
   actual tiny CatBoost/XGBoost fits, finite aligned predictions, native state reload, repeat and
   cross-hash-seed determinism, full two-fold refitting and unavailable-outcome perturbations,
   injected failures/interruption, legacy regression, per-process memory receipts, CLI import/
   comparison and existing UI serialization. Re-review with Astra, update context/Atlas and run
   the complete final-tree gate. Linux UI snapshots, authentic private coverage, real-data approval,
   empirical economics and promotion remain separate even if these two runtimes execute locally.

Official metadata/source links:
[CatBoost1.2.10](https://pypi.org/pypi/catboost/1.2.10/json),
[XGBoost3.4.1](https://pypi.org/pypi/xgboost/3.4.1/json),
[XGBoost CPU3.4.1](https://pypi.org/pypi/xgboost-cpu/3.4.1/json),
[Graphviz0.21](https://pypi.org/pypi/graphviz/0.21/json),
[Plotly7.1.0](https://pypi.org/pypi/plotly/7.1.0/json),
[CatBoost releases](https://github.com/catboost/catboost/blob/v1.2.10/RELEASE.md),
[XGBoost release](https://github.com/dmlc/xgboost/releases/tag/v3.4.1),
[XGBoost security](https://github.com/dmlc/xgboost/blob/v3.4.1/doc/security.rst).
Tagged API inspection SHA-256: CatBoost core
`9c478404e7e1957181c2bdd5bb67b19dd351de6623ee4f8f2fbe63a45b8eba55`;
XGBoost training
`158615f6a60c19ba794537dac94a09fd859e54ff19154ce0ffcd16a461ac967d`.

Mac wheels before installation: CatBoost CPython3.12 universal2 is28,884,278bytes,
SHA-256 `b27115d5b443048f710001c8ac666892dfe03498492310b00466203c91cc30a5`;
XGBoost ARM64 is2,365,501bytes,
SHA-256 `a7afd7dbace0951c93aa85ffe046e54bc40893f5b51cd3e7991eb157bf9c7c7c`.
CPU Linux x86/ARM wheels are approximately5.8/5.4MB. The CatBoost Linux wheel contains
CPU/GPU algorithms internally but adds no CUDA/NCCL package dependency; this adapter forces CPU.
Available disk was15GiB before adoption. New receipts go under
`.alpha/state/qlib-tabular-wave1/optional-backends/`, preserving previous evidence.


**Optional resolution and install checkpoint:** The copied proposal resolved217 packages with
all212 original package records unchanged except the worker's own dependency list; only the
five proposed additions entered the graph and no GPU runtime packages appeared. A first
blanket`--no-build` attempt failed because existing Qlib requires the already accepted Gym
sdist; its failure log was preserved. Targeting wheel-only restrictions to the five additions
resolved that issue without changing an old pin. The isolated runtime sync then passed with
27.5MiB CatBoost,2.3MiB XGBoost and9.2MiB Plotly download labels; observed free-space delta
was163020800bytes. Root/global environments and their locks were not changed. Persistent
new-package wheel-only configuration is required for future ordinary sync/launch commands;
old Gym is not newly prohibited. CPU XGBoost requires Linux glibc>=2.28; Mac ARM XGBoost
requires macOS>=12, CatBoost macOS>=11 (Intel XGBoost>=10.15). These are installability limits,
not claims of tested platform qualification.

Astra preflight found **AR-004**: Qlib's XGBoost wrapper predicts all built trees after early
stopping, while reporting the validation-selected best iteration. Before qualification, the
adapter must slice to`best_iteration+1` and use that same selected state for prediction, model
hash, reload and importance. An actual early-stop fixture must show that full and selected
predictions differ and that the adapter matches the selected result. Installation alone does
not close this finding or establish either optional backend as numerically qualified.


## Final local candidate evidence and remaining gates

Product source fingerprint: `2070a9e4a11fc627b793456774e73b768c6240ec3a2ac220438abf7983492c64`; worker lock SHA-256: `95377c53944210b73996f05412daa690d47ba9691bfa6ca76b318370c63d21da`. All212 prior versions and all211 non-project package records remain identical; the217-package graph adds only the five declared packages and no GPU runtime dependencies.

The final corrected source passes68 worker tests (30 retained upstream warnings),269 consolidated root ML tests,431 frontend tests and27 canonical focused browser cases. All eight real recipe exchanges again emitted2420 finite aligned predictions. Each validated through the existing detail/tear-sheet response contracts, and the eight-way comparison passed immutable retry with identity `5083b2e97cbfd8441c443f72f7b556bb57f958f6d02949c52f44743df7d68597`. These are local macOS ARM results.

| Corrected-source recipe process | Peak RSS bytes | Seconds |
|---|---:|---:|

| lightgbm | 620494848 | 5.12 |

| linear-ols | 638697472 | 4.35 |

| linear-ridge | 638517248 | 4.23 |

| linear-lasso | 638304256 | 4.30 |

| linear-nnls | 636911616 | 4.37 |

| double-ensemble | 665092096 | 5.47 |

| catboost | 627343360 | 4.40 |

| xgboost | 634503168 | 4.54 |


Peak RSS includes imports and fitting in each separate worker process; it is measured evidence, not a cross-platform memory guarantee. The complete worker-suite process self peak was881770496bytes.

Final corrected-source canonical replays are CatBoost`60cd4efe8ba2ebb6` and XGBoost`cc0fcd50937637f8`, each121 OOS periods with1bps fee/2bps slippage. Both retain `counterfactual_refit=false`, null validation not run and `promotion_eligible=false`. Synthetic replay does not establish empirical economics. Prior f52-source trials and the original73da checkpoint are preserved under their original filenames.

Astra closed **AR-004** after an actual early-stop regression showed all eight full-booster scores differed from the validation-selected model, then verified selected-state prediction/hash/importance/reload parity. **AR-005** reproduced CatBoost all-core prediction defaults and XGBoost unbounded reload/matrix defaults; original and reloaded predictions now receive explicit thread bounds, verified by real spies at1 and2 threads. LightGBM/DoubleEnsemble reloads are explicit as well. The source review has no open product finding.

The ML list now distinguishes prepared inputs, predictions awaiting canonical replay, recorded replay and recorded counterfactual refit. Metadata no longer becomes a “VALIDATED” claim. The27-case browser replay includes those states, dependency failures, degenerate/tied diagnostics and all three viewport accessibility checks; existing macOS snapshots pass. Linux ML screenshots remain unqualified.

Exact final tree, changed paths, source patch, independent review and canonical-gate result remain in the sealed sibling worktree. The [final verification summary](../../../../qlib-tabular-wave1-20261026/.alpha/state/qlib-tabular-wave1/optional-backends/final-verification-summary.json) records that wave's outcome; it does not certify successor edits. The [first qualified checkpoint](../../../../qlib-tabular-wave1-20261026/.alpha/state/qlib-tabular-wave1/checkpoints/73daaeae84dc2a4a3fd5e8127dd1a3ad25e20582/verification-summary.json) remains independently preserved. No authentic private suite has been established; no hidden-source access or waiver is claimed. Current successor work is scoped by the [W11 refit packet](2026-10-26-qlib-w11-refit.md).

Current states: listed/adapter-implemented/local-runtime-executable and bounded synthetic checks complete for all eight recipes. Delivery integration, Linux/Windows native execution and screenshots, broader numerical calibration, authentic private coverage, real-data/discovery approval, empirical economics, counterfactual refitting and promotion remain pending. Persistent fitted-model reuse remains unsupported. No package decision is needed for the verified local pins; unsupported OS/ABI/source-build or accepted-stack upgrades require a separate decision.

Next coherent work package: qualify the same frozen inputs and selected-state/resource contracts on the declared Linux CPU lane, regenerate its own screenshots, and establish owner-provisioned private engineering coverage. Discovery/data approval and counterfactual research protocols remain subsequent independent gates. No publication, merge, deployment, protected data or broker execution occurred.

## Cloud qualification stabilization, 2026-10-27

**Repair.** Web experiment generation always sent `--model lightgbm --parameters-json {}`, and
`prepare_exchange` turns any override into a schema-3 request, so a frozen v1/v2 recipe (for example
`rank_ensemble_v1`) was silently replaced. `model` is now optional end to end (API, `_ml`, SPA default
"Experiment recipe (no override)"); `--model`/`--parameters-json` are sent only for an explicit choice,
and parameters without a model are rejected. Regressions: `test_default_experiment_generation_keeps_the_frozen_recipe`,
`test_project_generation_without_model_requests_no_override`, `mlLaunchRequest` unit cases and the
`ML generation keeps the experiment recipe by default` browser journey; the first two fail on the prior code.
The CLI's explicit `--model` remains a deliberate operator override.

**Visual baselines.** Five unchanged Linux baselines (Chart, Research, Governance reference;
Strategy Builder reference and wide) failed in the cloud container with 3–4% of pixels different.
Cause, established per view: the container image adds `/etc/fonts/conf.d/56-prefer-inter.conf`
(owned by no package), which aliases `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`,
`system-ui` and `sans-serif` to system Inter. `CSS.getPlatformFontsForNode` shows the chrome stack
then renders with the system Inter OTF; with that rule omitted it renders with the app's self-hosted
`Inter Variable` webfont, which the baselines record. With `FONTCONFIG_FILE` set to a copy of the
system configuration omitting only that rule (README cloud setup), each of the five views passed
against its unchanged baseline in a recorded per-view run; none was re-baselined and no threshold
changed. The ML-lab default view changed in this stabilization; both ML-lab Linux baselines were
re-taken under that corrected configuration (single title and project each). The Darwin ML-lab
baselines are stale and unverified.

**Open findings (not blockers).** `_diagnostic_metrics` returns no IC/RankIC when a schema-3 result has
no portfolio; the MlDiagnostics provenance still renders a LightGBM version row for other backends and
omits `backend_versions`; the capability notice reads "MODEL BLOCKED" while the probe is still loading;
schema-3 quantile diagnostics drop every cross-section with a tied score; `threadpoolctl` is imported
but only transitively declared; line 431 above cites receipts outside the repository.
