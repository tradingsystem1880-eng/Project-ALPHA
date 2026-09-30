# Codex-only continuation evidence

- `historical-inventory.json.gz` and `preservation.json`: hashes for 57,664 original files;
  all verified unchanged. The inventory contains paths/hashes, not raw research contents.
- `controlled-legacy/`: the preserved 143-card controlled subset, rendered with unknown legacy
  suite/scorer provenance. These are historical judgments, not newly rescored results.
- `judge-smoke/`: successful Codex judge smoke over retained A04 evidence.
- `codex-gap/`: new isolated diagnostic cohort, 15 completed Codex variants, 12 pass / 3 fail /
  0 critical / 0 harness-invalid / 0 ungraded, using `codex-gap-audit-v1`.
- `codex-gap-analysis/`: per-objective diagnostics for those 15 variants. Fixed base-capability
  totals and matched base/hint comparisons are intentionally empty because this cohort has no
  base scenarios. Do not pool it with the historical acquisition cohort to claim improvement.

The gap cohort used 352 tool calls and 3,471.1 aggregate trial seconds. Cost is unknown.
A rubric pass can reward an appropriate bounded design where the fixture cannot support execution;
consult the [capability audit](../../../../docs/audit/2026-09-29-codex-capability-audit.md) for what was
actually investigated, which workflow stopped, and which fixture defects were found.

Raw trials and revision manifests stay under `$ALPHA_EVAL_HOME` (default `~/.alpha-bench`).
All new trials/judges are Codex. Independent trace review is same-provider review, not cross-model
validation. No benchmark result grants research promotion or trading authority.

## Retained realistic evidence

`realistic-regraded/` and `realistic-analysis/` use `codex-evidence-audit-v4`: 132 trajectories,
53 pass / 64 fail / 11 automated critical / 3 harness-invalid / 1 oversized ungraded. All 128 primary
judgments were reused from V3 for the final deterministic correction. The historical acquisition
limits remain; no model ranking or improvement claim follows.

`critical-review.json` qualifies all 11 critical cards: eight supported critical behaviors, two
skill-workflow departures whose authority label is too broad, and one disputed design flag. Read it
before treating automated critical rates as confirmed failures. `legacy-matched-hints/` reports
retained Sonnet base/hint diagnostics; it launches no Claude model and does not compare old/new harnesses.

## Verification

`final-preservation.json` records the final unchanged-file and 15-trial isolation checks.
`verification.json` retains frozen-copy backend/frontend receipts and the aggregate UI blocker.
The backend passed; the full gate did not. No full-gate or hidden-suite acceptance is claimed.

`verification-2026-09-30.json` supersedes the earlier aggregate blocker: all six components passed
on one stable tree, checked against the live checkout. Later delivery documentation edits are
explicitly outside that stamp. Earlier failed receipts remain preserved; historical research
evidence and scoring were not changed.
