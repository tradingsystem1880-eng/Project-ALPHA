# Project layer: what each part is for

**Delivery state:** Completed — built and checked on branch `m3/project-layer`; documentation only.
**Build class:** standard — documentation and a contract test, written by Claude; no product code.

Filed straight into the archive: a live plan must be listed in `docs/roadmap/capabilities.toml`,
which another stream owns during this change, and the work was finished in one sitting.

## For the owner

- New folder `docs/reference/project/`: an overview of what ALPHA is for and how the research loop
  runs, one file per major part (14 parts), and a log of your direction-setting decisions.
- Each part's file says why it exists, its job, the intended design, where it lives, open
  questions for you ("Owner to confirm"), and what must never be done to it.
- Any proposal to shelve or remove a part must first cite that file and the log.
- Nothing changes in the app. You will be asked about ten open questions.

```json
{
  "schema_version": 1,
  "title": "Project layer: what each part is for",
  "context": "Agents could learn how to change code and how to deliver, but not why each part exists; one recommended shelving RD-Agent.",
  "assumptions": [
    {"statement": "Reference files under docs/reference/ may live in subfolders and are covered by the size, front-matter and link tests.", "verified_by": "tests/unit/test_filesystem_contract.py and tests/unit/test_docs_links.py pass with docs/reference/project/ present"},
    {"statement": "The capability map can be read but not edited.", "verified_by": "the brief; the mapping lives in the component files"}
  ],
  "alternatives_considered": [
    "Make docs/roadmap/rd-agent-in-alpha.md the RD-Agent component file: rejected, it is a dated status explainer for the owner; the component links to it.",
    "Add a component field to capabilities.toml: rejected, another stream owns that file; claims live in the component files."
  ],
  "pre_mortem": [
    "A new capability added to capabilities.toml fails the contract test until a component claims it; the failure message says where to add it.",
    "Component files restate status and go stale: they link STATUS.md and capability ids instead."
  ],
  "slices": [
    {"title": "Overview, owner decisions log and 14 component files", "verify": "uv run pytest -q tests/unit/test_filesystem_contract.py tests/unit/test_docs_links.py", "expected": "all pass", "rollback": "delete docs/reference/project/", "status": "done"},
    {"title": "Routing rows and contract tests", "verify": "uv run python scripts/gate.py check --all", "expected": "All checks passed", "rollback": "revert the routing rows and the new tests", "status": "done"},
    {"title": "Cold-reader trial before and after", "verify": "04-verify.md records both trials", "expected": "the shelving question is answered from the project layer", "rollback": "none needed", "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/reference/project/overview.md"],
  "out_of_scope": ["product code", "docs/roadmap/capabilities.toml", "docs/roadmap/triage-2026-11.md", "owner decisions themselves"],
  "files": ["docs/reference/project/", "CLAUDE.md", "CONTEXT.md", "*/CONTEXT.md", "workflow/stages/01-shape/CONTEXT.md", "workflow/stages/02-plan/CONTEXT.md", "tests/unit/test_filesystem_contract.py", "docs/README.md"]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [delivery pipeline](../../../../../workflow/CONTEXT.md) | The task folder | always |
| [documentation invariants](../../../../reference/invariants/documentation.md) | — | always |
| [file-system contract test](../../../../../tests/unit/test_filesystem_contract.py) | — | always |

## Slices

As in the JSON block: the files, then routing and enforcement, then the trial.

## Test plan

The contract test gains five checks: fixed sections and claim lines in each component file; every
capability claimed exactly once; every workspace claimed once and linking up to its component;
routing from the root, stage 01 and `CLAUDE.md`; dated, quoted owner-decision entries.

## Look-ahead, determinism and import impact

None: documentation and a test of documentation. No source under the quant tier changes.
