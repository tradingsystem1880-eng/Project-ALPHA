---
owner: isolated workers
sources:
  - workers/qlib/**
  - workers/literature/**
  - workers/rdagent/**
  - scripts/gate_components.py
  - tests/unit/test_qlib_isolation.py
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/_native_rule_environment.py
verified: f4767cd8d092
---

# Worker invariants

What must hold for the isolated worker projects under `workers/`: the Qlib ML worker, the literature
acquisition worker and the RD-Agent native-loop probe. The general rule is
[research integrity § Models and isolated workers](research-integrity.md#models-and-isolated-workers).

## Shared rules

- Each worker is its own uv project with its own `pyproject.toml` and `uv.lock`, outside the root workspace
  (root members are `packages/*` and `apps/*`). Never add a worker dependency to the root `pyproject.toml`
  or `uv.lock`. For Qlib this is enforced by `tests/unit/test_qlib_isolation.py`.
  [ADR-0016](../../adr/0016-isolated-qlib-worker.md).
- No ALPHA package imports worker code. `alpha_cli` launches a worker as a subprocess and exchanges files
  or JSON with it. [engineering § Subprocess boundary](engineering.md#subprocess-boundary).
- The qlib and literature gates are `uv run python scripts/gate.py component qlib|literature` (CI jobs of the
  same name). From `workers/<name>/` they run: `uv lock --check`, `uv sync --locked`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q -m "not network"`.
  `gate.py check` does not run worker tests.
- Workers target CPython 3.12 only (`>=3.12,<3.13`); qlib and literature run strict mypy. The one exception is RD-Agent's stock
  runtime bundle, CPython 3.11 (see below).

## Qlib worker

- This is the only environment with Qlib, LightGBM, CatBoost or XGBoost. No ALPHA process imports Qlib or
  deserialises a model pickle; no model pickle or executable object crosses the exchange.
  `tests/unit/test_qlib_isolation.py::test_importing_ml_contract_does_not_import_worker_or_model_stack`.
- Recorder data and fitted model state stay in an ephemeral worker directory deleted when the process exits.
  Native model text or JSON is round-tripped only inside the worker; persistent model reuse is unsupported.
- The exchange is built and validated by `apps/alpha-cli/src/alpha_cli/ml_input.py` and `ml_contract.py`,
  and validated again independently by `workers/qlib/src/alpha_qlib_worker/contract.py`. Change both sides
  together.
- Daily panel rows and predictions are available at the session close, `session_ts + 23h`, never midnight;
  `contract.py` rejects any other `available_at`.
- Request `schema_version` is 1 (LightGBM), 2 (`rank_ensemble_v1`) or 3 (model selection). Contract
  versions are additive: never change what v1 or v2 compute; older readers reject newer versions rather
  than downgrade them.
- Preprocessing statistics are fitted on each training fold only. Ensemble weights and ridge alpha are fixed,
  not tuned.
- Requests cannot supply device, seed, executable classes, arbitrary model arguments, validation inclusion
  or more than eight threads; numeric parameters are bounded by `schemas/request-v3.schema.json`.
- There is no model fallback: a missing, unsupported or failing dependency fails explicitly. `capabilities`
  reporting `available` means importable only, not data readiness, qualification or promotion eligibility.
- The newer registry packages (`catboost`, `xgboost`, `xgboost-cpu`, `graphviz`, `plotly`) are
  wheel-only (`[tool.uv] no-build-package`); a missing wheel fails instead of compiling from source.
- ALPHA's canonical replay (`alpha ml replay`, through `run_weight_replay`) is authoritative for the metrics
  it computes; Qlib's own Recorder and backtest reports are advisory. The replay keeps the label
  `OOS replay validated — model not recomputed under counterfactual`: not a full gauntlet, not promotion-eligible.
- Feature recipe version 1 is the default. Version 3 (opt-in) computes all 158 Alpha158 columns and the fold
  normalisation with upstream Qlib (`upstream_alpha158.py`); the parity test against Qlib's own provider and
  handler must stay exact. Version 2 is a legacy 40-column correction. The recipe is part of `config_hash`,
  which prediction readers enforce: never reuse a model just because feature names match.
- Versions 1 and 2 (`features.py`, `native_feature_corrections.py`, the v1 normalisation in `real.py`) exist
  only to reproduce stored results: never change their formulas. Their golden values are compared by value
  (1e-9), not by byte digest: recomputation is bit-identical on one machine only.
- `VWAP0` is a typical-price proxy in every recipe, never exchange VWAP, and every v3 result names it.
- Version 3 does not become the default until its per-model processor choice is measured on real data
  ([ADR-0042](../../adr/0042-qlib-worker-delegates-data-layer-to-upstream.md) § Open before v3 is the default).
- W09/W11 planning contracts, invocation observations, checkpoints and refit plans grant no admission,
  accounting, fit allowance or promotion; readiness stays blocked when the worker is absent.

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

## RD-Agent worker

- A development-only probe of pinned RD-Agent native loops on fixed synthetic inputs, plus the ALPHA-judged factor
  loop below. It has no public research command or production route, and no ALPHA package imports it. Every result stays synthetic,
  `not_admitted`; no scientific run id or completed D1 attempt is invented.
- Upstream source stays external at commit `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`; point
  `ALPHA_RDAGENT_SOURCE` at a byte-identical `rdagent/` copy. `source_pin.py` verifies the tree digest before
  any upstream import, and the source root is never put on `sys.path`. Never vendor upstream code here.
- The project is `package = false` with its own `uv.lock`, a focused import subset, not upstream's full
  environment. Rule and economics profiles are fresh-only venvs (`.venv-rule-qualified`,
  `.venv-economics-qualified`) built from hash-pinned requirement locks; list them in the clone's
  `.git/info/exclude` (`.gitignore` already covers `.venv-*/`) and never rerun the installer over a preserved profile.
- `measure_rule_environment` hashes the installed profile, the source and `pyproject.toml` of `alpha-core`,
  `alpha-patterns`, `alpha-strategies` (plus `alpha-backtest`, `alpha-data` for the costed profile), the
  requirement lock and the root `uv.lock`. Any byte change in those raises `DataError` until profiles are
  rebuilt and fingerprints re-approved; old approvals and history are not rewritten.
  [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
- The native fixture loop (`native_fixture.py::NativeFixtureLoop`) is a `LoopMeta` subclass of upstream
  `LoopBase` that never overrides `run`, `_run_step`, `dump` or `load`, so upstream's own loop drives it.
  Every executed stage is charged to the fixture owner, and interrupted admitted work stays charged
  (`conformance.py`).
- Stock RDLoop runtime: built only by `scripts/setup_rdagent.sh --with-stock-runtime` from the hash-pinned
  `stock-requirements.lock` on CPython 3.11 (`--require-hashes --no-deps`); `install_stock_profile.py` proves the installed
  distributions are exactly the locked ones and records an inventory digest. It measures a runtime and grants no authority.
- Model gateway ([ADR-0044](../../adr/0044-rdagent-model-gateway.md), `model_gateway.py`): the one route from RD-Agent to a
  model. Standard library only; it listens on `127.0.0.1` and imports neither ALPHA nor RD-Agent. Chat is the confined Codex
  program (read-only, no tools, no web search), embeddings are local Ollama, and the paid route is off unless the owner
  configures it. A request parameter it cannot honour is refused or recorded as waived, never dropped silently. Call and
  dollar budgets (monthly dollars capped at 50, not raisable) are checked before every attempt and fail closed. There is
  no automatic switch between routes, and the call log holds hashes and lengths, not text. The fixture loops still clear
  all model settings. `tests/unit/test_rdagent_model_gateway.py`.
- ALPHA-judged factor loop ([ADR-0049](../../adr/0049-alpha-judges-rdagent-factors.md)): the one model-connected
  real-data route, started by `factor_loop_launch.py` (not yet an `alpha` command). RD-Agent's own factor loop runs
  unmodified; only the classes named in its `QLIB_FACTOR_*` settings are ALPHA's (`alpha_factor_judge.py`), and they
  import RD-Agent and pandas, never an ALPHA package: the evaluator `alpha_cli.rdagent_factor_eval` runs as a subprocess
  in ALPHA's environment. The loop is never given data on or after 2024-01-01; every factor goes to the append-only
  cross-run trial ledger (a repeat by code hash is not new evidence); `decision` is ALPHA's rule, never the model's;
  every record is `exploratory, not admitted, not yet confirmed` with all authority flags false and the survivorship
  disclosure. Its runtime is built only by `--with-factor-runtime` from `factor-requirements.lock` and recorded by
  `install_stock_profile.py --profile factor`; generated factor code runs without the gateway's address and token,
  but as the same user: it is not isolated from the run folder, the ledger or other processes (trusted-mistake guard only).
  Tests: `tests/unit/test_rdagent_factor_{eval,judge,launch}.py`.
- There is no gate component or CI job (`scripts/gate_components.py` lists none). Its checks are root tests
  such as `tests/unit/test_native_loop_conformance.py`; the source-dependent ones skip without
  `ALPHA_RDAGENT_SOURCE`, and a skipped run confers no native qualification.
- Its audit hooks and sanitised subprocesses contain trusted fixture mistakes; they are not hostile-code
  or same-user isolation.
