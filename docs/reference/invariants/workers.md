---
owner: isolated workers
sources:
  - workers/qlib/**
  - workers/literature/**
  - workers/rdagent/**
  - workers/afml/**
  - apps/alpha-cli/src/alpha_cli/labels_cmds.py
  - scripts/gate_components.py
  - tests/unit/test_qlib_isolation.py
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/_native_rule_environment.py
verified: 9c856742539b975c
---

# Worker invariants

Qlib, literature, RD-Agent and AFML workers follow the [research integrity rules for isolated workers](research-integrity.md#models-and-isolated-workers).

On this page: [Shared rules](#shared-rules), [Qlib worker](#qlib-worker), [Literature worker](#literature-worker), [AFML worker](#afml-worker),
[RD-Agent worker](#rd-agent-worker).
## Shared rules
- Each worker is its own uv project with its own `pyproject.toml` and `uv.lock`, outside the root workspace (root members are `packages/*` and `apps/*`).
  Never add a worker dependency to the root `pyproject.toml` or `uv.lock`. For Qlib this is enforced by `tests/unit/test_qlib_isolation.py`.
  [ADR-0016](../../adr/0016-isolated-qlib-worker.md).
- No ALPHA package imports worker code. `alpha_cli` launches a worker as a subprocess and exchanges files or JSON with it. [engineering § Subprocess
  boundary](engineering.md#subprocess-boundary).
- The qlib, literature and afml gates are `uv run python scripts/gate.py component qlib|literature|afml` (CI jobs `qlib-worker`, `literature-worker`,
  `afml-worker`). From `workers/<name>/` they run: `uv lock --check`, `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run
  mypy`, `uv run pytest -q -m "not network"`. `gate.py check` does not run worker tests.
- Workers target CPython 3.12 only (`>=3.12,<3.13`); qlib, literature and afml run strict mypy. The one exception is RD-Agent's stock runtime bundle,
  CPython 3.11 (see below).
## Qlib worker

- This is the only environment with Qlib, LightGBM, CatBoost or XGBoost. No ALPHA process imports Qlib or deserialises a model pickle; no model pickle or
  executable object crosses the exchange. `tests/unit/test_qlib_isolation.py::test_importing_ml_contract_does_not_import_worker_or_model_stack`.
- Recorder data and fitted model state stay in an ephemeral worker directory deleted when the process exits. Native model text or JSON is round-tripped only
  inside the worker; persistent model reuse is unsupported.
- The exchange is built and validated by `apps/alpha-cli/src/alpha_cli/ml_input.py` and `ml_contract.py`, and validated again independently by
  `workers/qlib/src/alpha_qlib_worker/contract.py`. Change both sides together.
- Daily panel rows and predictions are available at the session close, `session_ts + 23h`, never midnight; `contract.py` rejects any other `available_at`.
- Request `schema_version` is 1 (LightGBM), 2 (`rank_ensemble_v1`) or 3 (model selection). Contract versions are additive: never change what v1 or v2 compute;
  older readers reject newer versions rather than downgrade them.
- Preprocessing statistics are fitted on each training fold only. Ensemble weights and ridge alpha are fixed, not tuned.
- Requests cannot supply device, seed, executable classes, arbitrary model arguments, validation inclusion or more than eight threads; numeric parameters are
  bounded by `schemas/request-v3.schema.json`.
- There is no model fallback: a missing, unsupported or failing dependency fails explicitly. `capabilities` reporting `available` means importable only, not
  data readiness, qualification or promotion eligibility.
- The newer registry packages (`catboost`, `xgboost`, `xgboost-cpu`, `graphviz`, `plotly`) are wheel-only (`[tool.uv] no-build-package`); a missing wheel
  fails instead of compiling from source.
- ALPHA's canonical replay (`alpha ml replay`, through `run_weight_replay`) is authoritative for the metrics it computes; Qlib's own Recorder and backtest
  reports are advisory. The replay keeps the label `OOS replay validated — model not recomputed under counterfactual`: not a full gauntlet, not
  promotion-eligible.
- Feature recipe version 1 is the default. Version 3 (opt-in) computes all 158 Alpha158 columns and the fold normalisation with upstream Qlib
  (`upstream_alpha158.py`); the parity test against Qlib's own provider and handler must stay exact. Version 2 is a legacy 40-column correction. The recipe is
  part of `config_hash`, which prediction readers enforce: never reuse a model just because feature names match.
- Versions 1 and 2 (`features.py`, `native_feature_corrections.py`, the v1 normalisation in `real.py`) exist only to reproduce stored results: never change
  their formulas. Their golden values are compared by value (1e-9), not by byte digest: recomputation is bit-identical on one machine only.
- `VWAP0` is a typical-price proxy in every recipe, never exchange VWAP, and every v3 result names it.
- Version 3 does not become the default until its per-model processor choice is measured on real data
  ([ADR-0042](../../adr/0042-qlib-worker-delegates-data-layer-to-upstream.md) § Open before v3 is the default).
- W09/W11 planning contracts, invocation observations, checkpoints and refit plans grant no admission, accounting, fit allowance or promotion; readiness stays
  blocked when the worker is absent.
## Literature worker
- The one research network surface ([ADR-0024](../../adr/0024-literature-acquisition-worker-and-claim-model.md)).
  Metadata comes only from OpenAlex, Crossref, Unpaywall and arXiv; Google Scholar stays manual. Documents are
  open-access or owner-provided only; no OCR and no paywall bypass.
- Every URL, redirect and response goes through the acquisition primitives: HTTPS only, IDNA host allowlist,
  global addresses only, MIME, size and magic-byte checks.
- Stored objects are content-addressed with a `SourceReceipt` labelled `UNTRUSTED_SOURCE`. Document text never
  carries instruction authority. Encrypted, malformed, image-only and truncated documents stay honest
  non-evidence states.
- No `alpha_*` imports. `src/literature_worker/_acquisition.py` is the only copy of the acquisition primitives
  (the CLI duplicate was removed 2026-11-14); their tests are `workers/literature/tests/test_acquisition.py`.
- The worker's commands are `fetch`, `discover` and `extract`, the three the CLI launches.
- Launch (`apps/alpha-cli/src/alpha_cli/research_cmds.py::_run_literature_worker`): a closed argument vector
  and a minimal environment (`LANG`, `LC_ALL`, `PATH=os.defpath`, `PYTHONPATH`, `UV_NO_CONFIG=1`,
  `UV_OFFLINE=1`), so no credentials, shell state or host override is inherited. It runs
  `uv run --locked --no-sync --project workers/literature python -P -m literature_worker` in a new session
  with limits of 60 s CPU, 1 GiB address space, 32 MiB file size, 64 open files and a 180 s timeout.
- A valid explicit `UV_CACHE_DIR` is preserved; otherwise a temporary per-invocation cache is removed after
  exit. An invalid explicit cache fails before the worker starts.
- Network work starts only from an explicit owner action, never from opening or refreshing a page. Only owner
  screening raises a claim from draft to screened.

## AFML worker

- The only environment with RiskLabAI, quantowl or numba ([ADR-0054](../../adr/0054-afml-worker.md)): RiskLabAI pinned from
  PyPI, quantowl by commit, `[tool.uv] exclude-newer` keeps releases two weeks old. Never in the root lock; never edited.
- Two libraries, one answer: a value both implement leaves only when they agree to 1e-10 (draws, events, folds: exactly);
  otherwise `AgreementError`. A value only one implements is not offered without a hand parity test.
- Labels default to ALPHA's convention (`basis="high_low"`): decide at the event close, enter at the next open, touch on
  the bar's high or low, a gap through a barrier exits at the open, a bar reaching both is stop-first with the
  optimistic reading beside it. `basis="close"` is the libraries' convention, for parity only.
- Nothing is fitted on the whole sample: barrier widths and CUSUM thresholds use closes strictly before the event; the
  vertical barrier is a bar count; an undecided event gets no label; fractional-differencing `d` is chosen on the
  training span (`fracdiff --fit-end`) and frozen; weights take `uniqueness --train-end`.
- Splits (`cv.py`) are RiskLabAI's combinatorial splitter (also for k-fold: its `PurgedKFold` under-purges labels
  of varying length), each passed through ALPHA's brute-force leak checker and compared with ALPHA's
  reference rule; a library may drop more rows (reported), never fewer. Importance (MDI, MDA, SFI) runs quantowl's
  functions on those checked folds only, never RiskLabAI's unpurged MDA or SFI; it is a report, no gate reads it.
- Root checks that need the worker skip elsewhere and run in the `afml-worker` job (`AFML_ROOT_TESTS` in
  `scripts/gate_components.py`): the `alpha labels` smoke check, the future-poison guard, and parity with
  ALPHA's `barrier.py`, `cpcv.py`, PSR, DSR and PBO. ALPHA's values stay the record.
- `alpha labels barrier|weights|importance` (`labels_cmds.py`) reads bars point in time, runs the worker with
  `uv run --locked --no-sync` and a minimal environment, and publishes one immutable folder under `data_dir/labels/`
  per hash of inputs and worker code, with `result.json` (spine-shaped facts, labels). A missing worker fails with
  `WORKER_NOT_INSTALLED` and the one setup step.

## RD-Agent worker
Moved to [rdagent.md](rdagent.md); its rules are grouped there by heading.

## Code map

### AFML code map

An isolated process that runs two independent implementations of methods from López de Prado's
*Advances in Financial Machine Learning*: RiskLabAI (primary) and quantowl (second opinion).
Today it offers sample uniqueness and weights, the sequential bootstrap, CUSUM events, triple-barrier
labels and meta-labels, purged CV, fractional differencing, feature importance and Sharpe statistics. A number leaves only when both libraries agree (or, for
labels on highs and lows, when ALPHA's own adapter code computed it). It is a separate uv
project with its own lock; no ALPHA package imports it and it imports no ALPHA package.
[ADR-0054](../../adr/0054-afml-worker.md)

- Code: `workers/afml/src/alpha_afml_worker/` (`contract.py` checks input; `uniqueness.py`,
  `labels.py`, `cv.py`, `fracdiff.py`, `importance.py`, `stats.py` are the adapter); tests: `workers/afml/tests/` (`shared_fixtures.py` holds the
  shared inputs: hand-built bars and a seeded synthetic series). Never commit market data.
- A new function gets a parity test first: a hand-worked value, and the two libraries equal to
  1e-10 where both implement it. A look-ahead-sensitive one also gets a truncation test.
- Read each library's API from the installed source in `workers/afml/.venv`, never from memory.
- From `workers/afml`: `uv lock --check`, `uv sync --locked`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q -m "not network"`.
- Or CI's job from the repository root: `uv run python scripts/gate.py component afml`.
- `alpha labels barrier|weights` calls this worker; its picture is `figure.py`. Real-data example:
  `uv run python examples/owner_figure.py --help` (writes outside git).

### Literature code map

An isolated process that discovers, fetches and extracts research literature for research cases
and returns bounded, validated claims. It is a separate uv project with its own lock; no root
package imports it. The CLI starts it with a minimal environment, no inherited credentials and
resource limits; its output is advisory evidence, never research authority.
[ADR-0024](../../adr/0024-literature-acquisition-worker-and-claim-model.md)

- Code: `workers/literature/src/literature_worker/`; tests: `workers/literature/tests/`
  (add a new unit test there, named `test_<module>.py`). The launch boundary is tested from the
  root in `tests/integration/test_research_cli.py`.
- From `workers/literature`: `uv lock --check`, `uv sync --locked`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q -m "not network"`.
- Or CI's job from the repository root: `uv run python scripts/gate.py component literature`.
- Tests that touch the network carry the `network` marker and never run in CI.

### Qlib code map

An isolated process that runs the real `pyqlib` package for daily cross-sectional model training
and returns close-stamped out-of-sample predictions. It is a separate uv project with its own lock;
no root package imports it, and it imports no ALPHA package. It exchanges only validated JSON and
Parquet with `alpha_cli`, and its results are advisory: ALPHA's own replay is the authority.
[ADR-0016](../../adr/0016-isolated-qlib-worker.md)

- Code: `workers/qlib/src/alpha_qlib_worker/`; tests: `workers/qlib/tests/`. Root tests that cover
  the boundary: `tests/unit/test_qlib_isolation.py`, `tests/unit/test_ml_*.py`.
- The worker has its own environment. From `workers/qlib`: `uv lock --check`, `uv sync --locked`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
  `uv run pytest -q -m "not network"`.
- Or run CI's job from the repository root: `uv run python scripts/gate.py component qlib`.
- A change to the exchange schema also needs the root check (`uv run python scripts/gate.py check`)
  for the CLI side.
