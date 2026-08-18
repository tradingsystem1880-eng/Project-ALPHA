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

- Single-file fix with an obvious test → skip straight to TDD + `/gate-fast`.
  No plan doc; the harness still enforces stamps and reviews at commit time.
- Docs-only change → just edit and commit (the commit guard waives docs-only diffs).
- Never skip for: anything touching quant paths, `alpha_backtest`, the seven
  risk-tier `alpha_cli` modules, cross-package work, or new public seams.

## The pipeline

1. **Explore** — dispatch the `navigator` subagent with the concrete question
   ("where does X live, what invariants apply, where do I add Y"). Keep the main
   context clean; you want file:line maps and applicable invariants, not file dumps.
   For risky areas also dispatch `invariants-auditor` in parallel.
2. **Plan** — `/plan-feature`: a dated plan doc in `docs/superpowers/plans/`
   (`YYYY-MM-DD-<slug>.md`, repo convention) with context, slices of ≤ ~100 lines
   each, a per-slice verify command, and explicit DAG / look-ahead / determinism
   impact. Never a 1-step plan; if it would be, no plan was needed.
3. **TDD implement** — per slice: failing test → minimal code → green →
   `/gate-fast` → conventional commit. Data/strategy changes require a
   `@pytest.mark.bias_guard` future-poison test (see `tests/bias_guards/`).
   Load `incremental-implementation` for the slicing discipline.
4. **Gate** — `/gate` (full tier) before any commit; the pre-bash guard enforces
   the stamp mechanically. Never soften or summarize away a failing step.
5. **Review** — risk-tier paths need `/review-gate` (independent APPROVE bound to
   the current tree); quant paths need `/verify-quant` (PASS attestation bound to
   the quant diff). BLOCK findings are fixed and re-reviewed, never argued away.
6. **Docs honesty** — CLAUDE.md / spec / plan-doc status updates land in the same
   change as the code they describe (repo rule). Run
   `verification-before-completion` before claiming done.

## Non-negotiables inherited from CLAUDE.md

Smallest diff that satisfies the request; no speculative abstractions; fail loud
(no empty `except`); Polars by default; `as_of`-only data access; seeds derive
from semantic namespaces; conventional commits; the architecture DAG is never
violated. This manual defers to CLAUDE.md wherever they conflict.
