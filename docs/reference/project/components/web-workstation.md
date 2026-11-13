---
owner: project layer
sources:
  - apps/alpha-web/CONTEXT.md
  - docs/adr/0021-research-workstation-read-plane-and-command-center.md
  - docs/roadmap/capabilities.toml
verified: f89aa1bb78af
---

# Web workstation

The Workstation is ALPHA in a browser on the owner's own computer: price charts, research cases,
backtest reports, job and provider status, and the results of RD-Agent and Qlib runs.

## Why it exists

The owner is not a programmer. Charts and screens are how the owner explores markets and reads
evidence before deciding ([ADR-0021](../../../adr/0021-research-workstation-read-plane-and-command-center.md)).

## Its job in the research loop

It shows every step of the [research loop](../overview.md#the-research-loop) and lets the owner
start supported actions. It never does the work itself: each action is a call to the
[command line](command-line.md).

## Intended design

- A local web server (FastAPI) and a React app, reachable only from the same computer.
- Every action runs the `alpha` command as a separate process; the browser holds no authority.

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md). Start it with `uv run alpha-web`.

## Where it lives

- **Workspaces:** `apps/alpha-web`
- **Capabilities:** `workstation`, `price-charts`
- Code: `apps/alpha-web/src/alpha_web/` (server), `apps/alpha-web/frontend/` (browser app).
- Tests: `tests/smoke/test_web_smoke.py`, `apps/alpha-web/frontend/e2e/`.
- How to change it: [apps/alpha-web/CONTEXT.md](../../../../apps/alpha-web/CONTEXT.md).
- Decision records: [ADR-0021](../../../adr/0021-research-workstation-read-plane-and-command-center.md).
- Screens for other parts (for example RD-Agent's native job result) are claimed by those parts.

## Decisions and open questions

- No owner decision about this part is in the [owner decisions log](../owner-decisions.md) yet.
- Open: no next step is recorded for the Workstation itself; new screens arrive with the parts they show.

## Never

- Never run the engine, read the database directly, or grant authority from the browser.
- Never hand-edit the generated browser bundle.
- The rules: [web API invariants](../../invariants/web-api.md) and
  [web frontend invariants](../../invariants/web-frontend.md).
