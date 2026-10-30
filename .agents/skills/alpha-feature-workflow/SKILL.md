---
name: alpha-feature-workflow
description: The mandatory Project ALPHA development pipeline for any multi-file feature or change - explore via the navigator subagent, plan as a dated plan doc, implement with TDD in small slices, pass the tiered gate, then independent review (plus quant verification for statistical code). States when to skip so trivial work never bloats.
---

# ALPHA Feature Workflow

The pipeline that turns "make a change" into verified, reviewed, committed work.
It composes the repo's existing skills — `karpathy-guidelines` (always),
`incremental-implementation`, `code-review-and-quality`,
`verification-before-completion` — with the harness's mechanical gates.

## When to skip

- Single-file fix with an obvious test → skip straight to TDD + `/gate fast`.
  No plan doc; the harness still enforces stamps and reviews at commit time.
- Docs-only change → omit a feature plan; commit checks still apply to the tested tree.
- Never skip for: anything touching quant paths, `alpha_backtest`, the seven
  risk-tier `alpha_cli` modules, cross-package work, or new public seams.

## The pipeline

1. **Explore** — dispatch the `navigator` subagent with the concrete question
   ("where does X live, what invariants apply, where do I add Y"). Keep the main
   context clean; you want file:line maps and applicable invariants, not file dumps.
   For risky areas also dispatch `invariants-auditor` in parallel.
2. **Plan** — `/plan-feature`: a dated plan doc in `docs/superpowers/plans/`
   (`YYYY-MM-DD-<slug>.md`, repo convention) with context, small coherent slices,
   a focused per-slice verify command, and explicit DAG / look-ahead / determinism
   impact. Slice by behavior and risk, not a line quota. Never a 1-step plan;
   if it would be, no plan was needed. Existing task authorization covers routine
   implementation choices; ask only when a real scope or authority gap remains.
3. **TDD implement** — per slice: failing test → minimal code → green →
   focused covering checks → self-review → continue the next dependent slice.
   Use `/gate fast` when broader backend feedback is useful; it excludes platform
   tests and does not replace their covering checks. Data/strategy changes require a
   `@pytest.mark.bias_guard` future-poison test (see `tests/bias_guards/`).
   Load `incremental-implementation` for the slicing discipline.
4. **Gate** — finish code, docs and generated outputs, then stage the coherent
   candidate and run `uv run python scripts/gate.py full` before every actual commit.
   Related verified slices may share one commit; unrelated work remains separate.
   No intermediate commit is required merely to advance to the next slice. Installed Git
   hooks bind the staged tree to verification; CI checks the shared component commands.
   Never soften or summarize away a failing step. See `docs/operations/claude-code-harness.md`.
5. **Review** — review-scope paths (risk-tier, protected control plane, hooks and guarded
   config) need `/review-gate` (independent APPROVE bound to the current tree); quant
   paths need `/verify-quant` (PASS attestation bound to
   the quant diff). BLOCK findings are fixed and re-reviewed, never argued away.
6. **Docs honesty** — CLAUDE.md / spec / plan-doc status updates land in the same
   change as the code they describe (repo rule). Run
   `verification-before-completion` before claiming done.

The implementing owner stays responsible through necessary fixes, QA, review findings,
documentation/context upkeep and authorized delivery. Use the existing `navigator`,
`test-architect`, `independent-reviewer` and, when useful, `retrospective` roles;
development roles are separate from product research agents. Handoffs identify the
candidate, owned paths, remaining work, exact commands/results and missing authority.
Delegate read-only review with the diff and binding hashes, without author justifications;
never manufacture the verdict or treat an advisory second opinion as approval.
Preserve failed-run evidence before retries. Changed contents invalidate prior evidence;
reuse unchanged focused results only within their scope. Follow the
[development loop](../../../docs/operations/development-loop.md) for final qualification.

## Non-negotiables inherited from CLAUDE.md

Smallest diff that satisfies the request; no speculative abstractions; fail loud
(no empty `except`); Polars by default; `as_of`-only data access; seeds derive
from semantic namespaces; conventional commits; the architecture DAG is never
violated. This manual defers to CLAUDE.md wherever they conflict.
