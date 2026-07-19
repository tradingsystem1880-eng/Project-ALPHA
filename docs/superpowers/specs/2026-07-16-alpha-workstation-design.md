# Design — ALPHA Quant Workstation: an institutional research & trading terminal

> **Implemented-state pointer (2026-07-18):** This approved design remains a historical plan.
> The shipped blotters use TanStack Table/Virtual rather than AG Grid, and frontend quality/assets
> are mandatory CI gates. The panel manifest ultimately remained a frontend-owned registry; the
> backend exposes capability catalogs but no separate panel-manifest route. See [`CLAUDE.md`](../../../CLAUDE.md) and
> [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) for current behavior.

## Context

Project ALPHA has a mature $0 Python quant backend and three surfaces over it: the `alpha` CLI
(single source of truth, only writer of run artifacts), the `alpha_mcp` conversational server, and
the `alpha_web` FastAPI+Jinja IDE. This spec unifies **every** capability behind **one
professional, desktop-feel workstation** — dark theme, dockable/floating/popout panels, multiple
savable workspaces, a command palette, keyboard shortcuts, dense fast rendering — comparable to
Bloomberg / OpenBB / TradingView / QuantConnect. It is **personal, single-user, $0, loopback-only**:
no auth, billing, multi-user, or SaaS features.

The workstation is a **thin orchestration layer**. Business logic stays in the packages; the UI
**subprocesses the `alpha` CLI and reads its byte-stable artifacts** (the proven `alpha_web`/
`alpha_mcp` pattern), adding a JSON+SSE API and a single-page app on top. Nothing in the import DAG
imports it — it stays at the top.

Design informed by research into the existing orchestration surface and the mandated OSS platforms
(OpenBB's widget/apps manifest + provider abstraction, TradingAgents' role-decomposed AI desk,
Ziplime/QuantStats result artifacts, QuantMuse/gs-quant risk/factor/scenario taxonomy) and a
front-end stack evaluation.

## Decisions (user-approved)

- **Front-end:** a **built SPA** — Vite + React + TypeScript, **Dockview** (docking/float/popout +
  serializable multi-workspace layouts), **TradingView Lightweight Charts** (candles) + **uPlot**
  (equity/analytics), **AG Grid** (dense blotters), **cmdk** (command palette). Built to static
  assets **served by FastAPI**. The Node/Vite build is the one accepted concession to the "no build
  step" ethos; FastAPI stays a thin JSON+SSE orchestrator, and the backend contract is front-end
  agnostic so nothing is wasted.
- **Evolve `alpha_web` in place** — grow the existing member; keep the package name `alpha_web`
  (branded "Workstation" in UI/docs). Its `_runs.py`/`_invoke.py` already are the workstation
  backend and it already sits correctly atop the DAG. A new member would triplicate the
  `_invoke`/`_runs` pattern for no gain. Deferred: a literal rename, and factoring web/mcp shared
  readers into `alpha_runstore`.
- **First milestone (this spec):** backend JSON/job/metadata contract + app shell + core panels over
  everything ALPHA already does. **No net-new quant modules** — those are the roadmap.

## Architecture

New/grown structure under `apps/alpha-web/`:

```
src/alpha_web/
  app.py                 # create_app(): mount /api routers, serve the SPA (catch-all), /healthz, tearsheet
  api/                   # NEW — thin JSON routers, one module per concern
    __init__.py runs.py jobs.py catalog.py candles.py workspaces.py manifest.py
  _runs.py               # EXTEND: mtime + kind + filters + pagination; equity_series (ts+drawdown); trades
  _invoke.py             # EXTEND: Popen handle, start_new_session, cancel, list_jobs, id:/Last-Event-ID replay
  _catalog.py            # NEW: subprocess+cache `alpha info strategies/commands --json`, `alpha data symbols --json`
  _candles.py            # NEW: subprocess+cache `alpha data candles --json`
  _workspaces.py         # NEW: server-side named-layout JSON store under data_dir/web/workspaces
  static/                # BUILT SPA assets (committed); templates/ + _charts.py removed once SPA charts land
frontend/                # NEW — SPA source (Vite/React/TS/Dockview); excluded from ruff/mypy/pytest
apps/alpha-cli/src/alpha_cli/_schemas.py   # NEW — declarative strategy-param table
```

- **Thin backend:** subprocess `alpha`, parse `-> run <id>`, read `manifest.json`/parquet. The
  engine never runs in the web process.
- **Declarative panel manifest** (OpenBB-inspired, implemented as the frontend-owned panel
  registry): panels + data endpoints + param schemas keep the shell generic so later modules add
  panels with no shell change.
- **Global linked context:** a client `LinkedContext` (in-memory pub/sub) holding `{symbol, start,
  end}`; producers broadcast, `linked` panels refetch. Snapshotted into a workspace on save.
- **Savable named workspaces:** Dockview `toJSON()` persisted server-side under
  `data_dir/web/workspaces/<slug>.json`; localStorage restores the unsaved working layout.

## Backend API (thin JSON+SSE; all under `/api`, loopback only)

Runs & artifacts (wrap existing/new `_runs` helpers):
- `GET /api/runs?kind&symbol&verdict&passed&limit&offset` → `{total, items:[{run_id, kind, command,
  label, symbol|symbols, passed, verdict, mtime}]}`, **mtime-desc** (filesystem mtime, never a
  manifest field — manifests stay byte-stable and wall-clock-free).
- `GET /api/runs/{id}` → full manifest + `{kind, mtime, has_equity, has_trades, has_tearsheet,
  has_forecast}`.
- `GET /api/runs/{id}/equity` → `{ts, equity, drawdown}` · `/trades` → trade rows · `/forecast` →
  `{history_ts, history, forecast_ts, forecast, p10, p90}` · `/tearsheet` → `text/html` FileResponse.

Market data & metadata (CLI `--json` projections consumed via subprocess — so `alpha_web`'s import
surface stays `alpha_core.config` + `alpha_cli.RUN_DIRS`):
- `GET /api/candles/{symbol}?start&end&snapshot` → `{symbol, snapshot_id, bars:[{t,o,h,l,c,v}]}`
  (PIT-adjusted, from the new `alpha data candles --json`; cached on the store parquet's mtime).
- `GET /api/symbols` → `{symbols:[str]}` (`alpha data symbols --json`).
- `GET /api/strategies` → `[{name, params:[{name,type,default,min?,max?,choices?,help}],
  has_tier1_surrogate}]` (`alpha info strategies --json`: `known_strategies()` joined with the new
  `_schemas.STRATEGY_PARAM_SCHEMA`).
- `GET /api/commands` → `[{id, run_type, args, options:[{name,type,default,required,help,multiple,
  choices?}]}]` (`alpha info commands --json`: Typer→Click tree introspection; defaults come from the
  real signatures, zero duplication).
- The panel manifest is frontend-owned; `/api/commands` and `/api/strategies` remain the dynamic
  backend capability catalogs.

Jobs (extended `_invoke` + `api/jobs.py`):
- `POST /api/jobs` `{command, args?}` → `{job_id, status}` (launch; replaces `/runs` +
  `/console/run`).
- `GET /api/jobs` → live + this-session-finished jobs · `GET /api/jobs/{id}` → status + buffered
  lines.
- `GET /api/jobs/{id}/stream` → SSE; each `line` event carries `id:` so a reconnect with
  `Last-Event-ID` replays only missed lines; terminal `done`/`failed`/`cancelled`.
- `DELETE /api/jobs/{id}` → cancel (spawn `start_new_session=True`, cancel via
  `os.killpg(SIGTERM)`; status `cancelled`). Registry is **in-memory** — finished work is durable in
  the run store; a restart loses the live job list and orphans running subprocesses (documented
  tradeoff).

Workspaces (`_workspaces.py` + `api/workspaces.py`):
- `GET /api/workspaces` · `GET /api/workspaces/{slug}` · `PUT /api/workspaces/{slug}`
  `{name, linked_context, dockview}` · `DELETE /api/workspaces/{slug}`. Store:
  `data_dir/web/workspaces/<slug>.json`, traversal-guarded, plain JSON (UI state, not a run
  manifest).

## Panels (W1)

Each panel is a frontend registry entry → a `panels/registry.ts` component: **Run Browser** (AG Grid over
`/api/runs`) · **Run Detail** (A–F verdict, oos_metrics, gauntlet folds/nulls/cis/dsr/cpcv tables;
uPlot equity+drawdown; trades AG Grid; tearsheet iframe; forecast band) · **Strategy Lab / New Run**
(dynamic form from `/api/strategies`+`/api/commands`; `POST /api/jobs`; live SSE console) ·
**Price/Candle chart** (Lightweight Charts + linked context) · **Data Explorer** (`/api/symbols` +
pull form) · one generic **Result View** (optim/portfolio/cross-sectional/propfirm/forecast cells) ·
**AI Console** (command console + a prominent pointer that natural-language orchestration **is** the
`alpha_mcp` server — no LLM loop in `alpha_web`) · **Workspaces** manager. Shell adds Dockview
docking, a cmdk command palette mapped to CLI/MCP verbs, global symbol search, dark theme, and
keyboard shortcuts.

## New CLI surface (in `alpha_cli`, keeping the CLI the single source of truth)

- `alpha data candles SYMBOL --start --end [--snapshot] --json` — PIT-adjusted OHLCV via
  `_runner.load_bars` → `PointInTimeSource.as_of` (split-adjusted, future bars excluded, `--end` as
  an as-of cutoff). Bias-guarded.
- `alpha data symbols [--json]` — stored symbols (`ParquetStore.list_symbols`).
- `alpha info strategies [--json]` / `alpha info commands [--json]` — the metadata catalogs above.

## Determinism, DAG, look-ahead

- Manifests stay byte-stable (`write_manifest`: sorted keys, `allow_nan=False`) and
  `run_id = sha256(params)` (no wall-clock). Run time-ordering uses filesystem `st_mtime`, never a
  manifest field. Job `created_at` is memory-only. No new byte-stable surface, no determinism hazard.
- `alpha_web` gains **no new internal import** (all new data is CLI JSON over subprocess), so the
  `alpha_web sits atop the DAG` contract passes verbatim.
- The candles command reads through the one audited PIT seam and carries a `bias_guard` future-poison
  test — the chart shows exactly the bars a backtest would see.

## Testing (no network)

- FastAPI `TestClient(create_app())` over a temp `ALPHA_DATA_DIR` seeded with hand-written
  manifests + parquet (mirrors `tests/integration/test_web_app.py`,
  `tests/fixtures/cli_fixtures.seed_store`) — one test module per router.
- Job lifecycle via the `_invoke._command` fake-fast-command seam: list, cancel, `Last-Event-ID`
  replay.
- New CLI commands: `alpha data candles/symbols` + `alpha info strategies/commands`, incl. a
  `bias_guard` candles-PIT test and a catalog test asserting `backtest run.lookback == 252` comes
  from the Typer signature.
- `test_web_spa_assets.py` ties the committed `static/index.html` to the gate (a missing SPA build
  fails loud, not blank).
- Full CI gate green before each commit: ruff, ruff format --check, lint-imports, `mypy --strict`,
  `pytest -m "not network"`, `pytest -m bias_guard`.

## Offline CI with a Node/Vite tree

- Exclude `apps/alpha-web/frontend` from the Python gate via `[tool.ruff] extend-exclude` (mypy only
  walks `.py`; pytest `testpaths=["tests"]` never sees it) — the same precedent as the vendored
  Kronos dir.
- **Commit the prebuilt SPA assets** into `src/alpha_web/static/` so `uv sync` + `uv run alpha-web` +
  the TestClient serve the app with **zero Node**. Commit `frontend/package-lock.json`.
- A separate, **non-gating** `frontend-build` job runs `npm ci --offline && npm run build` only where
  Node exists, to catch drift. The Python CI never runs Node.

## Build order (vertical TDD slices)

1. JSON API over existing readers · 2. Job lifecycle · 3. Strategy + command catalog · 4. Candles ·
5. SPA scaffold + Run Browser · 6. Run Detail + charts (remove legacy Jinja/SVG) · 7. Strategy Lab +
live console · 8. Price chart + linked context · 9. Workspaces persistence · 10. Remaining result
views + AI console · 11. Docs (CLAUDE.md, README).

## Roadmap (post-milestone) — no shell redesign

Each net-new module = a new `packages/` module (below the DAG) + new `alpha` CLI command(s) writing
manifests into a new `RUN_DIRS` entry and/or `--json` projections + a frontend registry component.
Order: Options & Derivatives (`alpha_options`; vollib/FinancePy/
QuantLib) → Screener & News + providers (`alpha_screener` + `alpha_data` adapters; finviz/finnhub,
optional keyed Alpaca/TwelveData) → Risk monitor & scenario/what-if (`alpha_risk`; VaR/CVaR +
gs-quant-style re-pricing) → Multi-agent AI research desk (TradingAgents-style, in `alpha_mcp` /
optional `alpha_agents` app) → ML/RL sandbox (TensorTrade, heavy) at the tail.

## Out of scope (v1)

- In-app LLM agent loop (the MCP server is the conversational path).
- Authoring strategy **Python** at runtime (the form edits registered strategies' parameters).
- Multi-user, auth, remote hosting, websockets (SSE suffices for one local user).
- The net-new quant modules above (roadmap, each its own spec).
