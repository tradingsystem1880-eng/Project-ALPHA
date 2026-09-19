# Agent-neutral engineering checks and the Claude adapter

Current transition: **implemented locally; full aggregate verified, 2026-09-16**.
[ADR-0036](../adr/0036-agent-neutral-research-engineering.md) supersedes the engineering ceremony
of ADR-0034. Application owner authorization, scientific verification and sandbox boundaries remain
unchanged. The [implementation plan](../superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md)
and fresh gate results determine acceptance; this document does not claim the entire program passed.

## Verification and discovery

Run `uv run python scripts/gate.py full` for aggregate verification. Shared component definitions
cover `backend`, `frontend`, `literature`, `qlib` and `atlas`; run one with
`uv run python scripts/gate.py component NAME`. A partial component pass is not a full pass.
CI and local execution consume the shared definitions; receipts must describe the checked tree.

`uv run python scripts/gate.py orient [--json] [--component NAME]` reads the shared computed
source index. It neither launches the Atlas viewer nor reads owner data or hidden tests.
`alpha info commands --all --json` lists every command leaf; `alpha info procedures --json`
describes registered analysis families, verified protocols and scan commands. These are descriptive,
not executable authority registries.

The real Git guards are `.githooks/pre-commit`, `.githooks/commit-msg` and
`scripts/git_guard.py`. They check staged-content verification evidence and commit-message
requirements without trying to parse arbitrary shell commands. **Installation is a separate local
step and is not asserted by the presence of those files.** Verify `core.hooksPath` and the guard
tests before claiming commit enforcement is active. Git hooks are bypassable local convenience
checks; CI must independently verify changes.

## Thin Claude adapter

`scripts/claude_hooks.py` is stdlib-only and has precisely three entrypoints:

| Event | Entrypoint | Behavior |
|---|---|---|
| SessionStart | `session-start` | Bounded pointers to CLAUDE.md, applicable rules, the canonical skill, orientation and gate. No scanning or telemetry. |
| PreToolUse: Read/Edit/Write/MultiEdit | `pre-file-guard` | Denies hidden-holdout paths, including resolved symlinks and nested edit paths. |
| PreToolUse: alpha MCP | `pre-mcp-guard` | Retains denial of owner research decisions, overrides and holdout reveal. |

The adapter no longer requires acknowledgments before source edits, intercepts Bash, checks Stop
or task/subagent completion, runs prompt judges, reinjects per-turn prose, or writes session/audit
telemetry. It does not lint each edit or infer shell mutations. Git guards and the shared gate own
engineering verification.

File/MCP checks fail closed on malformed inputs and when their script is unavailable. Session
guidance is advisory and does not block startup. Agent role labels, owner-token environment values
and the former `ALPHA_HARNESS_DISABLE` variable cannot bypass hidden-file safety. Proposed tests
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
strict typing, immutable evidence verification and independent review. Statistical changes require
primary-source verification under `.agents/skills/quant-source-verification/` and relevant numeric,
metamorphic, calibration and differential tests. Quantification remains in Python.

`gate.py mutate`, `semgrep`, `determinism` and `raise-cov` remain available. A timeout or unexecuted
mutant is not a kill; preserve honest mutation floors. `raise-cov` reports uncovered raises and is
not itself a successful behavioral test. Component/CI definitions own current scheduling.

Owner Touch ID, sealed D2 authorization, provider receipts, paper opt-ins, venue/unit separation,
and no-live-capital routing are application controls. No engineering receipt, advisory model
response, screening result or Monte Carlo scenario output substitutes for them. The optional
Codex bridge remains a read-only second opinion, not an approver or attestation authority.

## Current state and historical evidence

New agent-neutral engineering state belongs in `.alpha/state/`. Historical
`.claude/state/harness-audit.jsonl` is retained; read it using:

```bash
uv run python scripts/gate.py audit --legacy
```

The adapter does not delete or rewrite historical logs and does not consume old ack/override
tokens. Historical records describe the controls that existed when they were written; they do
not prove the new Git hooks are installed or that the current tree passed. Do not delete a state
directory as a recovery shortcut.

The root manual, active plan and BUILD-STATUS must distinguish implemented slices, checks actually
run, local hook installation, and aggregate acceptance. After configuration changes, a running
client may need to reload repository settings; file presence alone does not prove that happened.

Stage the intended candidate before final review/quant attestation. Moving a new file
from untracked to staged changes the scoped-diff serialization even when its content
tree is identical; if staging follows review, the independent reviewer must verify
identity and refresh the binding before commit. Do not bypass the guard.

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
attempt artifacts. The [closure record](../superpowers/plans/2026-09-19-research-walkthrough-closure.md)
tracks acceptance checks and limitations.

### Scoped missing-suite exception (2026-09-17)

The owner explicitly authorized this refactor/cancellation commit to proceed without
the unavailable private holdout suite, after unsuccessful restoration checks. The
[exception record](../superpowers/plans/2026-09-17-cancellation-and-research-walkthrough.md)
and independent-reviewer instructions define its one-time scope. Hidden tests remain
UNVERIFIED. Other tests, independent review, quant attestation and Git guards remain
mandatory; this is neither a hook bypass nor a waiver for future changes.

A separate explicit owner resolution on 2026-09-19 covers only the
[walkthrough closure change](../superpowers/plans/2026-09-19-research-walkthrough-closure.md)
based on `b1b7510`. It has the same UNVERIFIED disclosure and preserves all other
checks; it does not automatically extend the earlier exception to future work.
