---
owner: web backend
sources:
  - apps/alpha-web/src/alpha_web/*.py
  - apps/alpha-web/src/alpha_web/api/**
  - apps/alpha-web/frontend/openapi.json
  - scripts/generate_web_openapi.py
  - scripts/check_openapi_operations.py
  - tests/unit/test_web_*.py
  - tests/integration/test_web_api_*.py
  - tests/integration/test_openapi_safe_routes.py
  - tests/unit/test_owner_auth_api.py
  - tests/unit/test_owner_local_confirmation.py
  - tests/unit/test_run_context_authority.py
verified: d0fffa796f8e
---

# Web API invariants

Rules for the Workstation backend in `apps/alpha-web/src/alpha_web/`: a local FastAPI server that relays the `alpha` CLI
as JSON and SSE (server-sent events, a one-way live stream) and serves the built browser app. The browser side is in
[web-frontend.md](web-frontend.md).

## What the backend is

- Keep it a thin relay that composes nothing — all composition stays behind the `alpha` CLI.
  [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md)
  The general rule is in [engineering § Subprocess boundary](engineering.md#subprocess-boundary).
- Bind loopback only (`127.0.0.1`). The port comes from `ALPHA_WEB_PORT`, then `PORT`, default 8801; an invalid value fails
  loud. Requests to `127.0.0.1` redirect (307) to `localhost`, the one origin owner confirmation accepts.
  Enforced by `tests/unit/test_web_port_config.py`.
- Resolve the store through `AlphaSettings().data_dir` (`api/_common.data_dir`) so web, its child processes, the CLI and
  MCP share one store.

## Calling the CLI

- Spawn `alpha` only through `_catalog._run_json` (synchronous `--json` projection) or `_invoke.launch` (background job).
  Do not add another spawn path.
- Keep every synchronous call time-bounded. `_run_json` defaults to 60 s; long calls pass a larger but finite timeout.
- Pass the child only the allowlisted environment built by `_catalog._cli_environment`: process basics, bulk-data paths,
  and a provider credential only for the exact command that needs it. It sets `ALPHA_DATA_DIR` and `TYPER_USE_RICH=0`.
  Enforced by `tests/unit/test_web_invoke.py`.
- Treat a non-zero exit or non-JSON stdout as an error. Surface the CLI's own `Error:` line (not Click's usage banner) and
  map it to a typed 4xx, never a raw 500. Enforced by `tests/unit/test_web_invoke.py`.
- Launch background jobs in their own process group (`start_new_session=True`) so cancel can kill the whole tree.
  Heavyweight jobs reserve capacity (`alpha_cli.job_capacity`) and keep a durable lease heartbeat
  (`alpha_cli.durable_lease`). If start-up fails, reap the child before releasing capacity; never report a job done whose
  terminal journal update failed. Enforced by `tests/unit/test_web_invoke.py`, `tests/unit/test_web_cancellation_publication.py`.
- The live job registry is in memory. The durable record of finished work is the run store; a restart loses job handles.
- Cancelling a durable job first records it through `alpha project job-cancel` (actor and reason), then signals the
  process group. Lease rules: [cli-control-store § Jobs, leases and capacity](cli-control-store.md#jobs-leases-and-capacity).
- A timed-out terminal journal write may have committed. `_ml.py` reads the job back through `alpha project job-show`
  before one bounded retry. If the outcome stays unverified it logs an operator error and keeps the capacity reserved;
  never release capacity or report a terminal state that was not verified.
- Job ETA is honest: the median duration of finished jobs with the same command path in this web process. With no such
  sample progress is `indeterminate` (no ETA); an estimate never shows more than 95 % before the job ends.
- The generic launcher `POST /api/jobs` classifies argv with `alpha_cli.catalog.classify_generic_command`:
  - `owner_only` commands are refused (for example `owner-auth`, `project`, `suite`, `provider`, `assistant`, most
    `research` and `paper` verbs). Enforced by `tests/unit/test_owner_auth_api.py`.
  - An argv root that is not a classified `alpha` command (`unknown`) is refused with 422 before any subprocess or
    job record exists, with or without a run context.
  - `empirical` commands need an explicit run context, resolved by `run_authority.resolve_run_context`. A missing or
    unverifiable context is a denial, never a default. Enforced by `tests/unit/test_run_context_authority.py`.
- `MPLCONFIGDIR`, when set, passes to the CLI child verbatim (`_catalog._PROCESS_ENV_NAMES`), so Matplotlib
  configuration and cache placement follow the parent process.

## Allowed alpha_cli imports

- The import-linter contract `alpha_web imports only public platform surfaces` (root `pyproject.toml`, run by
  `uv run lint-imports` in the backend gate) forbids `alpha_patterns`, `alpha_data`, `alpha_strategies`, `alpha_backtest`,
  `alpha_validation`, `alpha_forecast`, `alpha_research`, `alpha_study` and `alpha_mcp` — including indirect imports.
  So any `alpha_cli` module you import must not pull those in. See [engineering § Import layers](engineering.md#import-layers).
- Seams in use today: `run_store`, `catalog`, `run_context`, `artifact_contract`, `run_projection`, `figure_cache`,
  `job_capacity`, `durable_lease`, `ml_contract`, `suite_catalog`, `paper_store`, `paper_readiness`,
  `assistant_contracts`, `investigation_workspace_contracts`, and `owner_auth` (exception below).
  A new `alpha_cli` import is an architecture change: keep it small and engine-free.
- `tests/unit/test_public_seams.py` checks that `alpha_cli.catalog` and `alpha_cli.run_store` load without numpy, scipy,
  torch, nautilus or `alpha_validation`. It covers only those two modules.
- The one `ignore_imports` entry is `alpha_web.api.owner_auth -> alpha_cli.owner_auth`
  ([ADR-0030](../../adr/0030-touch-id-owner-presence-for-research-actions.md)). Only that router may import it.
  Never add another ignore entry to make an import pass.
- Never import matplotlib or `alpha_research` in the web process. Enforced by
  `tests/unit/test_web_figures.py::test_the_web_process_never_imports_matplotlib_or_the_renderer`.
- Bounded Polars reads of artifacts are allowed (`_runs.py`, `_ml.py`). No engine, gauntlet, Nautilus, Qlib or Kronos
  in-process.

## Reads and writes

- Never open the CLI's SQLite control store (`control/workstation.sqlite3`) from web code. Read control-plane state
  through `alpha ... --json`. `_activity.py` only stats the file and its `-wal`/`-shm` sidecars to detect change.
  The one in-process writer is the owner-auth seam, which records challenges and receipts in the control store.
- Read runs only through bounded seams (`alpha_cli.run_store`, `artifact_contract.verify_manifest_artifacts`,
  `run_projection`). Operational state needs its own governed public seam — do not scan `RUN_DIRS` for it.
- Read paper state only through `alpha_cli.paper_store` / `paper_readiness`. Starting or stopping a paper node is a CLI
  job, never an in-process call. [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md)
- The only file the web code writes itself is a named workspace, `data_dir/web/workspaces/<slug>.json` (atomic write,
  slugified name). It is presentation state with no research or execution authority.
- Never reconstruct trading evidence or compute metrics in the backend; relay what the CLI and artifacts record.
- Run labels are server-side: `_runs.display_name` builds `<strategy> D1 — <symbol> · <source> · <first → last> · run
  <8 hex>` from the manifest and omits any part it does not record; `market_of` decides crypto/equities or `unknown`.

## Chart data

- `GET /api/candles/{symbol:path}` relays `alpha data candles`; `GET /api/overlays/{symbol:path}` relays
  `alpha chart overlays` over the same point-in-time window. Overlays live outside `/candles` because the path
  parameter swallows any suffix. A candles CLI failure is 404 and an overlay failure 400, both with the CLI's own text.
- Canonical reads are cached on the argv plus the bar file's mtime; `tail` only trims the payload. Archive reads
  (`manifest_id`) are never cached, so every archive chart open re-runs the CLI's manifest and raw-lineage
  verification. See [data § Crypto storage](data.md#crypto-storage).
- `GET /api/chart-datasets` (`alpha data chart-datasets`) is discovery only and returns 409 on a CLI failure.

## API contract

- Give every `/api/` JSON route a `response_model`. Only `/stream` (SSE) and `/tearsheet` routes are exempt. Models live
  in `api/models.py` and use `StrictModel` (`extra="forbid"`). Enforced by `tests/unit/test_web_contracts.py`.
- The committed `apps/alpha-web/frontend/openapi.json` must equal `create_app().openapi()`. Regenerate with
  `uv run python scripts/generate_web_openapi.py`; the gate runs it with `--check`. Enforced by
  `tests/unit/test_web_contracts.py::test_committed_openapi_matches_runtime`.
- After any route change also run `uv run python scripts/check_openapi_operations.py --write`. It regenerates
  `docs/governance/openapi-operation-classification.json` and the
  [capability matrix](../../governance/capability-authority-matrix.md); the gate fails if they are stale.
- A GET with no path or required parameters is classified `automatic`: `tests/integration/test_openapi_safe_routes.py`
  calls it against an empty temporary store and it must not return 422 or 5xx.
- `info.version` is the FastAPI default `0.1.0` and nothing reads it. Drift is caught by the committed-file equality
  check and the generated TypeScript client, not by a version number.
- Bound every input: string lengths, list sizes and patterns in the request model (for example owner `reason` ≤ 8,192
  characters, hashes as 64 lowercase hex). The activity poll interval is clamped to 0.05–10 s.
- Never use `profile` (crypto/equities) as a route parameter or schema property — it is a display setting, not a
  permission. Enforced by `tests/unit/test_web_contracts.py::test_profile_is_never_an_api_parameter_or_field`.
- Every error body is `ApiErrorV1` with a request id. `api/errors.safe_message` strips terminal codes, tracebacks, paths,
  secret environment values and broker account ids; unexpected exceptions return a generic 500 message.
  An in-band `error` string relayed from the CLI (as in `POST /api/rules/evaluate`) passes through `safe_message` too.
  Enforced by `tests/integration/test_web_api_errors.py`.
- The `/api/research` router may not gain mutation verbs; the allowed POSTs are pinned.
  [ADR-0021](../../adr/0021-research-workstation-read-plane-and-command-center.md)
  Enforced by `tests/integration/test_web_api_research.py::test_research_router_exposes_no_new_mutation_verbs`.

## Streaming (SSE)

- Job stream `GET /api/jobs/{job_id}/stream`: one `line` event per output line, `id` = line index. A reconnect with
  `Last-Event-ID` replays only missed lines. It ends with exactly one `done` (run id), `failed` (CLI error) or
  `cancelled`. The SPA depends on these event names.
- Parse the run id from the CLI's `-> run <16 hex>` line; never guess it.
- Activity stream `GET /api/activity/stream`: a per-connection polling diff of the run store and job registry. It is
  stat-only and reads a manifest only when its mtime changes, so runs started from the CLI or MCP also appear. Areas
  are declared in `_activity.AREAS`. Enforced by `tests/unit/test_web_activity_areas.py`.

## Owner confirmation routes

- `POST /api/owner-auth/actions/challenge` and `/actions/perform` are the only browser path to owner research actions.
  [ADR-0030](../../adr/0030-touch-id-owner-presence-for-research-actions.md),
  [ADR-0038](../../adr/0038-local-confirmation-and-terminal-archive-charts.md). Authority rules:
  [research-integrity § Owner authority](research-integrity.md#owner-authority).
- Verify in-process through `alpha_cli.owner_auth`, then run only the server-built closed argv from `_action_argv`
  through `_run_json`. `record_semantic_event` is never a CLI action; perform returns the seam's atomic result.
- Take the actor from the verified authorization, never from the request. Re-derive the artifact hash server-side and
  refuse a mismatch. Tokens are single-use and expire after 60 s.
  Enforced by `tests/unit/test_owner_auth_api.py`, `tests/unit/test_owner_local_confirmation.py`.
- Refuse (403) unless Origin is exactly `http://localhost:<port>`, Host matches, content type is JSON, and
  `Sec-Fetch-Site` is absent or `same-origin`.
- Local confirmation is not proof that a human was present. Never label it as verified physical presence.
- The closed action list is the `OwnerActionChallengeRequest.action_type` literal. Enforced against the generated
  contract by `tests/unit/test_web_owner_actions_drift.py`.
- Research-gate override, holdout reveal, reviewed asset master and owner-auth enroll/recover stay CLI-only.
  Enforced for the override by `tests/unit/test_web_owner_action_argv.py`.
- Agents never call these routes or `alpha owner-auth enroll|recover`; the `pre-owner-action-guard` hook blocks them.

## Figures

- Serve server-rendered figures without matplotlib in the web process. Derive the cache key from `alpha_cli.figure_cache`
  plus the key environment the CLI publishes. Serve on a hit; on a miss subprocess `alpha figures render` behind a
  single-flight lock, so concurrent requests render once.
- Bare image URL: strong `ETag` + `must-revalidate`. Pinned `?key=`: `immutable`. A stale pinned key returns 409 with
  the current key — never different bytes at one URL. A traversal-shaped figure id never reaches the filesystem.
  Enforced by `tests/unit/test_web_figures.py`.

## Adding a route

1. Make the CLI own the data: an `alpha ... --json` projection or a public `alpha_cli` read seam.
2. Add a thin adapter in `_<area>.py` that calls `_run_json`, and a router in `api/` with a strict response model.
3. Register it in `app.py`. Regenerate `openapi.json` and the operation classification (above).
4. Regenerate the TypeScript client — see [web-frontend.md § Generated API client](web-frontend.md#generated-api-client).
5. Add tests in `tests/integration/test_web_api_<area>.py` against an isolated temporary store; cover the CLI-failure
   (4xx) path as well as success.
