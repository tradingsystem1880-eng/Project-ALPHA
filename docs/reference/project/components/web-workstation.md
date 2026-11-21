---
owner: project layer
sources:
  - apps/alpha-web/CONTEXT.md
  - docs/adr/0021-research-workstation-read-plane-and-command-center.md
verified: 6a4d2d82a3dd6f31
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

A run made by `alpha test` (a rule test) opens with its own first section, above the summary:

- **What was tested**: the idea in the owner's words, the rule as one plain sentence, the asset,
  data source, period, costs, the trial count at the time and the run's labels.
- **Worth a look**: each flag from the diagnostic pass, as its stored sentence.
- **Audit**: each mechanical check with PASS, FLAG or NOT-CHECKED and its detail. No grade.
- **Against buy and hold**, **If things were slightly different**, **By year** and
  **Macro during the worst drawdown** (or one line saying why it is not available).

Every number comes from the run's stored `manifest.json` and `diagnostics.json`; a missing one
reads `not recorded` with the stored reason. The toolbar says `rule test` and lists the labels,
and the Run library names the run `rule test <name> <bar size> — <asset> · …` (for example `D1`).
The rule-test capability itself belongs to the [command line](command-line.md); this part shows it.

## Where it lives

- **Workspaces:** `apps/alpha-web`
- **Capabilities:** `workstation`, `price-charts`, `market-overview`, `follow-today-screen`, `idea-workspace`
- Code: `apps/alpha-web/src/alpha_web/` (server), `apps/alpha-web/frontend/` (browser app).
- Tests: `tests/smoke/test_web_smoke.py`, `apps/alpha-web/frontend/e2e/`.
- How to change it: [apps/alpha-web/CONTEXT.md](../../../../apps/alpha-web/CONTEXT.md).
- Decision records: [ADR-0021](../../../adr/0021-research-workstation-read-plane-and-command-center.md).
- Screens for other parts (for example RD-Agent's native job result) are claimed by those parts.
- **Plan:** [stage 10](../../../roadmap/production-scope-3.md#10-screens) of the checklist.

## Decisions and open questions

- Decided 2026-11-14 ([decisions log](../owner-decisions.md), later volumes): keep the user interface; it is how the owner understands the project, and every
  kept capability should be visible there in plain English
  ([log](../owner-decisions-2.md#2026-11-14-keep-the-user-interface)). Charts come with text, in a quant
  style ([log](../owner-decisions-2.md#2026-11-14-the-interface-shows-charts-with-text-in-a-quant-style-and-is-finished-later)).
- Decided 2026-11-18: the screen chrome must not be all black. Light is the default (a Light, Dim or Dark
  switch exists in `apps/alpha-web/frontend/src/theme/`); single charts may be dark. UI design is then
  deferred again, "get the project working first"; only the RD-Agent view is reshaped
  ([log](../owner-decisions-5.md#2026-11-18-the-workstation-must-not-be-all-black-ui-design-waits)).
- Decided 2026-11-18: the idea-journey layout is approved and is the style to reuse for other result views
  ([log](../owner-decisions-5.md#2026-11-18-the-idea-journey-layout-is-approved)).
- Open: when to resume Workstation design, and what design the owner wants; ask for reference screenshots.
- Screens that exist for the new golden paths: [Setup Lab](setup-lab.md) (stored results only) and
  Kronos Studio ([forecasting](forecasting.md)). Neither may be removed when slimming.

## Never

- Never run the engine, read the database directly, or grant authority from the browser.
- Never hand-edit the generated browser bundle.
- The rules: [web API invariants](../../invariants/web-api.md) and
  [web frontend invariants](../../invariants/web-frontend.md).
