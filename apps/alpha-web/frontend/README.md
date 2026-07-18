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
npm run build
```

CI requires zero lint warnings, the committed V8 coverage floors, fresh generated TypeScript API
definitions, a successful TypeScript/Vite build, and byte-identical committed assets.

`openapi.json` is generated from the backend by `scripts/generate_web_openapi.py`; the generated
`src/api/generated.ts` is authoritative. Keep handwritten API types to small aliases in
`src/api/types.ts`.
