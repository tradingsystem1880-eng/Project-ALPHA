# Connected edge workspace — implementation and verification

> **Superseded acceptance note (2026-10-05):** pending or failed aggregate results below are historical. The canonical full gate later passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC); see `docs/BUILD-STATUS.md`.

Purpose: help the owner find, falsify and test tradable edge after costs, preserving negative
findings and the distinction between screening, exploratory results and admitted evidence.
This implements the approved `2026-09-30-edge-workspace` plan. No profitability is established.

## Delivered behavior

- Chart-side Assistant, Conditions, searchable/favourite Indicators and case-linked Notes.
  Bottom Scan results, Trades, recorded Results and Run library; persisted profile layouts and
  keyboard tab navigation. Existing Lightweight Charts stays the chart engine.
- CLI-owned condition explanations share rule comparator semantics with screening/strategies.
  Exact cutoff, evaluated bar, rule hash, operand values and unavailable/short-circuited reasons.
  Scan drilldown clears alternate data identity, including same-symbol archive charts.
- Bounded native Codex sessions, local authentication, remote model inference, server-built
  source hashes and citations, one active model, explicit cancellation and supervised timeout.
  Model tools and arbitrary execution are disabled. Filesystem isolation must pass readiness.
  Draft application rechecks sources and validates RuleSpec, then opens the existing builder.
- Evidence summary reads recorded metrics, OOS fields, assumptions, trades and baseline data;
  absent costs and validation remain absent. DSR supports scalar and nested historical shapes.
- Fixed delayed assistant restore/draft races, rule-load overwrite and note-save data loss.
  Fixed ML lost-heartbeat cancellation classification after verified process cleanup, using
  the existing bounded recovery budget and retaining capacity when state remains uncertain.

## Evidence

Independent review found and drove the stale-session, unverified run context, process lifetime,
archive identity, builder edit and note-save fixes. Final source review found no unresolved
blocker after corrections; scalar DSR was separately corrected with both-shape unit coverage.

Focused tests include shared-rule equivalence and PIT boundaries, real API/CLI assistant
sessions and stale checks, actual supervised Codex explanation and validated rule draft,
deterministic ML cancellation recovery, deferred browser responses, and real browser scan →
canonical chart → hashed conditions. Model output in smoke tests explicitly withheld an edge
claim when costs and OOS evidence were missing. Browser fixtures are synthetic, not market evidence.

Final implementation verification: `ALPHA_PLAYWRIGHT_PORT=8803 uv run python scripts/gate.py full`
passed all six components (backend, frontend, literature, Qlib, atlas and eval) on one unchanged
tree. `gate.py check --tier full` confirmed the receipt at 2026-09-30T13:56:34Z, tree
`3908303d2ca9e4f36b27802b73811397cbe90ef8699786fea74ec87c6b5b94ff`.
The full run includes backend coverage, typing, import/security/API checks, wheel smoke,
numerical oracles and mutation checks, frontend coverage and all 244 browser scenarios.
Log: `/tmp/alpha-edge-complete-gate.log`. The gate must be rerun after this delivery-document
update; the machine receipt in `.alpha/state/gate-stamp.json` is the current-tree authority.

All 58 focused assistant backend tests passed, including provider symbols `^VIX`, `^TNX`,
`EURUSD=X` and `ES=F` with exact symbol and PIT preservation, plus unsafe-input and traversal
rejection. Eleven final focused browser journeys cover stale rules, explicit job failures,
saved-turn recovery and delayed edit/save responses. Independent review closed remaining
findings. A real Codex smoke test with final runtime flags returned a cited answer correctly
withholding an edge claim from 20 synthetic bars (`/tmp/alpha-assistant-final-smoke.log`).
Current-store labels say Stored chart; only verified snapshots/archives claim integrity verification.

Earlier mixed-tree runs were not acceptance receipts. One frozen run passed 243 browser
scenarios but failed the 25,000-bar stress budget by 0.085 percentage points. Three isolated
repeats and the subsequent complete browser suite passed with unchanged thresholds; the
original failure is retained in `/tmp/alpha-edge-frozen-gate.log`. This is bounded local
performance evidence, not a guarantee for every host. The live owner backend was restarted
after confirming no active jobs and its health check passed.

## Limits and separate work

Conditions currently support canonical daily bars only; alternate dataset contexts visibly
refuse substitution. Assistant legacy run attachment requires verifiable snapshot and cutoff.
Notes and model text are observations, not admitted research evidence. Missing provider access,
external-drive readiness and paid feeds are not repaired by an assistant response. Live orders,
autonomous promotion, arbitrary code, scheduling and new timeframe engines are out of scope.

The separate `feat/research-workflow-completion` checkout retains ownership of its research
changes. Coordination handoffs are recorded; no automatic cross-branch integration occurred.
