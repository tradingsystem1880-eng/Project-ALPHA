---
owner: documentation set
sources:
  - docs/README.md
  - docs/adr/README.md
  - scripts/roadmap_index.py
  - scripts/harness_awareness.py
  - scripts/harness_models.py
  - tests/unit/test_plan_schema.py
  - tests/unit/test_docs_links.py
  - tests/unit/test_repo_awareness_drift.py
  - tests/unit/test_roadmap_index.py
verified: ed121b80e439
---

# Documentation invariants

What must hold when adding or changing documents under `docs/`: decision records, feature plans and their
delivery states, the generated roadmap index, append-only records, and relative links.

## Document lifecycle

- Living documents (`ARCHITECTURE.md`, `context/`, `governance/` hand-written files, `operations/`) are
  updated in place when behaviour changes (`docs/README.md`).
- Research reports (`research/`) and dated specs and plans are rationale and intent: neither a
  recommendation nor a `Completed` plan proves current behaviour. Read the accepted ADR, the code and a
  fresh check result. A `verified` commit or resolving links show a document was checked, not that it is right.
- Private research material (such as the owner's October 2026 research archive, kept outside the repository)
  enters only as an owner-authorised, sanitised derivative with its own provenance, after checks for
  credentials, identifiers, private conversations, owner data, licences and redistribution rights. A right
  to keep material privately is not a right to publish it, and private verification grants no authority.
- One home per fact: when behaviour changes, update the one document that owns the fact (see the table in
  the root `CONTEXT.md`) and link to it from elsewhere; never copy a fact into a second file. There is no
  manual to update and no delivery log to append to — history is git log and pull requests.
- Records stay true as of their date: `records/` and `operations/retrospectives/` are appended to or left
  as-is, with path-only link fix-ups allowed. `docs/BUILD-STATUS.md` and `build-status/` are frozen history:
  never add to or rewrite them.
- `archive/` is not edited.
- Retrospectives are `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` with a `## Watch-outs` section.

## Decision records

- ADRs are `docs/adr/NNNN-<slug>.md`, zero-padded and sequential; a number is never reused. Add the new
  record to the index table in `docs/adr/README.md`.
- Decision text is not rewritten. A superseded ADR keeps its number; add a dated status note and a forward
  link to its replacement.
- Status is one of `Proposed`, `Accepted`, `Superseded`. Keep the Status/Date/Deciders header and the
  `Context`, `Decision` and `Consequences` sections, and cite precise `file:symbol` or test anchors.
- Every ADR file is linked from the index table in `docs/adr/README.md`, its one listing. Enforced by
  `tests/unit/test_repo_awareness_drift.py` through `scripts/harness_awareness.py::adr_drift`.

## Feature plans

- A live plan is `docs/work/YYYY-MM-DD-<slug>/02-plan.md` (the task folder of the
  [delivery pipeline](../../../workflow/CONTEXT.md)) with a `FeaturePlan` object in the first
  fenced `json` code block. It must validate against `scripts/harness_models.py::FeaturePlan`
  (`schema_version` 1, at least one alternative, at least two pre-mortem items, at least two slices each
  with `verify`, `expected`, `rollback`, and a closed `tier_impact` list). Check with
  `uv run python scripts/gate.py plan-check docs/work/<task>/02-plan.md`; enforced for every live plan by
  `tests/unit/test_plan_schema.py`.
- Every plan, live or archived, has exactly one `**Delivery state:** <state>` line within its first 12 lines.
  States: `Completed`, `Implemented – qualification pending` (en dash), `In progress`, `Blocked`, `Planned`,
  `Superseded by <relative path>`. Text may follow after ` — `, `(`, `.`, `;`, `,` or a date.
- Use `Completed` only for merged work (older plans may cite an acceptance recorded in `BUILD-STATUS.md`).
- By convention the state line sits under the title, or on line 1 when a JSON block leads the file, and
  reads `**Delivery state:** <state> — <evidence>` (the test checks only the first 12 lines).
- A `Completed` or `Superseded` task folder moves with `git mv` to `docs/work/archive/YYYY-MM/`, the
  month of its name; fix links to it. Plans finished before 2026-11-14 are single files there. Archived
  plans keep their text and JSON blocks as written; no finished plan stays in `docs/work/`.

## Roadmap index

- `docs/roadmap/README.md` is generated: never edit it by hand. Run `uv run python scripts/roadmap_index.py`
  after adding, moving or changing any plan, backlog item or refactor; `--check` reports a stale index, and
  `tests/unit/test_roadmap_index.py` fails on one.
- A wanted feature with no plan is `docs/roadmap/backlog/<slug>.md` with `**Status:**` `Idea` or `Scoped` and
  `**Rough size:**` `S`, `M`, `L` or `XL` within its first 8 lines. Remove it when a plan replaces it.
- A staged refactor is `docs/roadmap/refactors/<slug>.md` with `**Risk:**` `L`, `M` or `H` within its first
  8 lines. Copy an existing file's template.
- Archive month folders must be named `YYYY-MM` and hold only finished plans, and no live task folder may
  hold a finished plan, or the generator raises.

## Generated files

- Regenerate, never hand-edit. The generated files (`STATUS.md`, `docs/reference/commands.md`,
  `docs/roadmap/README.md`, the capability matrix and the OpenAPI classification) and their commands are
  listed once, in [docs/README.md § Generated files](../../README.md#generated-files).
- The work-in-progress limit is stated in the generated `docs/roadmap/README.md` (from
  `docs/roadmap/wip-limit.json`); status comes from `docs/roadmap/capabilities.toml` via `STATUS.md`.

## Links

- Relative Markdown links must resolve, including `#fragment` anchors on Markdown targets (GitHub heading
  slugs or explicit `<a id>`). Scope: tracked `docs/**/*.md`, root `*.md`, `.claude/**/*.md`,
  `.agents/**/*.md`, and READMEs under `apps/`, `packages/`, `tools/`, `workers/`. Fenced code, inline
  code, external URLs and `mailto:` are skipped. Enforced by `tests/unit/test_docs_links.py`.
- Its `ALLOWLIST` is only for links in dated records (including archived plans) whose target was removed or
  moved; each entry needs a reason and the test fails if an entry is no longer needed. Links from
  `docs/archive/` into the retired `docs/superpowers/` folder are tolerated, because archives are not edited.
- Find documents with `uv run python scripts/fs.py search "QUERY"`; it ranks living documents ahead of records.
