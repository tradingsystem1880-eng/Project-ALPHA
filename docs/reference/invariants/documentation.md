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
verified: 1ac86fc02443
---

# Documentation invariants

What must hold when adding or changing documents under `docs/`: decision records, feature plans and their
delivery states, the generated roadmap index, append-only records, and relative links.

## Document lifecycle

- Living documents (`ARCHITECTURE.md`, `context/`, `governance/` hand-written files, `operations/`) are
  updated in place when behaviour changes (`docs/README.md`).
- Records stay true as of their date: `BUILD-STATUS.md`, `build-status/`, `records/` and
  `operations/retrospectives/` are appended to or left as-is, with path-only link fix-ups allowed. New
  delivery records go at the end of `docs/BUILD-STATUS.md`; never rewrite earlier entries.
- `archive/` is not edited.
- Retrospectives are `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` with a `## Watch-outs` section.

## Decision records

- ADRs are `docs/adr/NNNN-<slug>.md`, zero-padded and sequential; a number is never reused. Add the new
  record to the index table in `docs/adr/README.md`.
- Decision text is not rewritten. A superseded ADR keeps its number; add a dated status note and a forward
  link to its replacement.
- Status is one of `Proposed`, `Accepted`, `Superseded`. Keep the Status/Date/Deciders header and the
  `Context`, `Decision` and `Consequences` sections, and cite precise `file:symbol` or test anchors.
- Every ADR id must be mentioned in `CLAUDE.md` or a `.claude/rules/*.md` file (forms like `ADR-0013`,
  `ADRs 0013-0016`). Enforced by `tests/unit/test_repo_awareness_drift.py` through
  `scripts/harness_awareness.py::adr_drift`; mentions elsewhere do not count. `.claude/rules/docs.md`
  keeps the full id list for this check.

## Feature plans

- Live plans are `docs/superpowers/plans/YYYY-MM-DD-<slug>.md` with a `FeaturePlan` object in the first
  fenced `json` code block. It must validate against `scripts/harness_models.py::FeaturePlan`
  (`schema_version` 1, at least one alternative, at least two pre-mortem items, at least two slices each
  with `verify`, `expected`, `rollback`, and a closed `tier_impact` list). Check with
  `uv run python scripts/gate.py plan-check PLAN.md`; enforced for every live plan by
  `tests/unit/test_plan_schema.py`.
- Every plan, live or archived, has exactly one `**Delivery state:** <state>` line within its first 12 lines.
  States: `Completed`, `Implemented – qualification pending` (en dash), `In progress`, `Blocked`, `Planned`,
  `Superseded by <relative path>`. Text may follow after ` — `, `(`, `.`, `;`, `,` or a date.
- Use `Completed` only for merged or BUILD-STATUS-accepted work (`.claude/rules/docs.md`).
- A `Completed` or `Superseded` plan moves with `git mv` to `docs/superpowers/plans/archive/YYYY-MM/`, the
  month of its filename date; fix links to it. Only plans in `PINNED_FLAT` (`tests/unit/test_plan_schema.py`,
  mirrored in `docs/superpowers/plans/archive/README.md`) stay flat, because a file that cannot change names
  their path. Archived plans keep their text and JSON blocks as written.

## Roadmap index

- `docs/roadmap/README.md` is generated: never edit it by hand. Run `uv run python scripts/roadmap_index.py`
  after adding, moving or changing any plan, backlog item or refactor; `--check` reports a stale index, and
  `tests/unit/test_roadmap_index.py` fails on one.
- A wanted feature with no plan is `docs/roadmap/backlog/<slug>.md` with `**Status:**` `Idea` or `Scoped` and
  `**Rough size:**` `S`, `M`, `L` or `XL` within its first 8 lines. Remove it when a plan replaces it.
- A staged refactor is `docs/roadmap/refactors/<slug>.md` with `**Risk:**` `L`, `M` or `H` within its first
  8 lines. Copy an existing file's template.
- Archive month folders must be named `YYYY-MM` and hold only finished plans, or the generator raises.

## Generated files

- Regenerate, never hand-edit: `docs/governance/capability-authority-matrix.md` and
  `docs/governance/openapi-operation-classification.json` (`uv run python scripts/check_openapi_operations.py --write`),
  and `docs/roadmap/README.md` (above).

## Links

- Relative Markdown links must resolve, including `#fragment` anchors on Markdown targets (GitHub heading
  slugs or explicit `<a id>`). Scope: tracked `docs/**/*.md`, root `*.md`, `.claude/**/*.md`,
  `.agents/**/*.md`, and READMEs under `apps/`, `packages/`, `tools/`, `workers/`. Fenced code, inline
  code, external URLs and `mailto:` are skipped. Enforced by `tests/unit/test_docs_links.py`.
- Its `ALLOWLIST` is only for links in dated records whose target was removed; each entry needs a reason and
  the test fails if an entry is no longer needed.
- Find documents with `uv run python scripts/fs.py search "QUERY"`; it ranks living documents ahead of records.
