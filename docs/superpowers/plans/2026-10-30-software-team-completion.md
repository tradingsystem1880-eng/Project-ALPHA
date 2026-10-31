# Software Team workflow completion

**Delivery state:** Completed — bounded scope delivered through [PR99](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/99).
The [verified main receipt](../../BUILD-STATUS.md#2026-10-30--verified-combined-delivery-on-main) records qualification and seven passing post-merge jobs. Private coverage remains UNVERIFIED; broader product and Mac scope remain open.

```json
{
  "schema_version": 1,
  "title": "Complete the existing Software Team development workflow",
  "context": "Finish the foundation backlog's missing orphan-test precondition and reconcile conflicting implementation instructions. Reuse the existing development roles and exact-tree gate; do not create another agent framework. Preserve the configured UV cache across the web-to-CLI boundary to repair the demonstrated installed-worker portability failure blocking qualification.",
  "assumptions": [
    {"statement": "Seven lifecycle tests in durable leases, research execution, suite execution and workstation jobs depend on the Linux test owner's orphan reaping.", "verified_by": "Foundation runtime-contract record, bounded process-test inventory and real non-reaping diagnostic probes with retained zombie metadata."},
    {"statement": "Implementation is authorized, and the owner approved a task-scoped private-suite absence-only exception through delivery; publication remains separately coordinated.", "verified_by": "Owner decision at 2026-10-30 05:41 UTC; bounded scope recorded append-only in .claude/agents/independent-reviewer.md, with private provenance retained outside publication."},
    {"statement": "Installed-worker capability requests need the configured writable UV cache in this managed runtime.", "verified_by": "Clean pinned f847 main passed before worker installation, failed afterward; forwarding only UV_CACHE_DIR restored both routes and schema validation."}
  ],
  "alternatives_considered": ["Keep per-slice full gates and commits: conflicts with the focused development loop and creates redundant qualification work.", "Add another team orchestration framework: existing roles and gate already provide the approved architecture."],
  "pre_mortem": ["An inherited owner marker could be stale or identify an unrelated process; validate live ancestry and process birth identity.", "Workflow edits could accidentally weaken commit verification; retain a full gate and independent review before every actual commit.", "Unavailable private coverage could be mislabeled as a pass; report UNVERIFIED and retain the approved task-scoped absence decision and never claim a private-suite pass.", "A cache correction might expose owner configuration; forward only the named non-secret UV_CACHE_DIR and regress HOME/credential filtering without weakening worker validation."],
  "slices": [
    {"title": "Fail early for orphan-dependent tests without their owner", "verify": "uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_gate_process_supervisor.py tests/unit/test_durable_job_lease.py tests/unit/test_research_execution.py tests/unit/test_suite_executor.py tests/unit/test_web_invoke.py", "expected": "A red-first unwrapped setup probe fails before implementation; supported owner launches and existing lease assertions pass after implementation.", "rollback": "Revert only the scoped owner-precondition changes.", "files": ["scripts/run_owned_test.py", "tests/conftest.py", "tests/unit/test_gate_process_supervisor.py", "tests/unit/test_durable_job_lease.py", "tests/unit/test_research_execution.py", "tests/unit/test_suite_executor.py", "tests/unit/test_web_invoke.py"], "status": "done"},
    {"title": "Preserve configured UV cache for web-launched CLI workers", "verify": "uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_web_invoke.py tests/unit/test_ml_selection.py tests/unit/test_web_ml.py::test_ml_capabilities_relays_only_cli_worker_probe plus the two installed-worker API capability integration cases", "expected": "Configured/absent cache regression is red first; both actual capability routes and existing worker failure/credential checks pass after the one-variable forwarding correction.", "rollback": "Revert only UV_CACHE_DIR forwarding and its portable regression.", "files": ["apps/alpha-web/src/alpha_web/_catalog.py", "tests/unit/test_web_invoke.py"], "status": "done"},
    {"title": "Reconcile workflow ownership and prepare final qualification", "verify": "Focused harness and Git-guard regressions, plan-check, lint-harness, then uv run python scripts/gate.py full and independent review", "expected": "Instructions use focused checks during edits and a full gate before each actual commit. Review and stale-evidence controls remain enforced. Any unavailable suite is disclosed.", "rollback": "Revert only workflow guidance and its delivery record.", "files": [".agents/skills/alpha-feature-workflow/SKILL.md", ".agents/skills/incremental-implementation/SKILL.md", ".claude/commands/implement.md", ".claude/commands/plan-feature.md", ".claude/rules/tests.md", "docs/operations/development-loop.md", "docs/BUILD-STATUS.md", "CLAUDE.md", ".claude/agents/independent-reviewer.md"], "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["CLAUDE.md", "docs/operations/development-loop.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-10-30-software-team-completion.md"],
  "out_of_scope": ["Product research agents", "Research recovery/cancellation", "Claude-owned ML response-schema and local-PDF fixes", "Filesystem/context-map redesign", "General codebase refactor", "Private test source", "Publication without the parent's authorization"],
  "files": ["scripts/run_owned_test.py", "tests/conftest.py", "tests/unit/test_gate_process_supervisor.py", "tests/unit/test_durable_job_lease.py", "tests/unit/test_research_execution.py", "tests/unit/test_suite_executor.py", "tests/unit/test_web_invoke.py", ".agents/skills/alpha-feature-workflow/SKILL.md", ".agents/skills/incremental-implementation/SKILL.md", ".claude/commands/implement.md", ".claude/commands/plan-feature.md", ".claude/rules/tests.md", "docs/operations/development-loop.md", "docs/BUILD-STATUS.md", "CLAUDE.md", "architecture/atlas/generated/graph.json", "architecture/atlas/generated/inputs.json", "architecture/atlas/generated/views/unknowns.json", "docs/superpowers/plans/2026-10-30-software-team-completion.md", "apps/alpha-web/src/alpha_web/_catalog.py", ".claude/agents/independent-reviewer.md"]
}
```

No engine imports, point-in-time semantics, seeds, statistical thresholds, or application authority change. The owner identity is a diagnostic execution precondition, not an authorization boundary. Linux does not expose another process's subreaper flag for independent inspection; the wrapper publishes identity only after successfully establishing ownership.

Acceptance uses a real unwrapped/wrapped regression, the existing stale stamp/review tests, the canonical six-component gate, and an independent reviewer. The private suite is not inspected or fabricated. A public check does not establish private coverage or production readiness.

## Focused evidence before aggregate qualification

- The new unwrapped setup regression failed against the original implementation:
  `assert result.returncode == 1` observed `0` and successful setup. No orphan test body ran.
- After the precondition was added, both actual durable-lease descendant tests passed;
  the complete process-supervisor and lease modules passed (58 tests). The wrapper was
  exercised through a real pytest worker, and missing/malformed/stale/unrelated/self
  owner identities were rejected. Existing cleanup, timeout, signal and exit assertions remain.
- Harness gate/skill, Git guard, component receipt, awareness and manual checks:
  322 passed, 1 skipped (the optional locally installed upstream plugin comparison).
- Ruff check/format, scoped mypy and harness lint passed. The failed Atlas invocation
  from repository root was a command-location error; Atlas has its own isolated project
  and is generated from `tools/alpha-atlas/`.

These are scoped results. At writing, final aggregate verification, independent approval,
the new private-suite absence decision, and publication authorization remain outstanding.

## Expanded orphan-precondition acceptance

The narrow two-test checkpoint subsequently passed all six components on unchanged Git tree
`6c14cc8c1fea8c4b693f9fda2a74053fd8667a1d`. Its patch, independent BLOCK verdict and passing
receipts remain preserved. That checkpoint does not qualify this expanded candidate.

A bounded public inventory of real descendant creation, PID/group disappearance assertions and
process-specific descendant test names found five further dependent cases. Each was run with its
original assertions and budgets under plain pytest inside a diagnostic supervisor that retained
adopted children until pytest exited. The existing outer process owner retained final cleanup
ownership. This deliberately supplies no prompt orphan reaping; it does not measure PID 1 latency.
All five failed in their actual cleanup path and left an adopted zombie, rather than failing to
import or collect:

- research `test_sigterm_reaps_child_and_returns_interrupted`;
- suite `test_suite_heartbeats_and_cancels_after_leader_exits_with_live_descendant`;
- suite `test_suite_cancellation_kills_and_reaps_nested_worker_group`;
- workstation `test_live_heavyweight_cancel_reaps_a_sigterm_ignoring_nested_child`;
- workstation `test_durable_startup_status_failure_reaps_the_entire_process_group`.

The setup regression matrix initially reported 5 failed / 2 passed, exposing exactly those missing
preconditions. The five tests now request the same scoped fixture as the durable pair. All seven
run through both real owner and pytest-worker routes. The complete five covering modules passed
135 tests. No application cleanup code, assertion, timeout or accounting budget changed.

The bounded inventory excluded cooperative acquisition/native payloads whose parents explicitly
wait for children, direct-child cleanup, pidfd exit-only escaped-child checks, RPC/heartbeat
checks that require stopped execution rather than PID disappearance, mocked assistant cleanup,
and supervisor tests that already launch the actual owner themselves. Cooperative acquisition and
native descendant cases also passed through the non-reaping diagnostic route with no adopted
orphans, confirming their parents supply the required reaping. Their distinct contracts
are retained; subprocess use alone is not a reason to require this fixture. The test-layer rule
now directs future externally reaped cases into the existing fixture and acceptance matrix.

This expansion still requires final-tree aggregate verification and independent review. The
private suite remains UNVERIFIED pending the task-scoped absence-only decision. The filesystem
owner's zero-byte discovery-link substitution is reserved for coordinated integration; this
candidate does not duplicate that link or alter the 5,995-byte manual budget.

## Configured cache portability acceptance

The expanded tree's aggregate failed only the two ML capability integration routes; the full
result was 2 failed / 6,713 passed / 61 skipped with 93.01% coverage against the unchanged 93% floor.
The failure remains retained and is not waived by any absence-only decision. Both routes failed
alone and after a capability mock neighbor in reversed order. Clean main `f847581` with its own
imports and locked environments passed before worker installation and failed after installation.

Exact response/CLI evidence identified an unwritable default UV cache, not a schema mismatch.
The web process allowlist dropped configured `UV_CACHE_DIR`; the existing CLI-to-worker allowlist
already supported it. A process-local diagnostic forwarding change restored 200 responses whose
schema-version-1 payloads validated against the unchanged response model. The production fix now
forwards only that non-secret variable. It changes no worker validation, credentials, HOME routing,
API model, local-PDF behavior or lifecycle budget.

The portable regression was 2 failed / 2 passed before the production correction. Afterward the
focused cache/web/CLI/worker checks passed 38 tests, including the original two real API cases.
Configured cache values survive; absent ones are not invented; HOME, CODEX_HOME, OPENAI_API_KEY,
ALPHA_TEST_OWNER and unrelated shell state stay excluded for ML and generic command cases.
Existing worker-error and malformed-entrypoint tests remain unchanged and passing.

All code, docs and generated changes must be frozen before the corrected candidate's full gate
and fresh independent review. Private coverage and publication remain separately pending. The
manual is now 5,998 bytes; the filesystem owner's zero-byte Map substitution remains reserved for
coordinated integration and needs no duplicate link or removal of an essential instruction.

## Through-delivery absence decision and final acceptance

Implementation slices record focused-verified work, not aggregate acceptance. The corrected
software tree `cf154fec628d71dd92122aa0df1cca40b4d8989c` passed all six components without changing
contents during its run. Its receipts remain preserved as a distinct checkpoint.

The owner approved the four-workstream absence-only exception at 05:41 UTC on 2026-10-30,
including Software Team corrections and integration through delivery. The append-only reviewer
record preserves existing policy/history and changes no actual test requirement or threshold.
Private coverage remains UNVERIFIED, never PASS; private contents stay protected. Actual failures
and other unavailable checks still block. This task-scoped decision does not require renewal on
each changed candidate, and grants no GitHub APPROVE review, protection bypass or uncoordinated
publication. Private authorization provenance is retained outside published source and payloads.

Because that record changes protected source, final acceptance requires a fresh exact-tree full
gate and independent attestation including the record. The prior software pass is not rebound to
this tree. Publication remains separately coordinated after normal repository checks and review.
