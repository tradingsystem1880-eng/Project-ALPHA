# Project Alpha Atlas — design and implementation plan

```json
{
  "schema_version": 1,
  "title": "Project Alpha Atlas: local knowledge-graph and explanation layer",
  "context": "Project ALPHA is AI-built; the owner's bottleneck is understanding, not functionality. Atlas is a permanent developer-only, local-only, read-only understanding layer: a deterministic generated architecture graph, an interactive React Flow UI, auto-generated mermaid docs, and a 12-section Generate-AI-Context prompt-pack builder. It distinguishes computed evidence levels (unknown/declared/implemented/connected/tested/observed) and never claims a feature exists because a file exists. It lives entirely in greenfield unprotected paths (tools/alpha-atlas, architecture/atlas, docs/atlas) as an isolated uv project outside the workspace, consumes existing awareness seams (gate.py index output, alpha info commands --json, openapi.json, import-linter tables, uniform ADR headers, rule paths globs), and changes no Alpha runtime, authority, or governance surface.",
  "assumptions": [
    {
      "statement": "architecture/, tools/, and docs/atlas/ are unprotected greenfield; a new isolated uv project there trips no harness guard, no MODULE MAP drift test, and needs no import-linter contract",
      "verified_by": "gate.py _PROTECTED_EXACT/_PROTECTED_PREFIXES review (scripts/gate.py:97-128) and tests/unit/test_repo_awareness_drift.py parametrization (packages/*/src, apps/*/src only)"
    },
    {
      "statement": "The CLI tree, MCP tools, OpenAPI operations, ADR headers, and import-linter contracts are all machine-enumerable today without importing alpha_* packages",
      "verified_by": "alpha info commands --json (info_cmds.py:101), AST idiom in scripts/check_openapi_operations.py:76, committed apps/alpha-web/frontend/openapi.json, uniform **Status:**/**Date:** headers across all 34 ADRs, [tool.importlinter] in root pyproject.toml"
    },
    {
      "statement": "alpha-web's frontend stack is React ^19.2.7 / Vite ^8 / TypeScript ~6 with vitest+oxlint, and contains no graph-rendering dependency, so Atlas matching it plus @xyflow/react causes no ecosystem split",
      "verified_by": "apps/alpha-web/frontend/package.json and package-lock.json grep for reactflow/d3/dagre/elkjs/mermaid (zero matches)"
    },
    {
      "statement": "Root pytest can import a stdlib-only Atlas core via sys.path insertion without adding root dependencies or editing guarded pyproject sections",
      "verified_by": "pyproject.toml [tool.pytest.ini_options] pythonpath review; the consistency test inserts tools/alpha-atlas/src itself"
    }
  ],
  "alternatives_considered": [
    "Place Atlas under packages/ or apps/ as a workspace member: rejected — trips the parametrized MODULE MAP drift test, requires a 15th import-linter contract, and couples a dev tool into the production DAG",
    "Extend scripts/harness_awareness.py build_index directly: rejected for v1 — protected control-plane file requiring gate.py ack per edit; consuming its output achieves extension without forking",
    "Server-rendered figures (matplotlib pipeline) instead of React Flow: rejected — the mandate is an interactive clickable graph; static bytes cannot serve NodePanel/ChangeImpact interaction",
    "TypeScript compiler (ts-morph) for frontend scanning instead of guarded regex: deferred — adds a node toolchain to the Python generation pipeline; regex with fail-loud openapi joins and count floors is sufficient for the house-controlled client.ts"
  ],
  "pre_mortem": [
    "Generated-output gate friction: if the root gate byte-checked Atlas output, every unrelated commit would force a slow subprocess-dependent regen and Atlas would be hated — freshness is Atlas-gate-only; the root test checks internal consistency only; the UI shows a stale banner",
    "client.ts regex brittleness: a client refactor silently drops frontend edges — every extracted path must join an openapi.json path or generation fails listing orphans, with a >=100 method-count floor; ts-morph escalation documented",
    "Curated-definition rot: renamed modules turn curated prose into stale lies, the exact failure Atlas exists to prevent — mandatory owner/created_from/last_verified_commit/confidence metadata, per-anchor content hashes downgrading entries to a visible needs-re-verification state, and generation failing on dangling node references",
    "Scope creep into a mini platform: weeks of graph infrastructure before any usable outcome — Milestone A (Research Lifecycle Explorer with NodePanel and Generate AI Context) must be demonstrably usable before any Milestone-B slice starts",
    "React Flow illegibility at ~500 module nodes: views are pre-sliced subgraphs, SystemMap expands one component at a time, mermaid emitter hard-caps 40 nodes per diagram and fails rather than emitting an unreadable graph"
  ],
  "slices": [
    {
      "title": "S0 design doc (this document) with valid FeaturePlan front block",
      "verify": "uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-08-20-project-alpha-atlas-design.md",
      "expected": "plan-check reports the plan as valid",
      "rollback": "git rm the document",
      "files": ["docs/superpowers/plans/2026-08-20-project-alpha-atlas-design.md"],
      "status": "done"
    },
    {
      "title": "S1 scaffold + schema + minimal generator with importlinter extractor as thin end-to-end proof",
      "verify": "cd tools/alpha-atlas && uv run pytest -q && uv run ruff check . && uv run mypy src; and root: uv run ruff check .",
      "expected": "14 contract nodes with source/forbidden lists in graph.json; two consecutive runs byte-identical; validator fails loud on a dangling edge; root ruff clean",
      "rollback": "git checkout -- tools/alpha-atlas architecture/atlas && git clean -fd tools/alpha-atlas architecture/atlas",
      "files": ["tools/alpha-atlas/pyproject.toml", "tools/alpha-atlas/src/alpha_atlas/core/model.py", "tools/alpha-atlas/src/alpha_atlas/generators/importlinter.py", "tools/alpha-atlas/src/alpha_atlas/generate.py", "architecture/atlas/schema/atlas-schema.json"],
      "status": "done"
    },
    {
      "title": "S2 research-lifecycle vertical data: docs_scan, curated definitions with anti-drift metadata, workflow+entity extractor with anchor verification, tests_map, minimal evidence resolver",
      "verify": "cd tools/alpha-atlas && uv run pytest -q",
      "expected": "34 ADR doc nodes; 10 workflow nodes + 6 research-entity nodes with verified control-store anchors; schema test rejects a definition missing owner/created_from/last_verified_commit/confidence; rot-guard test fails on a bogus anchor; lifecycle nodes carry validates edges",
      "rollback": "git checkout -- tools/alpha-atlas architecture/atlas && git clean -fd tools/alpha-atlas architecture/atlas",
      "files": ["tools/alpha-atlas/src/alpha_atlas/generators/docs_scan.py", "tools/alpha-atlas/src/alpha_atlas/generators/workflow.py", "tools/alpha-atlas/src/alpha_atlas/generators/tests_map.py", "architecture/atlas/definitions/research-lifecycle.json", "architecture/atlas/definitions/data-lineage.json"],
      "status": "done"
    },
    {
      "title": "S3 minimal viewer: read-only backend (meta/graph/views/node/excerpt with jail) + frontend scaffold + React Flow ResearchLifecycle view + NodePanel",
      "verify": "cd tools/alpha-atlas && uv run pytest -q; cd frontend && npm test; manual: open the UI, click D1",
      "expected": "jail tests pass (symlink escape, dot-dot, denylist); clicking D1 shows research_d1.py:1078, its tests, and ADR-0019..0027 links",
      "rollback": "git checkout -- tools/alpha-atlas && git clean -fd tools/alpha-atlas",
      "files": ["tools/alpha-atlas/src/alpha_atlas/backend/app.py", "tools/alpha-atlas/frontend/src/views/ResearchLifecycle.tsx", "tools/alpha-atlas/frontend/src/components/NodePanel.tsx"],
      "status": "pending"
    },
    {
      "title": "S4 Generate AI Context: pure prompt_pack core, POST endpoint, NodePanel copy-context-for-Codex button — closes Milestone A",
      "verify": "cd tools/alpha-atlas && uv run pytest -q tests/test_prompt_pack.py; manual walkthrough of the Definition-of-Done path",
      "expected": "all 12 sections in fixed order with correct DO-NOT-CHANGE and VALIDATION-COMMANDS content; lifecycle explorable end-to-end with copyable context",
      "rollback": "git checkout -- tools/alpha-atlas && git clean -fd tools/alpha-atlas",
      "files": ["tools/alpha-atlas/src/alpha_atlas/core/prompt_pack.py"],
      "status": "pending"
    },
    {
      "title": "S5 python modules + components extractors + full evidence resolver including unknown and the Unknowns review queue",
      "verify": "cd tools/alpha-atlas && uv run pytest -q",
      "expected": "known edge alpha_cli.research_d1 -> alpha_research.* present; an undocumented/untested/unlinked module resolves to unknown, not implemented; observed never emitted",
      "rollback": "git checkout -- tools/alpha-atlas architecture/atlas && git clean -fd tools/alpha-atlas architecture/atlas",
      "files": ["tools/alpha-atlas/src/alpha_atlas/generators/python_modules.py", "tools/alpha-atlas/src/alpha_atlas/generators/components.py", "tools/alpha-atlas/src/alpha_atlas/core/evidence.py"],
      "status": "pending"
    },
    {
      "title": "S6 CLI + MCP extractors with committed cli cache",
      "verify": "cd tools/alpha-atlas && uv run pytest -q",
      "expected": "178 cli_command leaves, 62 mcp_tool nodes, argv-AST maps a known action tool to its CLI path",
      "rollback": "git checkout -- tools/alpha-atlas architecture/atlas && git clean -fd tools/alpha-atlas architecture/atlas",
      "files": ["tools/alpha-atlas/src/alpha_atlas/generators/cli_tree.py", "tools/alpha-atlas/src/alpha_atlas/generators/mcp_tools.py", "architecture/atlas/generated/cache/cli-commands.json"],
      "status": "pending"
    },
    {
      "title": "S7 API routes + frontend scan: the connected layer",
      "verify": "cd tools/alpha-atlas && uv run pytest -q",
      "expected": "method-count floor >=100; every extracted client path joins an openapi path; one known screen->panel->method->route->cli->module chain asserted; connected level live",
      "rollback": "git checkout -- tools/alpha-atlas architecture/atlas && git clean -fd tools/alpha-atlas architecture/atlas",
      "files": ["tools/alpha-atlas/src/alpha_atlas/generators/api_routes.py", "tools/alpha-atlas/src/alpha_atlas/generators/frontend_scan.py"],
      "status": "pending"
    },
    {
      "title": "S8 mermaid emitter + docs/atlas + root consistency test + root ruff extend-exclude for the Atlas frontend",
      "verify": "cd tools/alpha-atlas && uv run python -m alpha_atlas.generate --check; root: uv run python scripts/gate.py fast",
      "expected": "5 docs/atlas files with overview-first progressive disclosure, details sections, <=40-node diagrams, ASCII fallbacks; root consistency test green; root gate fast passes",
      "rollback": "git checkout -- tools/alpha-atlas docs/atlas tests/unit/test_atlas_consistency.py pyproject.toml && git clean -fd docs/atlas",
      "files": ["tools/alpha-atlas/src/alpha_atlas/core/mermaid.py", "docs/atlas/system-map.md", "docs/atlas/research-flow.md", "docs/atlas/data-lineage.md", "docs/atlas/frontend-flow.md", "docs/atlas/cli-flow.md", "tests/unit/test_atlas_consistency.py", "pyproject.toml"],
      "status": "pending"
    },
    {
      "title": "S9 SystemMap + CodeExplorer views",
      "verify": "cd tools/alpha-atlas/frontend && npm test; manual navigation",
      "expected": "collapse/expand model tests green; drift and Unknowns badges render",
      "rollback": "git checkout -- tools/alpha-atlas/frontend",
      "files": ["tools/alpha-atlas/frontend/src/views/SystemMap.tsx", "tools/alpha-atlas/frontend/src/views/CodeExplorer.tsx"],
      "status": "pending"
    },
    {
      "title": "S10 DataLineage + ChangeImpact views",
      "verify": "cd tools/alpha-atlas/frontend && npm test; manual navigation",
      "expected": "research-entity chain rendered; impact BFS fixture test green with a known blast radius",
      "rollback": "git checkout -- tools/alpha-atlas/frontend",
      "files": ["tools/alpha-atlas/frontend/src/views/DataLineage.tsx", "tools/alpha-atlas/frontend/src/views/ChangeImpact.tsx", "tools/alpha-atlas/frontend/src/model/impact.ts"],
      "status": "pending"
    },
    {
      "title": "S11 polish: stale banner, README, final acceptance walkthrough",
      "verify": "full Atlas gate + root gate + manual acceptance walkthrough of the what-happens-when-I-create-a-trading-idea path",
      "expected": "all acceptance criteria met; zero protected edits; MCP pin and CLI surface untouched",
      "rollback": "git checkout -- tools/alpha-atlas",
      "files": ["tools/alpha-atlas/README.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/atlas/system-map.md", "docs/atlas/research-flow.md", "docs/atlas/data-lineage.md", "docs/atlas/frontend-flow.md", "docs/atlas/cli-flow.md", "tools/alpha-atlas/README.md"],
  "out_of_scope": [
    "Phase 7 runtime/OpenTelemetry observation (schema fields reserved: runtime_observation kind, trace_id/span_id/execution_id/timestamp provenance; never emitted in v1)",
    "GitNexus integration (evaluated below; it appears nowhere in the repo; optional future read-only provider only, never a source of truth)",
    "New MCP tools (surface pinned at 62), CLI sub-apps, .claude commands/agents/rules, or any protected-file edit",
    "New ADRs (this plan doc carries the decisions; an ADR would force a protected CLAUDE.md citation)",
    "alpha-web integration or any Alpha runtime/authority/governance change",
    "Instance-level browsing of workstation.sqlite3 (live state, not repository truth)",
    "Committing frontend build output (dist/ is gitignored)",
    "Rewriting docs/ARCHITECTURE.md (drift is surfaced by Atlas, never fixed by it)"
  ],
  "files": ["tools/alpha-atlas/", "architecture/atlas/", "docs/atlas/", "tests/unit/test_atlas_consistency.py"]
}
```

## 1. Mission and framing

Atlas is a **local engineering knowledge graph + explanation layer** — not an
architecture-diagram tool and not another application framework. It exists so a
non-expert developer (and any AI agent) can answer, before changing anything:

- What exists, and at what evidence level?
- How do components actually connect (web → API → CLI → package)?
- What happens when a new trading idea is created (the full research lifecycle)?
- What is safe to change, what must not change, and which tests/specs govern it?

Atlas is **read-only over repository truth**. It never reads live state
(`workstation.sqlite3` rows), never imports `alpha_*` packages, never executes
the engine, and its server never subprocesses anything (generation is a
separate, explicit CLI step).

## 2. Boundaries (non-negotiable)

- No changes to trading logic, research authority, CLI/MCP authority (MCP stays
  pinned at its current tool count), governance, or protected files.
- Not under `packages/` or `apps/` (would trip the MODULE MAP drift test and
  require a new import-linter contract). Isolated uv project under
  `tools/alpha-atlas/`, following the `workers/` precedent: own `pyproject.toml`,
  own `uv.lock`, own gate ritual, deliberately not a root workspace member.
- No new ADR in v1: this document is the decision record.
- Zero protected-file edits. The only root-file edit in the whole program is an
  unguarded `[tool.ruff] extend-exclude` entry for the Atlas frontend (S8),
  mirroring the existing alpha-web frontend exclusion.

## 3. Architecture

```
architecture/atlas/
  schema/atlas-schema.json        JSON Schema for graph + definitions
  definitions/*.json              curated, committed, metadata-mandatory
  generated/graph.json            merged graph, committed
  generated/views/*.json          pre-sliced per-view subgraphs, committed
  generated/cache/cli-commands.json  committed subprocess cache
tools/alpha-atlas/
  src/alpha_atlas/core/           stdlib-only: model, merge, validate, evidence,
                                  mermaid, prompt_pack
  src/alpha_atlas/generators/     stdlib-only extractors
  src/alpha_atlas/generate.py     pipeline entry (--check | --offline | --refresh-cli)
  src/alpha_atlas/backend/        FastAPI read-only server, loopback :8803
  frontend/                       Vite + React (alpha-web's exact stack) +
                                  @xyflow/react + @dagrejs/dagre; dist/ gitignored
docs/atlas/*.md                   5 generated mermaid docs, progressive disclosure
```

`core/` and `generators/` are **stdlib-only** so the root consistency test can
import them via `sys.path` insertion without the Atlas venv. Third-party deps
(fastapi, uvicorn) are confined to `backend/`.

### 3.1 Extend-by-consuming (no duplicate indexing)

Atlas consumes the existing awareness seams and layers on top:

| Existing seam | Atlas use |
|---|---|
| `gate.py index` → `.claude/state/repo-index.json` | public symbols per module (AST fallback under `--offline` / stale tree_hash; regenerated via `uv run python scripts/gate.py index` when needed) |
| `alpha info commands --json` | CLI tree (cached to a committed file; `--refresh-cli` re-runs) |
| committed `apps/alpha-web/frontend/openapi.json` + `docs/governance/openapi-operation-classification.json` | API route nodes + safe/mutate classification |
| root `pyproject.toml` `[tool.importlinter]` via stdlib `tomllib` | authoritative DAG contract nodes incl. source/forbidden lists no index captures today |
| uniform ADR headers, rule `paths:` globs, MODULE MAP tables, spec section anchors | doc nodes, doc→code edges, per-module one-liners, governance zones |
| `.claude/mutation-baseline.json` | per-module confidence badges |

New derived layers that exist nowhere today: Python import edges, test→target
map, frontend→API→CLI chain, doc→file reverse index, evidence-level resolution.

## 4. Schema

**Node** `{id, kind, label, path?, component?, evidence:{level, provenance[]}, meta{}}` —
20 kinds: code/doc kinds `component module cli_command mcp_tool api_route screen
panel workflow_node test doc rule artifact contract`, research-entity kinds
`research_case hypothesis dataset experiment decision strategy_version`, and the
reserved `runtime_observation`. Deterministic ids (`module:alpha_cli.research_d1`,
`cli:alpha research capture`, `route:GET /api/research/{case_id}`, `doc:ADR-0025`,
`wf:research.d1`, ...). Research-entity nodes are **type-level** in v1, derived
from curated definitions plus verified code anchors (e.g. `research_case` ←
`control_store.py:3117`, `dataset` ← `research_dataset_refs` at
`control_store.py:878`, `strategy_version` ← promotion packet at
`control_store.py:7452`), so DataLineage renders Research Case → Hypothesis →
Dataset → Experiment → Evidence → Decision → Strategy Version.

**Edge** `{id, type, source, target, evidence}` — 8 types: `depends_on
implements validates defines calls serves produces part_of`.

**Evidence** — ordered enum `unknown < declared < implemented < connected <
tested < observed`, computed by the resolver, never hand-asserted:

- `unknown`: discovered code/artifact with no doc reference, no curated
  definition, no validating test, no cross-layer edge — surfaced in an explicit
  Unknowns review queue rather than silently labeled implemented.
- `declared`: only a doc/definition mentions it.
- `implemented`: a code extractor produced it AND at least one doc/rule/definition anchors it.
- `connected`: implemented + participates in a cross-layer calls/serves/implements chain.
- `tested`: ≥1 incoming `validates` edge (mutation kill rate joined as a badge, not a level input).
- `observed`: reserved for Phase 7 runtime traces; never emitted in v1. The
  schema reserves `runtime_observation` and provenance fields
  `{trace_id, span_id, execution_id, timestamp}` now so OTel later is additive.

Every node and edge carries provenance `[{extractor, source, line, detail}]`.
`generated/graph.json` is `{schema_version, inputs_hash, nodes[], edges[], stats}`,
sorted by id, `sort_keys=True`, **no timestamps** — two runs on one tree are
byte-identical. `inputs_hash` is a sha256 over `generated/inputs.json`, which
records the exact repository files (path → content sha256) the extractors read;
generated outputs are never inputs, so regeneration can never invalidate itself
(a whole-tree hash would: writing graph.json changes the tree it stamps).

### 4.1 Curated definitions (anti-drift contract)

Hand-written JSON in `architecture/atlas/definitions/` supplies purpose,
inputs/outputs, limitations, and safe-change notes. Every entry **must** carry
`owner ("human"|"agent")`, `created_from` (ADR ids / spec paths / code anchors),
`last_verified_commit`, and `confidence ("high"|"medium"|"low")` — where
confidence rates **documentation/provenance quality, not architectural
correctness**. The generator records a content sha256 per code anchor; a changed
anchor later downgrades the entry to a visible "needs re-verification" state.
Dangling node references or stale file:line anchors fail generation loudly.
Curated text can flag expectations but can never raise a computed evidence level.

## 5. Generator pipeline

`ensure_inputs → extractors (fixed order) → merge (dedupe by id, union
provenance) → validate (fail loud, name the offending id) → evidence resolver →
graph.json + views/*.json → mermaid emitter → docs/atlas/*.md`. `--check`
regenerates in memory and byte-compares against committed output.

Ten extractors (inputs → technique): components (dirs + MODULE MAP regex),
python_modules (AST imports; repo-index symbols when fresh), importlinter
(tomllib), cli_tree (cached `alpha info commands --json` + AST over `*_cmds.py`),
mcp_tools (AST over `server.py`, argv literals → CLI paths), api_routes
(openapi.json + classification + router AST for `_run_json`/launch seams),
frontend_scan (guarded regex over `client.ts` + `api.*(` usage + `SCREENS`
literal), docs_scan (uniform ADR headers + Implementation anchors + ADR-ref
regex), tests_map (AST `from alpha_x.y import` + category + mutation join),
workflow (curated lifecycle/entity definitions with anchor verification).

Frontend scanning stays regex-based with hard guards: every extracted `/api/...`
path must join an `openapi.json` path (orphans fail generation), a ≥100
method-count floor holds, and unmatched `api.*` usages fail loud. A ts-morph
node-script escalation is documented but not built.

## 6. Backend (read-only)

FastAPI on `127.0.0.1:8803` (`ALPHA_ATLAS_PORT`). `GET /api/meta` (graph vs live
tree_hash → stale flag), `GET /api/graph`, `GET /api/views/{view}`,
`GET /api/node/{id}`, `GET /api/excerpt` (repo-root-jailed resolve +
`is_relative_to`, symlink escapes rejected, denylist `.env*` / `*.sqlite3*` /
`.claude/state/`, ≤400 lines, text only), `POST /api/prompt-pack`. Serves
`frontend/dist` when built, else 503 with the exact rebuild command. No write
endpoints; no subprocess calls.

### 6.1 Generate AI Context (core feature, Milestone A)

`core/prompt_pack.py` is a pure function producing markdown with 12 fixed
sections: TARGET AREA, CURRENT STATE, ARCHITECTURAL INTENT, EXISTING
IMPLEMENTATION, DEPENDENCIES, DO NOT CHANGE (import-linter contracts, matching
`.claude/rules` via `paths:` globs, protected/risk/quant path tiers, pinned
surfaces), FILES LIKELY TO MODIFY, FILES NOT TO MODIFY, TEST REQUIREMENTS,
VALIDATION COMMANDS (the exact gate ritual for the touched tier), OPEN
QUESTIONS / KNOWN LIMITATIONS (curated + evidence gaps incl. in-scope `unknown`
nodes), RELEVANT DOCUMENTATION. Every major node exposes a
"Generate AI Context / Copy context for Codex" action from Milestone A onward —
this is the bridge from human understanding to a safe AI prompt and the primary
reason Atlas exists.

## 7. Frontend

Match alpha-web's exact stack (React ^19.2.7, Vite ^8, TS ~6, vitest node-env
pure-model tests, oxlint) + `@xyflow/react` + `@dagrejs/dagre` (synchronous,
tiny, right for layered LR DAGs; layout behind `model/layout.ts` for a later
elkjs swap). Dark `:root` tokens copied from alpha-web; hash-based view
switching; no router library. Views: ResearchLifecycle (first), SystemMap
(one-component-at-a-time expansion, ≤~150 visible nodes), CodeExplorer,
DataLineage (entity chain), ChangeImpact (reverse-edge BFS blast radius +
affected tests). Shared NodePanel drawer: purpose, evidence + provenance with
excerpt links, used-by/produces, constraints, docs, Generate AI Context.

## 8. Generated documentation (`docs/atlas/`)

Five files (`system-map`, `research-flow`, `data-lineage`, `frontend-flow`,
`cli-flow`), each headed `<!-- GENERATED by alpha-atlas — do not edit -->`, each
mermaid block paired with an ASCII fallback in `<details>` (the
`docs/ARCHITECTURE.md` convention). **Progressive disclosure is a hard emitter
rule**: overview prose + one small summary diagram first (hard cap ~40 nodes per
mermaid block — the emitter fails rather than emitting an unreadable graph);
detail in collapsible sections and links to deeper views; large enumerations as
collapsed tables. `system-map.md` also carries the drift section (e.g. the stale
`docs/ARCHITECTURE.md` §6 ADR table — surfaced, never fixed) and the Unknowns
review queue. Freshness: Atlas gate `generate --check` byte-equality + one
stdlib-only root test (`tests/unit/test_atlas_consistency.py`) asserting
internal consistency (schema-valid, no dangling references, mermaid matches
graph) — the root gate never forces a regen; the UI shows a stale banner when
the recorded input-file hashes in `generated/inputs.json` no longer match the
working tree.

## 9. Milestones

**Milestone A — Research Lifecycle Explorer (S0–S4), protected above
everything:** the lifecycle chain (Idea → Research Case → Hypothesis → Dataset →
Experiment → Evidence → Decision → Strategy Version) visually explorable with
clickable nodes, explanations, provenance, linked files, ADR/spec references,
tests, and Generate AI Context. Must be demonstrably usable before any
Milestone-B slice begins.

**Milestone B — general graph expansion (S5–S11):** remaining extractors, full
evidence resolver incl. `unknown`, mermaid docs, SystemMap / CodeExplorer /
DataLineage / ChangeImpact, polish.

Slice details, verification commands, and rollbacks are in the FeaturePlan front
block above. Small conventional commits per slice (`feat(atlas): ...`); root
`gate.py full` stamp per commit (docs-only commits waived).

## 9a. Implementation refinements (recorded as they land)

- **inputs_hash over tree_hash** (S1): the staleness key hashes the exact input
  files read, so regeneration can never invalidate itself.
- **Primary-anchor validates rule** (S2): tests join a workflow/entity node only
  through its first (primary) anchor. Secondary anchors like `control_store.py`
  span six lifecycle nodes; joining through them would let any store test
  "validate" all of them — the overclaiming Atlas exists to prevent.
- **Compact graph.json** (S2): the merged graph is emitted as single-line
  canonical JSON (13k+ indented lines would trip the per-commit line guard on
  every regen and diff as pure noise). Humans review views and docs/atlas;
  `inputs.json` stays indented.

## 9b. Out-of-plan edits (justified)

- `tests/integration/test_crypto_coverage_completion.py` (commit 6437909): the
  S1 full-gate run exposed that `test_read_only_projections_answer_honestly_
  when_no_volume_is_configured` monkeypatched the env var but not the cwd
  `.env`, so an owner machine with a configured Expansion volume broke the
  test's premise. Fixed by running from a tmp cwd. Unrelated to Atlas code;
  required for any commit on this machine to obtain a full-gate stamp.

## 10. GitNexus evaluation (Phase 8 — evaluation only)

GitNexus appears nowhere in this repository (verified: zero grep matches). It is
an external code-graph tool that would overlap Atlas's python_modules /
tests_map extractors while knowing nothing about ALPHA's governance layers
(evidence levels, curated definitions, protected tiers). Verdict: **do not
integrate in v1.** If revisited later it must be (a) an optional local developer
tool, (b) read-only, (c) an additional context source feeding Atlas provenance —
never the source of truth, and never touching CLAUDE.md, AGENTS.md, hooks, or
MCP configs. Any future setup command must be reviewed before execution.

## 11. Phase 7 (runtime layer) — deferred by design

No runtime instrumentation in v1. The schema reserves the `runtime_observation`
kind and `{trace_id, span_id, execution_id, timestamp}` provenance so a later
OpenTelemetry investigation (user action → frontend → API → CLI → worker →
artifact) is additive. Runtime truth will be kept separate from static analysis
when it arrives.

## 12. Acceptance criteria

1. Milestone A usable end-to-end before Milestone B starts.
2. `uv run python -m alpha_atlas.generate` is byte-deterministic; `--check` passes.
3. Clicking any lifecycle node reveals purpose, computed evidence with file:line
   provenance, responsible files, docs, tests, dependencies, limitations.
4. Evidence levels demonstrably computed (≥1 declared-only, ≥1 tested, ≥1
   `unknown` in the review queue when one exists in the tree).
5. Generate AI Context yields all 12 sections for any selection.
6. All five views navigable; docs/atlas renders legibly on GitHub.
7. Root gate passes with zero protected edits; Atlas gate (ruff, mypy --strict,
   pytest, `generate --check`) passes; MCP pin, CLI surface, governance untouched.
