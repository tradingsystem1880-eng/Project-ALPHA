**Delivery state:** Completed locally; aggregate verified (2026-09-16).
Final delivery is valid only with a fresh current-tree full stamp.

# Agent-neutral engineering and reproducible research

```json
{
  "schema_version": 1,
  "title": "Agent-neutral engineering and reproducible research",
  "context": "Owner approved the audited roadmap on 2026-09-16: thin local guards, unified screening and reproducibility program, supported historical reads retained. Baseline HEAD f250489 has pre-existing Phase C panel work that must be preserved.",
  "assumptions": [
    {"statement": "The runtime DAG, authority boundaries and historical evidence remain unchanged.", "verified_by": "import-linter, public authority contracts, migration and historical research tests"},
    {"statement": "Refactoring source may change new execution fingerprints without changing scientific results.", "verified_by": "source-bound identity and numerical equivalence tests"}
  ],
  "alternatives_considered": ["Rejected a universal workflow engine and package mergers; reuse CLI composition and existing stores.", "Rejected CI-only checks; retain thin Git guards and independent review evidence."],
  "pre_mortem": ["A blanket V2 approval rule breaks V1 confirmation and historical admission; restrict cutover to new exploration approval.", "A gate stamps concurrent edits or a partial commit; bind stable tested tree and require staged-tree equality.", "Screening loses failed/repeated attempts or hashes live aliases; freeze exact inputs and record each attempt separately."],
  "slices": [
    {"title": "0 Preserve baseline and owner work", "verify": "git status --short; compare recorded owner-file hashes", "expected": "Pre-existing Phase C bytes preserved", "rollback": "No runtime state changed", "status": "done"},
    {"title": "1 Shared checks and thin local guards", "verify": "uv run pytest -q tests/unit/test_gate_components.py", "expected": "Stable-tree component receipts and local/CI parity", "rollback": "Restore prior adapters; retain audit reads", "status": "done"},
    {"title": "2 Versioned research parameters and explicit intent", "verify": "uv run pytest -q tests/unit/test_research_analysis_plan_v2.py tests/integration/test_research_program_acceptance.py", "expected": "V2 rejects ignored axes; V1 confirmation and history remain valid", "rollback": "Disable new V2 creation but retain readers", "status": "done"},
    {"title": "3 Generated discovery and concise orientation", "verify": "uv run alpha info procedures --json; uv run python scripts/gate.py orient --json", "expected": "Complete descriptive discovery and <=6KB default orientation", "rollback": "Restore prior discovery consumer", "status": "done"},
    {"title": "4 Proven metadata and orchestration simplification", "verify": "uv run lint-imports; relevant suite/migration/surface tests", "expected": "Stable public contracts and transaction behavior", "rollback": "Revert each mechanical extraction independently", "status": "done"},
    {"title": "5 Frozen-input screening and attempt provenance", "verify": "offline screening, replay, bias and interruption tests", "expected": "Repeated/failing attempts retained; exact input replay; authority none", "rollback": "Disable launches; preserve stored specs and readers", "status": "done"},
    {"title": "6 Integration and final acceptance", "verify": "uv run python scripts/gate.py full", "expected": "All required components pass on one stable tree with independent review", "rollback": "Disable new link creation while retaining readers", "status": "done"}
  ],
  "tier_impact": ["protected", "risk", "quant", "bias", "determinism"],
  "docs_to_update": ["AGENTS.md", "CLAUDE.md", "docs/BUILD-STATUS.md", "docs/operations/claude-code-harness.md"],
  "out_of_scope": ["Live provider/broker actions", "Owner research approvals", "D2 lifecycle redesign", "New cost models and portfolio sizing", "Runtime package mergers", "Historical evidence rewriting"],
  "files": ["scripts/", ".github/workflows/", ".claude/", "apps/alpha-cli/", "apps/alpha-web/frontend/", "apps/alpha-mcp/", "tools/alpha-atlas/", "tests/", "docs/", "AGENTS.md", "CLAUDE.md"]
}
```

## Baseline evidence

At HEAD `f250489`: 1,311 tracked files; 138,306 owned runtime/research-script lines;
8,196 development-tooling lines; 104,717 test lines; 12 workspace packages and two
isolated workers. Six principal harness modules total 3,873 lines. Root guidance
totals 28,452 bytes. The audit run passed 4,608 offline tests (two skips), 93.14%
coverage, in 205.65 seconds; fast selection passed 1,714 (one skip) in 36.87 seconds.
Ruff, mypy, import contracts, frontend types/lint/309 tests, both workers and 12
wheel builds passed. Atlas freshness failed on the removed `shell/screens.tsx`.
Full gate, browser acceptance, mutation and slow-oracle completion were not claimed.

## Accepted implementation boundaries

- Preserve existing approved V1 exploration execution/admission/recovery and V1
  confirmation. New double-bottom exploration approvals use V2; crypto keeps its
  existing separate contract. Never migrate immutable stored contracts on read.
- Keep procedure discovery descriptive: one registry projection, no new workflow
  executor. Keywords suggest intent; explicit resolved choices determine execution.
- Screening requires frozen content-bound inputs. Scientific spec identity differs
  from invocation identity. Every repeat/failure/interruption remains inspectable.
  Trial counts alone cannot supply PBO/RC/SPA inputs.
- Git hooks provide local feedback, not cryptographic authority. CI independently
  verifies committed changes. Runtime owner authorization and hidden-test isolation
  remain distinct from engineering acknowledgements.
- Each component receipt binds tree, definition, command set and terminal result;
  concurrent changes, missing components and stale success cannot form a full pass.
- Preserve numerical behavior, migrations, serialized historical contracts and the
  62-tool MCP surface. No external messages, owner data mutations or trading actions.

## Current implementation state

All implementation slices are delivered, with focused independent reviews. The
aggregate candidate gate passed; final source/documentation updates require a
fresh exact-tree full pass, as recorded in `.alpha/state/` rather than a self-hashed
document. No commit, owner approval or live-provider readiness is implied.

### Preservation checkpoint

Rechecked during implementation: all seven pre-existing Phase C files match the
initial SHA256 values (panel primitive, package exports, fixtures, differential and
metamorphic tests, unit tests, and research path rule). No owner data or approval
state was modified. HEAD remains `f250489`; changes are not committed.

### Verified increments (not aggregate acceptance)

- Gate regression reproduced then fixed: files changed during checks cannot gain a
  passing stamp. Seven stamp tests passed.
- Shared component definitions and receipts added; a failed component invalidates
  prior full success, and full backend Semgrep does not silently skip a clean CI
  checkout. Merge-base change selection includes committed and untracked files.
- Thin Git commit guard rejects unstamped and partially staged trees; six tests
  passed, including a real Git-hook invocation in a disposable repository.
- Research V2 broader regression suite: 276 passed. Schema/constants extraction:
  220 migration/concurrency/control-store tests passed. Migration helper ASTs and
  SQL text remain unchanged; no transaction orchestration was relocated.
- Shared suite vocabulary retains MCP holdout exclusion and unchanged OpenAPI.
  Root orientation is computed from current source, not stale runtime data.

### Evidence-based scope refinement

Do not move migration functions merely to reduce the ControlStore line count:
their fault-injection globals and backup/lock seams are a deliberate compatibility
contract. Extract immutable schema constants with facade reexports instead.
Likewise, relocating the 992-line suite planner would not simplify it. The bounded
increment instead shares cutoff/redaction construction across eight sites and
isolates null-family command building, preserving validation order; 65 targeted
planner/executor/catalog tests passed. The planner remains large (about 887 lines).

### Final candidate evidence

- Root instructions: 5,968 bytes combined, down from 28,452. Claude adapter:
  113 lines, down from 1,169; source/index discovery replaces repeated prose pins.
- Real Git hooks installed (`core.hooksPath=.githooks`). Guards bind exact staged
  content to the tested tree and independent protected/risk review. Local hooks
  remain bypassable; CI independently consumes shared component commands.
- Preserved legacy audit: 833 events, chain intact. New state is `.alpha/state/`;
  old tokens are not imported. Numeric file/contract-count ratchets are retired;
  actual architecture and bias tests remain required.
- Independent final V2 review: 178 tests passed. Actual V2 roles and one primary
  horizon are frozen; missing/null new exploration plans fail closed. V1 historical
  validation, fingerprints and existing-approval idempotence remain supported.
- Screening uses content-bound specs and distinct invocation/trial evidence,
  preserves ordinary index-exit outcomes, and verifies typed crypto quality.
  Existing context packets can link a verified identifier/hash-only screening
  reference; default packets and authority are unchanged.
- Slow oracles: six passed. Mutation: panel 548/580 (94.48%, floor 90%);
  overfitting 118/145 (81.38%, existing floor 77.7%). No timeouts credited as kills.
- Twelve wheels built and imported from a temporary installation outside checkout.
- Aggregate candidate verification: `uv run python scripts/gate.py full` passed
  backend, frontend/browser, literature, Qlib and Atlas on one stable tree, with
  709.8 seconds of checks. `gate.py check --tier full` confirmed the stamp. Earlier
  concurrent-edit runs correctly refused a passing receipt.
- Final reproducibility hardening canonicalizes V2 family order. Reordering a
  scientifically identical plan must not alter its fingerprint; historical V1
  fingerprints and numerical measurements remain unchanged. The focused research
  regression run passed 260 tests after two observed red ordering regressions.
- A later parallel run reported one ML cancellation-test failure (isolated rerun
  passed); its cause was not established because the coverage table displaced the
  traceback in tail-only gate output. Component failures now retain complete output,
  with a regression test; no cancellation deadline or coverage threshold was relaxed.
- Interrupted parallel coverage left an unignored `.coverage.*` shard; Git tree
  comparison proved that its removal alone invalidated a later passing backend
  run. Ignore these generated shards alongside `.coverage`; a red/green regression
  verifies their creation/removal cannot change the source-tree hash. Tracked-file
  and real-source change checks remain intact.

### Exact-tree acceptance procedure

After final documentation and generated Atlas updates, rerun
`uv run python scripts/gate.py full` and `uv run python scripts/gate.py check --tier full`.
The ignored stamp and all five component receipts identify the delivered tree and
terminal results. Editing this record afterwards would invalidate that stamp, so
the final handoff reports the fresh verification result without mutating this file.

### Explicit limitations

Screening is research-only, not portfolio simulation, confirmatory inference, or
proof of edge. Equity horizons count observed union rows; common-calendar gaps
are disclosed, not calendar-validated. Trial counts are not PBO/RC/SPA input and
are not propagated into optimization claims. Generic approval of the separate
crypto crowding plan remains a pre-existing unsupported path; this refactor does
not broaden its authority. No owner data, approvals, provider or broker actions
were exercised, and no commits were made.
