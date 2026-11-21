---
owner: web workstation
sources:
  - apps/alpha-web/src/alpha_web/*.py
  - apps/alpha-web/src/alpha_web/api/**
  - apps/alpha-web/frontend/index.html
  - apps/alpha-web/frontend/src/**
  - apps/alpha-web/frontend/package.json
verified: 3b61fc50d4488d7a
---

# alpha-web workspace
## Purpose
The ALPHA Workstation: a local FastAPI backend and a React single-page app.
It runs `alpha` as a subprocess for every action, except that Setup Lab reads stored files directly, bounded and read-only
([rule](../../docs/reference/invariants/web-api-reads.md#reads-and-writes)). It never runs the engine, reads SQLite itself or grants authority.

## Read first
| Read | Section | When |
|---|---|---|
| [engineering rules](../../docs/reference/invariants/engineering.md) | Subprocess boundary | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [web API invariants](../../docs/reference/invariants/web-api.md) | Calling the CLI | always |
| [web API reads and writes](../../docs/reference/invariants/web-api-reads.md) | Reads and writes | changing what the backend reads or writes |
| [web run detail](../../docs/reference/invariants/web-run-detail.md) | Run detail binding | changing the run detail, journey or Setup Lab panels |
| [web API invariants](../../docs/reference/invariants/web-api.md) | — | adding a route or changing the API contract |
| [web frontend invariants](../../docs/reference/invariants/web-frontend.md) | — | changing a panel, chart or the browser app |
| [web research surfaces](../../docs/reference/invariants/web-research.md) | — | changing the assistant, investigations, rules or scans |
| [what this part is for](../../docs/reference/project/components/web-workstation.md) | — | why it exists; before you keep, shelve or remove it |
| [Setup Lab](../../docs/reference/project/components/setup-lab.md) | — | a Setup Lab screen change (page is enough) |
| [alpha-web README](README.md) | Code map | finding a module or its tests |

## How to change it
- Code, tests and checks: [code map](README.md#code-map), [change loop](README.md#change-loop); `uv run python scripts/gate.py check`.

## Outputs
- The owning document: `docs/reference/invariants/web-api.md` or `web-frontend.md`.
