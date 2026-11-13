---
owner: web workstation
sources:
  - apps/alpha-web/src/alpha_web/*.py
  - apps/alpha-web/src/alpha_web/api/**
  - apps/alpha-web/frontend/src/**
  - apps/alpha-web/frontend/package.json
verified: d0fffa796f8e
---

# alpha-web workspace

## Purpose

The ALPHA Workstation: a local FastAPI backend (JSON and server-sent events) in
`apps/alpha-web/src/alpha_web/` and a React single-page app in `apps/alpha-web/frontend/`. It sits
on top of the import graph: it imports only `alpha_core` and public `alpha_cli` seams (import-linter
contracts "alpha_web imports only public platform surfaces" and "alpha_web sits atop the DAG"), and
runs `alpha` as a subprocess for every action. It never runs the engine, reads SQLite itself, or
grants authority.

## Read first

| Read | Section | When |
|---|---|---|
| [engineering rules](../../docs/reference/invariants/engineering.md) | Subprocess boundary | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [web API invariants](../../docs/reference/invariants/web-api.md) | Calling the CLI | always |
| [web frontend invariants](../../docs/reference/invariants/web-frontend.md) | No authority in the browser | changing the browser app |
| [web API invariants](../../docs/reference/invariants/web-api.md) | Adding a route | adding or changing a route |
| [web API invariants](../../docs/reference/invariants/web-api.md) | API contract | changing a response model or the OpenAPI contract |
| [web frontend invariants](../../docs/reference/invariants/web-frontend.md) | — | changing a panel, chart or the browser app |
| [web research surfaces](../../docs/reference/invariants/web-research.md) | — | changing the assistant, investigations, rules, scans or Study tab |
| [command line native](../../docs/reference/invariants/cli-native.md) | Results and inspection | showing a native job result (see `api/native_results.py`) |
| [command line research](../../docs/reference/invariants/cli-research.md) | Projections and dossiers | showing research case state |
| [command reference](../../docs/reference/commands.md) | — | finding the `alpha` command a route should call |
| [what this part is for](../../docs/reference/project/components/web-workstation.md) | — | why it exists; before you keep, shelve or remove it |

## How to change it

- Backend code: `apps/alpha-web/src/alpha_web/` (routes in `api/`; copy a sibling such as
  `api/native_results.py` with its adapter `_native_results.py`). Frontend: `frontend/src/`
  (`panels/`, `shell/`, `components/`, `api/`). The built bundle `src/alpha_web/static/app` is
  committed; never edit it by hand.
- Backend tests: `tests/unit/test_web_*.py`, `tests/integration/test_web_api_*.py`,
  `tests/integration/test_openapi_safe_routes.py`. Frontend unit tests sit next to the code as
  `frontend/src/**/*.test.ts` (vitest); browser tests in `frontend/e2e/` (Playwright).
- After a backend route change, from the repository root:
  1. `uv run python scripts/generate_web_openapi.py` (rewrites `frontend/openapi.json`);
  2. `uv run python scripts/check_openapi_operations.py --write` (operation classification and
     `docs/governance/capability-authority-matrix.md`);
  3. `uv run python scripts/gate.py check`.
- Frontend loop, in `apps/alpha-web/frontend`: `npm ci`; `npm run generate:api`;
  `npm run lint -- --deny-warnings`; `npm run build` (also rebuilds the committed bundle);
  `npm run test:coverage`; browser lanes `npm run test:e2e:built`. Commit `src/api/generated.ts`
  and the bundle with the source.
- CI runs the whole loop as `uv run python scripts/gate.py component frontend`; it fails if the
  generated client or the bundle differs from what is committed.

## Outputs

- Tests: a backend test for every route (including the CLI-failure path), a vitest model test for
  new panel logic, and a browser spec when a page's behaviour changes.
- Regenerated `frontend/openapi.json`, `src/api/generated.ts`, the static bundle and the governance
  classification, as above.
- The owning document: `docs/reference/invariants/web-api.md` or `web-frontend.md`.
