# Bounded controller iteration

## Decision and learning

The paired panel showed that adding measurements improved empirical completion but increased tool/time consumption and still allowed missing conclusions and omitted denials. This iteration moves the execution/result-accounting part into deterministic CLI code. It is deliberately one baseline plus one validation, no agent roles, candidate search or new authority. Existing Pydantic validates the frozen plan; adding PydanticAI transport would not fix the measured execution and evidence-accounting problems.

The [smoke evidence](../../tools/alpha-eval/results/controller-v1-20260930/README.md) demonstrates actual engine completion, independent snapshot-session reconciliation, explicit denied-order disclosure and byte-identical receipt replay. It does not demonstrate an agent-level completion uplift. The first controller only supports the existing momentum operator; R19's rules recipe remains outside its coverage. Expanding a controller is useful only when operator coverage and temporal information boundaries match the research question.

## Normalized independent review

|id|severity|area|location|issue|impact|proposed_fix|source|status|
|---|---|---|---|---|---|---|---|---|
|RE01|high|lifecycle|research_execution.py:run_child|SIGTERM bypassed cleanup|Validation child could outlive controller|Convert active-child SIGTERM to interruption, reap process group, restore handler; subprocess regression with SIGTERM-resistant descendant|Independent delivery_review reproduction|Fixed; regression failed before patch and passes after patch|

Patch queue: RE01 applied in the child lifecycle and tests. No statistical estimator or engine behavior changed. Semantic session checks reuse the existing splitter. Abrupt SIGKILL/controller death remains unverified cleanup; restart does not authorize replacement work.

## Next experiments, in order

1. Extend the closed operation contract to immutable rule specifications and targeted diagnostic operators; prohibit arbitrary argv and preserve snapshot/cost/source matching. This is required before claiming the controller addresses the retained rules-based dead-end task.
2. Build a physically cutoff-restricted sandbox from canonical data with distinct derivative lineage and corporate-action knowledge times. Deny original snapshots, future reports and inherited messages. Prove forbidden reads fail in a fresh context; never describe `--as-of` alone as an information firewall.
3. Compare controller-backed and existing single-agent execution on a small new versioned panel, preserving all pressure turns, tool limits, final-answer requirements and failed attempts. Score task completion separately from fixed-operator completion, and keep a final-report reserve.
4. Only then compare optional artifact-bound data/overfitting/economic reviews against controller alone. Adopt additional roles only if they improve detected errors and usable evidence per bounded resource budget. Macro remains conditional on vintage/publication-lag relevance.

## Verification record

Focused diagnostic/controller suite: 39 passed, including 25 new controller/digest tests. New modules and CLI command code passed Ruff and mypy. A real copied-snapshot baseline/validation and unchanged-plan replay completed; evidence hashes were checked. Canonical full-gate and final independent-review acceptance are bound to the delivered tree by their accompanying receipts, not inferred from these focused results. Main/UI integration remains owned by the concurrent UI session; this branch must not overwrite its changes.

Full-gate preparation found missing test-helper type annotations (fixed), then a coverage-only rejection at 92.99% despite 4718 passing tests. Added receipt identity/mismatch and public digest CLI tests; the 93% coverage threshold remains unchanged. Earlier rejected logs remain external evidence, not acceptance.
