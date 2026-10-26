# Qualification preflight

**Delivery state:** Implementation complete; the first owner-authorized full-gate attempt exposed
a synthetic-fixture omission, corrected by deriving the fixture from the canonical script list.
The corrected candidate's qualification is governed by its exact-tree checks and canonical receipt.

## Goal

Add a small read-only command that finds known checkout and environment blockers before the
canonical full gate. Reuse the existing manual-size test, harness lint, gate definitions, and Atlas
freshness check rather than duplicating their rules. The diagnostic must not install dependencies,
alter candidate files, inspect private or holdout contents, skip tests, or weaken gate coverage.

## Feature plan

```json
{
  "schema_version": 1,
  "title": "Qualification preflight",
  "context": "At baseline e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc, the canonical gate already defines full-scope mypy and Atlas freshness checks and includes an existing manual-size test before backend checks, but no read-only qualification command covers sparse public prerequisites, Git alternates, or the candidate-local environment. The existing doctor writes a probe and checks harness wiring, so it is not reusable for this diagnostic.",
  "assumptions": [
    {
      "statement": "Qualification must be read-only and must not install, repair, or weaken the canonical gate.",
      "verified_by": "Delegated owner task and scripts/gate.py/scripts/gate_components.py inspection"
    },
    {
      "statement": "Only public tracked prerequisites and the existing Atlas --check operation are eligible inputs; holdout and private contents remain out of scope.",
      "verified_by": "Delegated owner task and tools/alpha-atlas/src/alpha_atlas/generators/tests_map.py boundary"
    }
  ],
  "alternatives_considered": [
    "Reuse gate.py doctor, rejected because it writes a probe file and checks unrelated harness state.",
    "Run a full component or full gate, rejected because it installs dependencies or executes broad checks and is not authorized in this task."
  ],
  "pre_mortem": [
    "A path check might enumerate or read beyond the named public prerequisites; scope Git path listing to explicit public roots and inspect existence metadata only.",
    "Running the Atlas check through uv could create an environment; invoke only an already available compatible Python interpreter with bytecode writes disabled, otherwise report freshness as unverified."
  ],
  "slices": [
    {
      "title": "Add read-only qualification diagnostics and gate command",
      "verify": "Run focused synthetic tests for missing tracked prerequisites, temporary alternates, local venv readiness, full-gate mypy coverage of tests, and Atlas freshness; share the manual-size predicate with its existing unit test.",
      "expected": "gate.py preflight reports candidate identity and resources, gives blockers a nonzero status, supports JSON, and leaves the candidate unchanged.",
      "rollback": "Revert the preflight module, CLI wiring, and focused tests as one slice.",
      "files": [
        "scripts/gate.py",
        "scripts/gate_preflight.py",
        "tests/unit/test_claude_md_relocation.py",
        "tests/unit/test_gate_preflight.py"
      ],
      "status": "done"
    },
    {
      "title": "Document the diagnostic and record delivery",
      "verify": "Run the focused test module and validate the feature plan format.",
      "expected": "The development-loop guide exposes the read-only preflight command and the build record states exactly what was verified.",
      "rollback": "Revert only the guide, plan, and appended build-status entry.",
      "files": [
        "docs/operations/development-loop.md",
        "docs/BUILD-STATUS.md",
        "docs/superpowers/plans/2026-10-25-qualification-preflight.md"
      ],
      "status": "done"
    }
  ],
  "tier_impact": ["none"],
  "docs_to_update": [
    "docs/operations/development-loop.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "Running the canonical full gate",
    "Changing dependencies or lockfiles; the later owner-authorized follow-up may only create the root candidate-local environment with `uv sync --locked`",
    "Reading private data, tests/holdout, credentials, secrets, or Codex sessions",
    "Editing CLAUDE.md or AGENTS.md while their wording is owned by another report",
    "Weakening existing gate test or type-check coverage, or regenerating anything except Atlas outputs through its canonical generator during the later owner-authorized follow-up"
  ],
  "files": [
    "scripts/gate.py",
    "scripts/gate_preflight.py",
    "tests/unit/test_claude_md_relocation.py",
    "tests/unit/test_gate_preflight.py",
    "docs/operations/development-loop.md",
    "docs/BUILD-STATUS.md",
    "docs/superpowers/plans/2026-10-25-qualification-preflight.md"
  ]
}
```

## Verification record

Focused verification: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -B -m unittest
tests.unit.test_gate_preflight -v` passed all eight synthetic tests. `gate.py plan-check` accepted
this two-slice plan. `gate.py preflight --json` returned 1 on the candidate because its local
`.venv` is missing and Atlas outputs are stale; other reported checks passed. Independent review
found no remaining code findings after the missing root lock/config checks and executable-venv
check were added. Pytest integration and the canonical full gate remain unverified because the
candidate-local `.venv` is absent and pytest is unavailable; no environment was installed or
synchronized.

## Owner-authorized follow-up

The later owner instruction authorizes only the repository's existing root `uv.lock` workflow
(`uv sync --locked`) in this candidate, canonical Atlas generation, focused tests under the
repository runner, canonical mypy including public tests, and cheap checks. It still prohibits a
full gate, dependency or lock changes, or publication. The preflight distinguishes command-scope
inspection (`scope_only`) from executed commands (`executed`) and explicitly reports canonical
mypy as `not_run`; actual typing results belong in the follow-up record, not the preflight result.

Follow-up verification passed: 15 focused pytest cases, canonical `uv run mypy packages apps tests`
(857 source files), canonical harness mypy (18 files), Ruff check/format on changed Python files,
import contracts, harness lint, and this plan check. After final documentation edits, the canonical
Atlas generator was rerun with the root candidate `.venv`; its freshness check passed for all 8
outputs. The root `.venv` is ignored; `pyproject.toml` and `uv.lock` are unchanged. The generator's
only changed tracked outputs are `architecture/atlas/generated/graph.json`,
`architecture/atlas/generated/inputs.json`, and `architecture/atlas/generated/views/unknowns.json`.
The existing Semgrep 1.181.0 contract probe passed on retry; its earlier exit 130 remains preserved
at `/workspace/alpha-preflight-semgrep-exit-130.json`. At completion of this follow-up, no full gate
or publication had been performed.

## Owner-authorized canonical gate attempt and correction

The owner subsequently authorized one canonical full gate on the reviewed candidate tree. Its
backend receipt reported 11 of 12 steps passing and a stable tree. The full pytest/coverage step
reported 5,987 passed, 10 skipped, one failed, with 93.12% coverage against the unchanged 93.0%
floor. The single failure was
`tests/unit/test_claude_harness_gate.py::TestDoctor::test_doctor_passes_on_wired_repo`: its
synthetic fixture used a hardcoded script list and omitted newly registered
`scripts/gate_preflight.py`. The original log and failed backend receipt are retained at
`/workspace/alpha-preflight-full-gate.log` and
`/workspace/alpha-preflight-backend-failed-receipt.json`; the receipt records the original
candidate fingerprint `73c350a90902b139fba989885208dc53012e51ab6d7dccf8dd47ab5a302c138d` and
`stable_tree: true`. No full-gate stamp was written. The minimal correction makes the synthetic
fixture build stubs from `gate.HARNESS_SCRIPTS`, then independently reviewed. Qualification of the
corrected tree is determined by its exact-tree checks and canonical receipt.
