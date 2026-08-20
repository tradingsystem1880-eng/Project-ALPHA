# Alpha Atlas

A developer-only, local-only, **read-only** explanation layer for Project
ALPHA: a deterministic knowledge graph over the repository (architecture,
research lifecycle, CLI/MCP/web surfaces, tests, docs), an interactive viewer,
generated mermaid maps, and "Generate AI Context" prompt packs.

Atlas never touches trading logic, research/CLI/MCP authority, or governance.
It is not part of the Alpha runtime; nothing in the platform imports it. Every
claim carries a **computed** evidence level — `unknown < declared <
implemented < connected < tested` (`observed` is reserved for a future runtime
layer and never emitted) — with file:line provenance. A file existing is never
"the feature exists".

Design doc: `docs/superpowers/plans/2026-08-20-project-alpha-atlas-design.md`.

## Commands (from `tools/alpha-atlas/`)

```sh
uv sync                                        # install (isolated project, not a workspace member)
uv run python -m alpha_atlas.generate          # regenerate graph + views + docs/atlas
uv run python -m alpha_atlas.generate --check  # freshness check (byte-exact)
uv run python -m alpha_atlas.generate --refresh-cli   # re-enumerate the CLI cache (subprocess)
uv run alpha-atlas                             # serve UI+API on http://127.0.0.1:8803
./gate.sh                                      # lock check, ruff, mypy --strict, pytest, --check
cd frontend && npm install && npm run dev      # SPA dev server (proxies /api to :8803)
cd frontend && npm test && npm run build       # vitest models + production build (serves from dist/)
```

Root guard: `tests/unit/test_atlas_consistency.py` (stdlib-only) proves the
committed outputs stay internally consistent; freshness itself is enforced
only by the Atlas gate (owner decision 2026-08-20). The UI shows a stale
banner when any recorded input file changed.

## Layout

- `architecture/atlas/schema/` — graph JSON Schema (20 node kinds, 8 edge
  types, reserved Phase-7 runtime fields)
- `architecture/atlas/definitions/` — curated definitions (purpose, limits,
  safe-change notes) with mandatory `owner/created_from/last_verified_commit/
  confidence` metadata and sha256-pinned code anchors; a changed anchor
  downgrades to a visible "needs re-verification", never silent stale prose
- `architecture/atlas/cache/` — committed `alpha info commands --json` cache
  (an input, refreshed only explicitly)
- `architecture/atlas/generated/` — `graph.json` (single-line canonical),
  `inputs.json` (exact files read + sha256; the staleness key), `views/`
  (incl. the Unknowns review queue)
- `docs/atlas/` — five generated mermaid views (system map, research flow,
  data lineage, frontend flow, CLI flow)
- `src/alpha_atlas/` — stdlib-only `core/` + `generators/`; FastAPI confined
  to `backend/` (loopback, read-only, jailed excerpts, no subprocesses)
- `frontend/` — Vite + React (alpha-web's stack) + React Flow; five views:
  Research Lifecycle, System Map, Code Explorer, Data Lineage, Change Impact

## The core path

Open the UI → Research Lifecycle → click any step (Idea … Strategy Promotion)
→ the panel shows its purpose, computed evidence with provenance, implementing
files (click for jailed excerpts), defining ADRs/specs, validating tests,
limitations, and safe-change notes → **Generate AI Context** builds the
12-section prompt pack (target area, current state, intent, implementation,
dependencies, do-not-change, files to modify/not modify, test requirements,
validation commands, open questions, documentation) → **Copy for Codex /
Claude**.
