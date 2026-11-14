# One copy of each duplicated helper

**Delivery state:** Completed — built and checked on branch `m6/shared-helpers`; done when its pull request merges.
**Build class:** hard — 31 files in scope (handoff.py's own count); the harness edits are Claude's.

Filed straight into the archive, as `2026-11-14-code-size-limits` was: the work-in-progress
ceiling (34) admits no new live plan, and the work was finished in one sitting.

## For the owner

- Five groups of copied helper code now exist once each (file writing, command output, D1/D2
  artifact reading, a bootstrap Sharpe statistic, two study id checks). Product code shrinks by 142 lines (175 added, 317 removed).
- Every copy left in place is listed with the reason, usually that it sits in code your research
  approvals are bound to (changing it would make you re-approve) or across a boundary that must
  stay separate (the isolated workers, the web app and the MCP server).
- Three functions that only tests called are deleted; eleven others stay, each with a reason.
- One visible change: an idea you capture in the Workstation is recorded as created by
  `workstation`, not `codex`. One error message changes on a corrupt-file path (below).
- No research or rule approval is invalidated.

```json
{
  "schema_version": 1,
  "title": "One copy of each duplicated helper",
  "context": "Copied helpers drift apart and make agents read the same code twice; earlier audits named JSON, hash and validator helpers without numbers.",
  "assumptions": [
    {"statement": "Structurally identical function bodies (AST, names and docstrings aside) across files are the duplicates worth measuring; same-name functions with different bodies were compared by hand.", "verified_by": "scratch measurement over 514 product files: 32 identical groups, 235 duplicated lines"},
    {"statement": "research_d1, research_d2, research_cmds, alpha_study and the touched CLI modules are outside every approval binding.", "verified_by": "research_cmds._research_code_paths and _native_rule_environment.DAILY_GUARD_FILES"},
    {"statement": "alpha_web may import alpha_core.", "verified_by": "uv run lint-imports (13 contracts kept)"}
  ],
  "alternatives_considered": [
    "One shared canonical-JSON helper for the ~12 one-line wrappers and 73 inline calls: rejected; four different encodings exist (ensure_ascii, trailing newline, -0.0 folding, size caps), each defines a hash, and most sit in approval-bound files. One helper would couple unrelated hash formats.",
    "Moving helpers out of approval-bound files into shared modules: rejected; the bound file would then depend on code its approval does not cover, and the edit itself invalidates approvals.",
    "alpha_data's copy of the atomic writer: left for the data stream working in that package now."
  ],
  "pre_mortem": [
    "A moved helper reads a module-level name whose value differs between copies: each was checked (the D1/D2 size cap is 4 MiB in both; alpha_study helpers already used _contracts' _text and _hash).",
    "The Workstation label change confuses something that treats 'codex' specially: created_by is free text; only the separate responsibility field is checked."
  ],
  "slices": [
    {"title": "Consolidate five helper groups, delete two test-only functions, Workstation label (Codex build)", "verify": "uv run python scripts/gate.py check --all", "expected": "All checks passed", "rollback": "revert the refactor commit", "status": "done"},
    {"title": "Guard the digest rules; delete dead harness names (Claude)", "verify": "uv run pytest -q tests/unit/test_claude_harness_handoff.py tests/unit/test_claude_harness_gate.py", "expected": "all pass", "rollback": "revert the harness commit", "status": "done"},
    {"title": "Baseline, documents, smoke before and after", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0", "expected": "8 passed, 4 skipped", "rollback": "none needed", "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/reference/model-routing.md", "docs/reference/invariants/engineering.md", "docs/reference/invariants/cli-runs.md", "packages/alpha-core/CONTEXT.md"],
  "out_of_scope": ["approval-bound files", "packages/alpha-data", "packages/alpha-validation", "packages/alpha-research", "workers"],
  "files": ["packages/alpha-core/", "packages/alpha-study/", "apps/alpha-cli/", "apps/alpha-web/src/alpha_web/", "tools/alpha-eval/", "scripts/handoff.py", "scripts/harness_awareness.py", "tests/unit/", ".claude/code-size-baseline.json", "docs/reference/", "docs/work/archive/2026-11/2026-11-14-shared-helpers/"]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [engineering rules](../../../../reference/invariants/engineering.md) | Import layers | always |
| [engineering rules](../../../../reference/invariants/engineering.md) | Hash-bound source bytes | always |
| [ADR-0045](../../../../adr/0045-approvals-bind-code-structure.md) | Consequences | changing `scripts/handoff.py` |

## Slices

As in the JSON block. Codex built the consolidation from a brief that listed every bound file under
"Do not touch"; Claude made the harness edits (guarded paths a brief cannot declare).

## Test plan

Existing tests of every touched module, the moved-name tests, new tests for `alpha_core.atomic`,
the D1/D2 non-finite artifacts and the handoff guard; the whole platform tier and smoke ran here.

## Look-ahead, determinism and import impact

No data read, clock, fill or statistic changes. Run ids change (any `alpha_cli` or `alpha_core`
byte edit does). Import contracts hold; `alpha_core` gains a standard-library-only module.
