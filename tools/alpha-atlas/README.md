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

## Query project intent, features, tasks and decisions

From `tools/alpha-atlas/`, query the current tracked documents without starting the viewer:

```sh
uv run python -m alpha_atlas.context query H26 --kind feature --format markdown
uv run python -m alpha_atlas.context query 'research precedes strategy' --kind project --format text
uv run python -m alpha_atlas.context query 'stage contract' --kind task --limit 4
uv run python -m alpha_atlas.context query 'sealed confirmation' --kind decision --limit 4
```

`--kind` accepts `all`, `project`, `feature`, `task`, `decision`, `history`, `reference`.
Project intent comes from the manual, architecture and context maps; feature scope comes from
the canonical readiness checklist and specs; tasks come from dated plans; decisions come from
ADRs; build history and stable rules/governance/operations remain distinguishable. These source
families are direct-directory allowlists for tracked `.md`, `.txt` and `.json` files. The tool
does not follow links or recursively ingest arbitrary folders. Stage a new intended public source
before querying it; untracked private drafts remain excluded. Tracked sources are read from the
current worktree, including staged and unstaged edits. Deleted, unreadable, oversized, invalid-UTF-8
or symlink sources fail loud. Owner stores, credentials, private suites and `.alpha/state` are
never indexed. Adding a tracked secret to a public source family remains forbidden by repository
policy; retrieval is not a content sanitizer.

Every query word must occur in an excerpt or its inherited heading. Ranking is deterministic:
heading matches first, then text matches, path and line. Each excerpt retains at most 40 source
lines, its full heading ancestry, kind, line range and exact file SHA-256. The default selection
is eight excerpts and 12,000 UTF-8 source-text bytes; metadata is additional. Configure `--limit`
(1–20), `--budget-bytes` (256–40,000), and `--ttl-seconds` (1–86,400; default one hour).
All matching excerpts omitted by count or byte budget remain cited with their reason. More than
500 matches fails with a request to narrow the query. No matches is explicit. Read omitted matches
and adjacent source sections when needed; lexical selection cannot detect or resolve contradictions
or guarantee that every relevant fact was retrieved. Dated plans retain their status and history;
search never declares a feature complete or makes a historical decision current.

JSON is the default reusable handoff. Save it with the existing ignored task evidence, then
validate it immediately before consumption (create the task evidence directory if needed):

```sh
uv run python -m alpha_atlas.context query H26 --kind feature > ../../.alpha/state/context-h26.json
uv run python -m alpha_atlas.context check ../../.alpha/state/context-h26.json
```

Validation re-reads the source corpus and replays the exact query. Added, removed or changed
tracked source files, changed retrieval code, expired/future-dated receipts, altered excerpts,
omission lists or other payload changes fail with exit 2. A fresh receipt prints `status: fresh`
and `authority: none`; the receipt hash is an integrity identifier, not a signature or approval.
Markdown and text output are readable views; retain JSON for validation. Query/check do not write
files themselves or refresh stale receipts. A source change requires a new query. This is a context
filesystem over existing canonical documents, separate from bulk-document storage, archival backup,
scientific context admission and Mac recovery. Ignored receipts remain local until separately
preserved; Git-tracked and pushed sources supply durable history.

The [delivery record](../../docs/superpowers/plans/2026-10-30-queryable-context-filesystem.md)
maps the primary ICM paper's five roles to existing ALPHA paths. Receipt expiry and mechanical
invalidation are ALPHA adaptations; no autonomous-quality or backup-performance claim is made.
