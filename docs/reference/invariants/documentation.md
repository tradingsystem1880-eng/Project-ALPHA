---
owner: documentation set
sources:
  - docs/README.md
  - docs/adr/README.md
  - scripts/roadmap_index.py
  - scripts/harness_awareness.py
  - scripts/harness_models.py
  - tests/unit/test_docs_links.py
  - tests/unit/test_repo_awareness_drift.py
  - tests/unit/test_roadmap_index.py
verified: 3a0098cd96e3
---

# Documentation invariants

What must hold when adding or changing documents under `docs/`: decision records, feature plans and their
delivery states, the generated roadmap index, append-only records, and relative links.

## Document lifecycle

- Living documents (`ARCHITECTURE.md`, `context/`, `governance/` hand-written files, `operations/`) are
  updated in place when behaviour changes (`docs/README.md`).
- The June 2026 research reports (`archive/2026-06-research-notes/`) and dated specs and plans are rationale
  and intent: neither a recommendation nor a `Completed` plan proves current behaviour. Read the accepted ADR, the code and a
  fresh check result. A `verified` commit or resolving links show a document was checked, not that it is right.
- Private research material (such as the owner's October 2026 research archive, kept outside the repository)
  enters only as an owner-authorised, sanitised derivative with its own provenance, after checks for
  credentials, identifiers, private conversations, owner data, licences and redistribution rights. A right
  to keep material privately is not a right to publish it, and private verification grants no authority.
- One home per fact: when behaviour changes, update the one document that owns the fact (see the table in
  the root `CONTEXT.md`) and link to it from elsewhere; never copy a fact into a second file. There is no
  manual to update and no delivery log to append to — history is git log and pull requests.
- Retrospectives stay true as of their date: left as-is, with path-only link fix-ups allowed. Older plans,
  records and archives were removed on 2026-11-14; read them at git tag `pre-thin-2026-11-14`. The
  owner's research notes stay in `docs/archive/research-notes/`, never edited (links inside are not checked).
- Retrospectives are `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` with a `## Watch-outs` section.

## Front matter

- Every `CONTEXT.md` and hand-written `docs/reference/` file starts with `owner` (a role, never a person),
  `sources` and `verified` (the commit it was last checked against); `tests/unit/test_filesystem_contract.py`
  enforces the shape and `uv run python scripts/fs.py stale` lists documents whose sources changed since.
- `sources` lists only files whose change can make the document wrong: the code, scripts, templates,
  schemas and configuration whose behaviour it states. It never lists data the document tells the reader to
  open or edit (`docs/roadmap/capabilities.toml`, backlog items, plans,
  generated pages): those change with routine work, and a document that names their fields is covered by
  the script that reads them (`scripts/capabilities.py`, `scripts/status.py`, `scripts/roadmap_index.py`).
- Never copy a value from a data file (a count, a cap, a list of names) into a document; name the field
  and link the file or the generated page that shows it.
- After re-reading a stale document against its changed sources, fix it and set `verified` to that commit,
  even when nothing needed fixing.

## Decision records

- ADRs are `docs/adr/NNNN-<slug>.md`, zero-padded and sequential; a number is never reused. Add the new
  record to the index table in `docs/adr/README.md`. If another branch merges first and takes the number, renumber
  yours before it merges (ADR-0045 was 0044 until then) and fix every reference.
- Decision text is not rewritten. A superseded ADR keeps its number; add a dated status note and a forward
  link to its replacement.
- Status is one of `Proposed`, `Accepted`, `Superseded`. Keep the Status/Date/Deciders header and the
  `Context`, `Decision` and `Consequences` sections, and cite precise `file:symbol` or test anchors.
- Every ADR file is linked from the index table in `docs/adr/README.md`, its one listing. Enforced by
  `tests/unit/test_repo_awareness_drift.py` through `scripts/harness_awareness.py::adr_drift`.

## Feature plans

- A plan is `docs/work/YYYY-MM-DD-<slug>/02-plan.md` (the task folder of the
  [delivery pipeline](../../../workflow/CONTEXT.md), on the task branch only) with a `FeaturePlan` object in the first
  fenced `json` code block. It must validate against `scripts/harness_models.py::FeaturePlan`
  (`schema_version` 1, at least one alternative, at least two pre-mortem items, at least two slices each
  with `verify`, `expected`, `rollback`, and a closed `tier_impact` list). Check with
  `uv run python scripts/gate.py plan-check docs/work/<task>/02-plan.md`; `scripts/handoff.py build --task`
  runs the same check.
- Every plan has exactly one `**Delivery state:** <state>` line within its first 12 lines.
  States: `Completed`, `Implemented – qualification pending` (en dash), `In progress`, `Blocked`, `Planned`,
  `Superseded by <relative path>`. Text may follow after ` — `, `(`, `.`, `;`, `,` or a date.
- A plan written from 2026-11-14 also states `**Build class:** small|standard|hard — <reason>` in its first
  12 lines and lists every file in scope in the front block's `files`
  ([model routing](../model-routing.md#task-classes)); `scripts/handoff.py` builds and checks from them.
- By convention the state line sits under the title, or on line 1 when a JSON block leads the file, and
  reads `**Delivery state:** <state> — <evidence>` (the test checks only the first 12 lines).
- The task folder is removed before its pull request merges; the pull request is the record.

## Roadmap index

- `docs/roadmap/README.md` is generated: never edit it by hand. Run `uv run python scripts/roadmap_index.py`
  after adding, moving or changing any backlog item or refactor; `--check` reports a stale index, and
  `tests/unit/test_roadmap_index.py` fails on one.
- A wanted feature with no plan is `docs/roadmap/backlog/<slug>.md` with `**Status:**` `Idea` or `Scoped` and
  `**Rough size:**` `S`, `M`, `L` or `XL` within its first 8 lines. Remove it when the work lands.
- A staged refactor is `docs/roadmap/refactors/<slug>.md` with `**Risk:**` `L`, `M` or `H` within its first
  8 lines. Copy an existing file's template.

## Generated files

- Regenerate, never hand-edit. The generated files (`STATUS.md`, `docs/reference/commands.md`,
  `docs/roadmap/README.md`, the capability matrix and the OpenAPI classification) and their commands are
  listed once, in [docs/README.md § Generated files](../../README.md#generated-files).
- Status comes from `docs/roadmap/capabilities.toml` via `STATUS.md`; work in progress is the open pull
  requests.

## Links

- Relative Markdown links must resolve, including `#fragment` anchors on Markdown targets (GitHub heading
  slugs or explicit `<a id>`). Scope: tracked `docs/**/*.md`, root `*.md`, `.claude/**/*.md`,
  `.agents/**/*.md`, and READMEs under `apps/`, `packages/`, `workers/`. Fenced code, inline
  code, external URLs and `mailto:` are skipped. Enforced by `tests/unit/test_docs_links.py`.
- Its `ALLOWLIST` is only for links in dated records whose target was removed or moved; each entry needs a
  reason and the test fails if an entry is no longer needed. A link to removed history points at git tag
  `pre-thin-2026-11-14` on GitHub.
- Find documents with `uv run python scripts/fs.py search "QUERY"`; heading matches rank first.
