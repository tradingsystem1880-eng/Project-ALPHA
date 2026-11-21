---
owner: project layer
sources:
  - apps/alpha-cli/src/alpha_cli/setup_cmds.py
  - apps/alpha-web/src/alpha_web/api/setup_runs.py
  - apps/alpha-web/frontend/src/panels/SetupLabPanel.tsx
  - packages/alpha-study/src/alpha_study/setup/**/*.py
verified: 9dcec26aaf2f2fc5
---

# Setup Lab

Setup Lab is golden path 2: the owner describes a chart setup ("a double bottom", "a pullback in an
uptrend") and sees every past match, and then what happened after, before any trading rule is fixed. It has
three commands and one Workstation screen. The screen shows the data health finding beside each result that is not a pass.
Older runs read “Data health: not recorded.”

## Why it exists

Many of the owner's ideas are chart setups, not machine-learning models, and the owner wants them judged by
the same ledger and statistics as RD-Agent's ideas
([design brief](../owner-decisions-2.md#2026-11-14-the-retail-traders-fit-is-the-design-brief)). Looking at
the matches first, with the outcome hidden, keeps the owner from fitting a rule to what happened next. The
work order that put it first is in [volume 4](../owner-decisions-4.md#2026-11-18-working-order-golden-paths-1-and-2-reach-the-screen-first).

## Its job in the research loop

Steps 1 to 4 of the [research loop](../overview.md#the-research-loop) for a chart setup: state the idea,
look at it, measure it, then trade it with declared exits. It is a way of working, not a strategy.

## Intended design

- A setup is a small TOML spec: a name, assets, a daily timeframe, ordered filters, an optional trigger and
  named reference levels. Expressions read only bars already seen
  ([setup causality](../../invariants/study.md#setup-causality)).
- A condition may read a context series (positioning or short volume) declared in a `[context]` table. The find
  then counts the days the condition was true and its separate spells, and the screen shows the plain label
  `short-context-history` under three years of such data ([rules](../../invariants/cli-setups.md#setup-context)).
- `alpha setup find <spec>` records every match and counts separate occurrences (days within ten bars of
  each other are one). It draws contact sheets that stop at the entry open: nothing after entry is computed
  or drawn until the outcome is asked for.
- The detail answer carries only the first match sheet (about 1.5 MB against 4.5 MB before); the others come one at a time from
  `GET /api/setup/runs/{find_id}/sheets/{kind}/{number}`. The screen shows its heading and coverage before the detail arrives.
  Study and trade figures are drawn in light colours, to sit on the default light page; older stored figures stay dark.
- `alpha setup study <find_id>` measures net forward returns after each occurrence against drift and
  against random dates, with one counted exploratory trial, a figure and citable facts.
- `alpha setup trade <find_id>` trades the occurrences long or short with declared exits (stop, target, time),
  after per-asset costs, in percent and in risk units of the initial stop (R). The opposite direction on the
  same entries is an uncounted control.
- `alpha setup show <id> [<id> ...]` reads stored studies or trades: its evidence word and place in the setup's family.
- The Workstation screen (Research → Setup Lab) only reads stored results through
  `GET /api/setup/runs`.

## What is real today

All three commands run; each has a smoke test, and on 2026-11-17 a double-bottom spec ran on stored SPY and
BTC/USDT daily bars as a system test, not evidence of an edge. The screen exists and is read-only. Not built:
sizing, the owner's setup library and the daily scan with export, and starting a find from the screen. See the
capabilities on [STATUS.md](../../../../STATUS.md) and the tool cards for [find](../../../../research/tools/setup-find.md),
[study](../../../../research/tools/setup-study.md) and [trade](../../../../research/tools/setup-trade.md).

### To change this screen

- Each study and trade shows a reading block: its evidence word with a four-step scale,
  the stored sentence and its place in the idea's family; old records say "(old wording)".
- Files: the panel `apps/alpha-web/frontend/src/panels/SetupLabPanel.tsx` and its model `setupLabModel.ts` (registered in `shell/documents.ts`); the
  backend `apps/alpha-web/src/alpha_web/api/setup_runs.py` with `_setup_runs.py`.
- The routes (`GET /api/setup/runs` and `/{find_id}`) read stored files directly through `_setup_runs` (bounded, allowlisted, no `alpha` subprocess, unlike most
  routes). The screen starts nothing, and missing parts read "not recorded". Rules:
  [web API reads and writes](../../invariants/web-api-reads.md#reads-and-writes).
- After a backend route change, from the repository root: `uv run python scripts/generate_web_openapi.py`, then `uv run python
  scripts/check_openapi_operations.py --write`, then `uv run python scripts/gate.py check`.
- Frontend loop, in `apps/alpha-web/frontend`: `npm ci`; `npm run generate:api`; `npm run lint -- --deny-warnings`; `npm run build`; `npm run test:coverage`;
  `npm run test:e2e:built`. Commit `src/api/generated.ts`. Never edit or commit the built bundle `src/alpha_web/static/app`.
- Tests owed: a backend test for every route, including the failure path (`tests/unit/test_web_setup_runs.py`), a vitest test for new model logic
  (`setupLabModel.test.ts`) and a browser spec when behaviour changes (`frontend/e2e/setup-lab.spec.ts`). Colours follow the
  [theme contract](../../invariants/web-frontend.md#workstation-themes-and-readability).
- Screenshots (owner decision 2026-10-07): one baseline per platform, `*-darwin.png` and `*-linux.png`, both at a 2% pixel tolerance. Re-take the Linux ones in
  the `mcr.microsoft.com/playwright:v<version>-noble` container (`--platform linux/amd64`) against a locally started backend, never by copying macOS images.
- The default browser lane starts its own backend on port 8802 (set `ALPHA_PLAYWRIGHT_PORT` for another; never 8801). Its SPY and BTC/USDT bars are synthetic
  fixtures, labelled as such, not market evidence ([web invariants](../../invariants/web-frontend.md#tests)).

## Where it lives

- **Workspaces:** none (code sits in `apps/alpha-cli`, `apps/alpha-web` and `packages/alpha-study`, owned by
  [command line](command-line.md), [Workstation](web-workstation.md) and [strategies and signals](strategies-and-signals.md)).
- **Capabilities:** `setup-find`, `setup-study`, `setup-trade`
- Code: `apps/alpha-cli/src/alpha_cli/setup_cmds.py`, `apps/alpha-cli/src/alpha_cli/spine/setup_find.py`,
  `packages/alpha-study/src/alpha_study/setup/`, `apps/alpha-web/src/alpha_web/api/setup_runs.py`,
  `apps/alpha-web/frontend/src/panels/SetupLabPanel.tsx`.
- Tests: `tests/unit/test_setup_find.py`, `test_setup_study.py`, `test_setup_trade.py`,
  `test_web_setup_runs.py`; smoke checks `tests/smoke/test_setup_*_smoke.py`.
- How to change it: [apps/alpha-cli/CONTEXT.md](../../../../apps/alpha-cli/CONTEXT.md) and
  [apps/alpha-web/CONTEXT.md](../../../../apps/alpha-web/CONTEXT.md).
- **Plan:** the [three golden paths](../../../roadmap/production-scope.md#the-three-golden-paths) in the checklist.

## Decisions and open questions

- Decided 2026-11-18 (orchestrator's order, reversible; see the [decisions log](../owner-decisions.md), volume 4): Setup Lab comes first.
- Open: the reserve policy for setups. Today a setup run holds nothing back
  ([ideas and things considered](../ideas-and-considered.md#open-questions)).

## Never

- Never show or compute anything after the entry open in a find; outcomes appear only in study and trade.
- Never let an expression read a bar it could not yet have seen.
- Never present a setup result as evidence of an edge; it is one counted look.
- The rules: [study invariants](../../invariants/study.md) and [CLI runs](../../invariants/cli-runs.md).
