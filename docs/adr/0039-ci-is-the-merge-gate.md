# ADR-0039: CI on the pull request is the merge gate

**Status:** Accepted
**Date:** 2026-11-13
**Deciders:** Project ALPHA owner and AI build agents

## Context

Every local commit required a fresh "full gate stamp": all six components passing on one
unchanged tree, bound to a tree hash and to `origin/main`, plus tree-bound review, quant and
README attestations. The full gate needs native research assets and a browser stack that the
owner's development machine did not have, so the stamp was never obtained there. Work therefore
piled up uncommitted and landed in giant reconciles: 23 days with nothing merged to `main`, then a
607-file reconcile, and later about 390 files left uncommitted for six days. Bugs gathered where
no check could run.

Meanwhile GitHub CI already runs every component on every pull request (about 20 minutes), and
`main` is branch-protected. The local stamp duplicated CI while blocking the commits CI needs.

## Decision

- **CI on the pull request is the merge gate.** A single aggregate job, `ci-ok`, depends on every
  other CI job; branch protection requires only `ci-ok`. The owner merges.
- **A local commit needs only a well-formed message.** The `commit-msg` hook
  (`scripts/git_guard.py:check_message`) is the only local check that can refuse a commit; partial
  staging and work-in-progress commits are allowed. There is no pre-commit hook.
- **Agents get a fast local check**, `gate.py check` (`scripts/gate.py:run_check`, selection in
  `scripts/gate_select.py`), target three minutes: ruff, import contracts, one strict mypy run,
  then the bias guards, quick oracles, acceptance seeds, tests mapped from changed files and last
  failures. It records nothing. `gate.py component NAME` runs one CI job's steps unchanged.
- **Removed:** gate stamps and tier ranks, tree-hash and origin binding, component receipts,
  review/quant/README attestations, override and acknowledgement tokens and the harness owner
  token, evidence checkpoints, the hash-chained audit journal, the 6,000-byte manual-size step,
  `gate.py fast` and `gate.py full`.
- **Unchanged:** the `.claude` hooks and deny rules that keep agents away from owner-authority
  commands ([ADR-0038](0038-local-confirmation-and-terminal-archive-charts.md)), bias guards,
  oracles, determinism, import contracts, strict typing, Semgrep, mutation testing, the harness
  weakening scanner, and every application owner-authority control. Model review is advisory and
  visible on the pull request.

This supersedes the local-stamp, attestation and commit-guard parts of
[ADR-0014](0014-cli-owned-development-control-plane.md),
[ADR-0015](0015-evidence-ledger-not-agent-memory.md),
[ADR-0034](0034-agent-operating-system-v2.md) and
[ADR-0037](0037-agent-neutral-research-engineering.md). Their other decisions stand.

## Consequences

- Work can land in small pull requests every session; nothing waits on an environment the owner
  does not have. The local check gives feedback, not proof; CI gives the binding answer.
- CI jobs can be added, removed or renamed by editing `ci-ok`'s `needs` list, without touching
  repository settings.
- The local guarantee that a commit's exact tree passed is gone; it is replaced by CI on the merge
  candidate. A broken commit on a branch is possible and harmless; a broken merge is not possible
  while branch protection requires `ci-ok`.
- Tests that only exercised the removed machinery were deleted with it. Research-integrity tests
  and CI's test selection are unchanged.
