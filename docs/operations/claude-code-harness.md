# Agent-neutral engineering checks and the Claude adapter

Current rule: **CI on the pull request is the merge gate**
([ADR-0039](../adr/0039-ci-is-the-merge-gate.md), which supersedes the local-stamp parts of
[ADR-0037](../adr/0037-agent-neutral-research-engineering.md) and ADR-0034). Application owner
authorization, scientific verification and sandbox boundaries are unchanged.

## Verification and discovery

`uv run python scripts/gate.py check` is the fast local check; `gate.py component NAME` runs one
CI job's steps (`backend`, `frontend`, `literature`, `qlib`, `eval`) exactly as CI does.
The [development loop](development-loop.md) describes both. Nothing local records that a tree
passed: there are no stamps, receipts, attestations, override tokens or audit journal.

`uv run python scripts/fs.py orient [--json] [--component NAME]` (also `gate.py orient`) lists
components, module counts and the routing documents, computed from directory listings.
`uv run python scripts/fs.py search "QUERY" [--kind KIND] [--limit N] [--format json]` returns
ranked excerpts of tracked documentation, live documents ahead of archived history. Neither reads
owner data, untracked files or hidden tests ([ADR-0040](../adr/0040-one-file-system-atlas-retired.md)).
`alpha info commands --all --json` lists every command leaf; `alpha info procedures --json`
describes registered analysis families, verified protocols and scan commands. These are descriptive,
not executable authority registries.

The only Git hook is `.githooks/commit-msg` (via `scripts/git_guard.py`), installed with
`uv run python scripts/git_guard.py install`. It refuses a commit whose subject is not
`type(scope): summary` and nothing else. `gate.py lint-harness` (in CI) fails if a deny rule,
a hook event, `--strict-markers` or the coverage floor is weakened against
`.claude/harness-baseline.json`; `gate.py baseline` rewrites that file for review in a pull request.

<a id="checkpoint-retention-without-evidence-loss"></a>
Gate checkpoints and `gate.py checkpoints` were removed with ADR-0039. Existing
`.alpha/state/gate-checkpoints/` folders are left untouched and are history, not current evidence.

## Thin Claude adapter

`scripts/claude_hooks.py` is stdlib-only and has precisely four entrypoints:

| Event | Entrypoint | Behavior |
|---|---|---|
| SessionStart | `session-start` | Bounded pointers to CLAUDE.md, applicable rules, the canonical skill, orientation and the local check. No scanning or telemetry. |
| PreToolUse: Read/Edit/Write/MultiEdit | `pre-file-guard` | Denies hidden-holdout paths, including resolved symlinks and nested edit paths. |
| PreToolUse: alpha MCP | `pre-mcp-guard` | Retains denial of owner research decisions, overrides and holdout reveal. |
| PreToolUse: Bash/WebFetch/MCP | `pre-owner-action-guard` | Denies tool input naming owner-action routes or owner-auth enrollment/recovery, including decoded references. |

The adapter no longer requires acknowledgments before source edits, checks Stop
or task/subagent completion, runs prompt judges, reinjects per-turn prose, or writes session/audit
telemetry. It does not lint each edit or infer shell mutations. The owner-action guard scans
Bash/WebFetch/MCP tool inputs for the existing denied routes and credential ceremonies; it is not
a shell parser. CI on the pull request owns engineering verification.

File/MCP checks fail closed on malformed inputs and when their script is unavailable. Session
guidance is advisory and does not block startup. Agent role labels and the former
`ALPHA_HARNESS_DISABLE` variable cannot bypass hidden-file safety. Proposed tests
belong in `tests/holdout_seed/`; agents may run hidden tests without reading their source.

All pre-existing native deny entries remain in `.claude/settings.json`, including secret access,
destructive Git operations, owner research commands, owner-auth recovery/enrollment and protected
IBKR operations. Explicit native Read/Edit/Write denials also cover `tests/holdout/**`.
Subagent native `disallowedTools` settings are separate and retained.

These tool-boundary rules are **not an operating-system filesystem sandbox**. Arbitrary process
execution must remain constrained by the runtime's native sandbox and agent instructions; removing
the shell-text parser does not create stronger process isolation. The bounded MCP server and
application owner-auth enforcement remain authoritative regardless of adapter presence.

## Quantitative and domain controls

Keep point-in-time poison guards with discriminating leaky controls, import-linter boundaries,
strict typing, immutable evidence verification and review on the pull request. Statistical changes require
primary-source verification under `.agents/skills/quant-source-verification/` and relevant numeric,
metamorphic, calibration and differential tests. Quantification remains in Python.

`gate.py mutate`, `semgrep`, `determinism` and `raise-cov` remain available. A timeout or unexecuted
mutant is not a kill; preserve honest mutation floors. `raise-cov` reports uncovered raises and is
not itself a successful behavioral test. Component/CI definitions own current scheduling.

Owner Touch ID, sealed D2 authorization, provider receipts, paper opt-ins, venue/unit separation,
and no-live-capital routing are application controls. No engineering receipt, advisory model
response, screening result or Monte Carlo scenario output substitutes for them. The optional
Codex bridge remains a read-only second opinion, not an approver.

## Historical state

Older `.alpha/state/` and `.claude/state/` files (stamps, receipts, attestations, the audit
journal) are no longer read or written. They are left in place; do not treat them as evidence
that any current tree passed, and do not delete a state directory as a recovery shortcut.

### Research walkthrough operation

Crypto screening discovers content-hash-verified manifest metadata across the local
inventory, then fully verifies only matching normalized inputs and their raw lineage.
Unrelated bulk artifact bytes are not read by screening discovery. Metadata corruption
still fails closed; `CryptoBulkStore.inventory()` remains a full artifact audit, and
replay re-verifies each frozen selected input. No persistent verification cache is used.

Unsupported research observations remain neutral, unresolved drafts with an explicit
missing-operator blocker. They do not inherit a double-bottom mechanism, trough fields,
US-market chart assumptions or a fabricated executable protocol. Explicit registered
operator/event intent still selects the corresponding supported draft path. Historical
immutable contracts are not rewritten, and neither draft capture nor screening grants
approval, promotion, sealed-data or trading authority.

For interactive inspection, project the large JSON response with `jq` while preserving
the CLI exit status (`set -o pipefail`); full per-date data remains in the immutable
attempt artifacts. The [closure record](../superpowers/plans/archive/2026-09/2026-09-19-research-walkthrough-closure.md)
tracks acceptance checks and limitations.

### Scoped missing-suite exception (2026-09-17)

The owner explicitly authorized this refactor/cancellation commit to proceed without
the unavailable private holdout suite, after unsuccessful restoration checks. The
[exception record](../superpowers/plans/2026-09-17-cancellation-and-research-walkthrough.md)
and independent-reviewer instructions define its one-time scope. Hidden tests remain
UNVERIFIED. Other tests, independent review, quant attestation and Git guards remain
mandatory; this is neither a hook bypass nor a waiver for future changes.

A separate explicit owner resolution on 2026-09-19 covers only the
[walkthrough closure change](../superpowers/plans/archive/2026-09/2026-09-19-research-walkthrough-closure.md)
based on `b1b7510`. It has the same UNVERIFIED disclosure and preserves all other
checks; it does not automatically extend the earlier exception to future work.

A third explicit owner resolution on 2026-10-05 covers only the commits made under the
[clean-and-reconcile plan](../superpowers/plans/2026-10-05-clean-reconcile-main.md). Hidden
tests remain UNVERIFIED; every other check stays mandatory; no extension to later work.


## Checkpointed weekly mutation execution (2026-10-10)

`scripts/mutation_fragment.py inventory` under pinned `mutmut==3.8.0` generates every functional
module's canonical mutant identity with the backend's original generator. Then
`scripts/mutation_sweep.py plan --commit SHA --run-id RUN-ATTEMPT --mutants mutation-keys.json`
freezes the entire `all_quant_source_modules` inventory, source hashes and complete mutant lists.
Sorted identities are partitioned round-robin into balanced, disjoint fragments of at most
96 mutants each; constant-only modules retain a singleton job. The current inventory has 250 jobs and
planning rejects matrices over GitHub's 256-job limit. Weekly scheduling and
on-touch local mutation requirements are preserved. Each hosted job uses unique temporary
staging, at most two `mutmut run --max-children` workers and eight matrix jobs concurrently.
Modules without functions use pinned `mutmut==2.5.1` serially because mutmut 3 cannot mutate
their module-level constants. Both backends retain exactly the selected tests and exclusions.
Inventory freezes the backend; checkpoints identify it. Legacy export requires actual mutant
rows for the assigned source, known terminal statuses and a test hash; empty or unfinished
measurements fail completeness. `--CI` makes legacy score findings report-only while fatal
errors still fail. No constants are dropped or reclassified as successful empty measurements.
Each functional fragment regenerates and verifies the complete frozen identity set before
executing its exact assigned names with the unchanged associated tests. Its export requires
every assigned verdict terminal and every unassigned verdict untouched. Aggregate reconstructs
counts from disjoint per-mutant verdicts, requires their exact complete union and identical
excluded-test audits, then computes each module's original floor verdict. Partial backend
whole-module exports are never accepted. Setup, preflight and test statistics repeat per fragment;
no mutant executes more than once. Concurrency and worker bounds are unchanged.
Checkpoints initialize before dependency installation and atomically record module, full expected
inventory, commit, run/attempt, phase, elapsed time, command timings and terminal measurement.
Command logs persist separately during execution. SIGTERM/interruption records an unfinished
checkpoint; hard runner loss can still prevent upload and is detected as missing aggregation.

Preflight and mutation retain their 5400-second limits; export retains 120 seconds. A shared
11100-second elapsed budget bounds commands, with process-group TERM/KILL cleanup and upload
headroom inside the 200-minute job limit. Setup/staging filesystem time remains outside command
timeouts and is included in elapsed-budget accounting before each command. Local mutation also
cleans descendant processes and uses unique staging. Tooling absence remains locally nonblocking.

Always-upload artifacts include run/attempt and module index; `aggregate` runs even when a shard
fails. It rejects missing, duplicate, malformed, stale, mismatched or unfinished records and
unaccounted/interrupted mutant counts, and writes a success or failure summary artifact. Low kill
rates remain report-only hosted findings. Minimum 0.90, tolerance 0.005, baseline floors, selected
tests, excluded-test audit, and conservative timeout/no-tests accounting are unchanged. No
baseline writes occurred. Local mocked checks do not prove hosted completion.


Before merge, the existing default-branch `nightly.yml` dispatcher can run the candidate branch's
new reusable sweep: `gh workflow run nightly.yml --ref BRANCH -f mutation_sweep=true`.
The explicit input defaults false; scheduled nightlies retain their ordinary non-mutation checks.
Manual mutation callers use a separate concurrency group and cannot be cancelled by a scheduled
nightly. The reusable sweep's own concurrency still prevents overlapping mutation batches.

The pinned functional adapter explicitly certifies successful fresh full test-statistics collection
when no mutant has associated tests. The certificate binds source, generated inventory and effective
staged configuration, records executed test IDs/durations and staged import origins, and requires
empty tracer hits plus untouched metadata. Only assigned mutants receive conservative `no_tests`
verdicts (zero kills); generic tool failures and invalid certificates still block completeness.


### Collection-time SQLite contention

Unmutated collection can expose the public concurrent-control-store migration test. Preserve
its assertions, timing and test selection; retain chained errors and SQLite codes before diagnosis.
WAL negotiation retries only exact `SQLITE_BUSY` outside a transaction within the configured
busy-timeout budget, with remaining milliseconds applied per attempt and the original timeout
restored. The normal five-second WAL budget is not an overall `_open` deadline; migration waits
are unchanged. Other errors and exhausted budgets still fail. Complete fresh hosted results remain
mandatory; retries never manufacture mutation measurements or bypass the aggregate.
