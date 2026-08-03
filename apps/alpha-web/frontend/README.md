# ALPHA Workstation frontend

The Workstation is a Vite/React/TypeScript SPA served by `alpha_web`. Dockview owns the desktop
layout; Lightweight Charts and uPlot render market and analytics series; TanStack Table/Virtual
power dense blotters; cmdk provides the command palette.

The FastAPI backend remains a thin JSON+SSE surface over `alpha` subprocesses and run-store reads.
Do not add business logic or direct engine/data-package imports to the frontend or web server.

## Development

From this directory:

```bash
npm ci
npm run dev
```

The development server proxies API traffic according to `vite.config.ts`. For the packaged app,
`npm run build` writes byte-pinned assets to `../src/alpha_web/static/app`.

## Required gate

```bash
npm run lint -- --deny-warnings
npm run test:coverage
npm run generate:api
npm run test:e2e
```

CI requires zero lint warnings, the committed V8 coverage floors, fresh generated TypeScript API
definitions, a successful TypeScript/Vite build, and byte-identical committed assets. The browser
gate builds the production SPA, serves it through Vite preview with deterministic API mocks, checks
all six curated desks at 1280×720, 1440×900, and 1920×1080, exercises the desk selector by keyboard,
runs the 25,000-bar/200-annotation interaction fixture at the reference viewport, and fails on any
serious or critical axe violation. Install Chromium once locally with
`npx playwright install chromium` before running `npm run test:e2e`.

`openapi.json` is generated from the backend by `scripts/generate_web_openapi.py`; the generated
`src/api/generated.ts` is authoritative. Keep handwritten API types to small aliases in
`src/api/types.ts`. New Workstation control/ML/chart consumers should use the explicit `/api/v3`
aliases; unversioned `/api` routes remain for compatibility.
