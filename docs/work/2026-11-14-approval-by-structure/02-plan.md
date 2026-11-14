# Approvals bind code structure, not bytes

**Delivery state:** Planned — built by Claude on `m6/approval-by-structure` (draft pull request); the work-in-progress ceiling (34 of 34) does not allow `In progress`
**Build class:** hard — guarded and hash-bound paths (`_native_rule_environment.py` is a daily approval guard file), quant/protected tier, owner-authority semantics

## For the owner

- What changes: a research approval you make from now on stays valid when someone only fixes
  comments, blank lines, formatting or docstrings in the approved code. Any change to what the code
  does still invalidates it.
- What does not change: every research approval you already made stays tied to the exact bytes it
  was made on, exactly as before, until you re-approve. Nothing is upgraded for you.
- One-off cost: pending fixed-rule and daily-rule approvals made before this change stop verifying
  (the rule lane's own guard file changes); re-draft and re-approve them when you next run one.
- Lock files, data files and code that reads its own source or line numbers stay byte-exact.
- Decision record: [ADR-0045](../../adr/0045-approvals-bind-code-structure.md). Nothing for you to
  decide; no approval, promotion or acceptance is made by this work.

```json
{
  "schema_version": 1,
  "title": "Approvals bind code structure, not bytes",
  "context": "Owner decision 2026-11-14: tie research approvals to code structure. Today hashes.code (research lane) and hashes.code/hashes.evaluator (rule lanes) are SHA-256 of exact source bytes, so a comment fix invalidates an approval. Add a standard-library structural digest (scheme 2) used by every approval-binding site, keep the byte digest (scheme 1) verifying old approvals, and fail closed on anything the digest cannot classify.",
  "assumptions": [
    {
      "statement": "Only two sites bind owner approvals to source: research_cmds._implementation_hashes and _native_rule_environment.rule_implementation_fingerprints; every other source hash is environment, upstream pin, launch identity or provenance.",
      "verified_by": "Repository grep for sha256 over source files, __file__, read_bytes, source_sha256, implementation_hash, worker_source and every reader of contract hashes (map in ADR-0045)."
    },
    {
      "statement": "No research-bound file needs to change, so research approvals made before this change keep verifying under scheme 1.",
      "verified_by": "research_cmds.py is not in the research code set; the diff touches none of the alpha_research tree or the four research CLI modules."
    },
    {
      "statement": "No bound module reads docstrings or source of another bound module at run time.",
      "verified_by": "tests/unit/test_structural_digest.py::test_no_unreviewed_code_reads_docstrings_or_source_of_other_modules"
    },
    {
      "statement": "The interpreter is Python 3.12 everywhere the digest runs.",
      "verified_by": "pyproject requires-python and CI's --python 3.12; the digest refuses any other minor version."
    }
  ],
  "alternatives_considered": [
    "A new hashes.code_scheme key: rejected, the five-key hashes set is frozen by exact-set checks in control_store._d1_native_spec and _native_daily_rule_protocol, and scheme selection would have to be threaded through every exact-equality admission check.",
    "ast.dump as the canonical form: rejected for an explicit encoder over every _fields entry, so the hashed form does not depend on dump's formatting rules.",
    "Compiled bytecode as the digest: rejected, it depends on the optimiser (constant folding) and on line tables; it is used only as the independent test oracle.",
    "Dual scheme on the rule lane: rejected, the lane's guard file changes here so no old rule approval can verify anyway.",
    "Adding the digest to the quant tier: rejected, the mutation gate would stage most of the suite for alpha_cli; a mutation self-check is recorded instead."
  ],
  "pre_mortem": [
    "The digest drops something that is behaviour (a docstring that is read, a line number that is used): mitigated by per-file reader scans that keep docstrings or fall back to bytes, a repository scan of readers, and a mutation sweep checked against compiled bytecode.",
    "A scheme-1 approval is accepted for different bytes: mitigated by keeping the byte formula frozen and testing that a comment-only edit invalidates scheme 1 while scheme 2 holds.",
    "An interpreter upgrade changes the tree format silently: the digest refuses any Python other than 3.12.",
    "Rule-lane tests assumed byte binding: one test that appended a comment as its 'changed guard' now appends a behaviour change."
  ],
  "slices": [
    {
      "title": "Structural digest module and its adversarial tests",
      "verify": "uv run pytest -q tests/unit/test_structural_digest.py",
      "expected": "Cosmetic edits keep the digest, every behaviour edit changes it, unknown or unparsable source falls back to bytes, other Python versions refuse, every behaviour-changing mutant of bound code changes the digest.",
      "rollback": "Delete apps/alpha-cli/src/alpha_cli/_structural_digest.py and the test file.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/_structural_digest.py",
        "tests/unit/test_structural_digest.py"
      ],
      "status": "done"
    },
    {
      "title": "Research lane: scheme 2 for new approvals, scheme 1 still verifies",
      "verify": "uv run pytest -q tests/unit/test_structural_digest.py tests/integration/test_research_cli.py",
      "expected": "New drafts freeze the structural code hash; _implementation_drifted accepts a scheme-1 hash only for identical bytes and a scheme-2 hash only for identical structure.",
      "rollback": "Revert research_cmds.py to compute code from _byte_code_hash only.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/research_cmds.py"
      ],
      "status": "done"
    },
    {
      "title": "Rule lanes: code and evaluator bound by structure",
      "verify": "uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_native_rule_authority.py tests/unit/test_native_daily_rule_lifecycle.py tests/unit/test_daily_rule_recovery_contracts.py tests/unit/test_native_launch_fingerprint_contracts.py",
      "expected": "Rule admission, completion and daily lifecycle tests pass; a behaviour change to an approved guard still refuses.",
      "rollback": "Revert _native_rule_environment.py and the one test edit.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py",
        "tests/unit/test_daily_rule_recovery_contracts.py"
      ],
      "status": "done"
    },
    {
      "title": "Decision record and owning document",
      "verify": "uv run python scripts/gate.py check --all",
      "expected": "ADR-0045 indexed, engineering rules updated, plan and roadmap regenerate cleanly.",
      "rollback": "Remove the ADR, its index row and the plan; restore the engineering rules section.",
      "files": [
        "docs/adr/0045-approvals-bind-code-structure.md",
        "docs/adr/README.md",
        "docs/reference/invariants/engineering.md",
        "docs/work/2026-11-14-approval-by-structure/02-plan.md",
        "docs/roadmap/capabilities.toml",
        "docs/roadmap/README.md",
        "STATUS.md"
      ],
      "status": "done"
    }
  ],
  "tier_impact": [
    "quant",
    "protected",
    "determinism"
  ],
  "docs_to_update": [
    "docs/adr/0045-approvals-bind-code-structure.md",
    "docs/reference/invariants/engineering.md"
  ],
  "out_of_scope": [
    "Any edit to the alpha_research tree, the four research CLI modules or uv.lock",
    "Run identity (_identity.py) and every provenance, launch-identity, environment or upstream-pin hash: they stay byte-exact",
    "The synthetic fixture lanes (NativeLaunch without a study, StockFixtureLaunch): authority none, stay byte-exact",
    "Adding the digest to scripts/handoff.py GUARDED or the quant tier (recommended follow-up)",
    "Approving, promoting or accepting any research artifact"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_structural_digest.py",
    "apps/alpha-cli/src/alpha_cli/research_cmds.py",
    "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py",
    "tests/unit/test_structural_digest.py",
    "tests/unit/test_daily_rule_recovery_contracts.py",
    "docs/adr/0045-approvals-bind-code-structure.md",
    "docs/adr/README.md",
    "docs/reference/invariants/engineering.md",
    "docs/work/2026-11-14-approval-by-structure/02-plan.md",
    "docs/roadmap/capabilities.toml",
    "docs/roadmap/README.md",
    "STATUS.md"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [ADR-0045](../../adr/0045-approvals-bind-code-structure.md) | — | always: the map, the design and its hazards |
| [engineering rules](../../reference/invariants/engineering.md) | Hash-bound source bytes | always |
| [research integrity](../../reference/invariants/research-integrity.md) | Owner authority | always |
| `apps/alpha-cli/src/alpha_cli/research_cmds.py` | `_implementation_hashes`, `_implementation_drifted` | research lane |
| `apps/alpha-cli/src/alpha_cli/_native_rule_environment.py` | `rule_implementation_fingerprints` | rule lane |

## Slices

1. The digest module and its tests (failing first: no module).
2. Research lane: `_implementation_hashes` freezes scheme 2; `_byte_code_hash` keeps scheme 1;
   `_approved_code_scheme` decides which one reproduces an approved hash.
3. Rule lane: `rule_implementation_fingerprints` binds `code` and `evaluator` by structure.
4. ADR, owning document, roadmap.

## Test plan

`tests/unit/test_structural_digest.py`: invariance for each cosmetic edit and the project formatter
on a real bound file; one test per behaviour edit (more than 40 kinds); fail-closed cases; the
reader scan; scheme 1 pinned to the pre-ADR formula; a comment-only and a behaviour edit to a copy
of the real research tree; a mutation sweep over real bound modules checked against compiled,
line-free bytecode (research tree always, all bound files under `slow_oracle`). Then the existing
research, rule and daily lifecycle tests, the acceptance tests and the research smoke checks.

## Look-ahead, determinism and import impact

No data path changes, so no look-ahead impact. Determinism: the digest is a pure function of file
bytes and the pinned Python minor version; warning filters cannot change it. Imports: the new module
is standard-library only and lives in `alpha_cli`, imported lazily by its two callers; no layer
contract changes.
