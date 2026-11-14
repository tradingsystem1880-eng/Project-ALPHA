# Break up oversized functions

**Risk:** M

## Scope

`.claude/code-size-baseline.json` caps 98 functions over the 150-line limit (2026-11-14, `def` line
to last line; `tests/unit/test_code_size.py` enforces it): 55 of 151-200 lines, 32 of 201-300,
11 over 300, 21,389 lines in all. Largest: `_suite.py::build_suite_plan` 889,
`alpha_qlib_worker/real.py::_fold_model` 394, `tabular_adapters.py::fit_tabular` 329,
`research_intake.py::draft_exploration_contract` 325, `_artifacts.py::write_execution_trace` 325,
`portfolio_replay.py::run_weight_replay` 321, `alpha_research/gate_packet.py::build_research_gate_packet`
319.

| Group | Functions | What a change costs |
|---|---:|---|
| `control_store.py` | 18 | daily-rule approvals; planned in `control-store-split.md` |
| other approval-bound files (`research_intake.py`, `alpha_research/gate_packet.py`, `_artifacts.py`, `artifact_contract.py`, `_native_fixture_store.py`, `_native_rule_completion.py`, `daily_native_cmds.py`) | 9 | research or daily-rule approvals; `alpha_research` is also quant tier (mutation gate) |
| isolated workers (`workers/qlib`, `workers/rdagent`) and `tools/alpha-eval` | 7 | worker tests and CI jobs; no approval for Qlib or eval |
| harness scripts (`scripts/gate*.py`, `harness_quant.py`, `mutation_sweep.py`, browser lanes) | 5 | protected files: reviewed pull request |
| `alpha_data` | 3 | owned by the data stream while it works there |
| everything else (`research_cmds.py` 6, `research_gate_packet.py` 4, command modules, `_suite.py`, backtest, strategies, web) | 56 | run fingerprints only |

## Why

A function over 150 lines cannot be reviewed or tested in isolation; the worst have many
parameters (`crypto_data_cmds.py::_acquire_result` takes 22).

## Invariants at risk

- D1/D2 seeds, suite plans and execution fingerprints are frozen: refactoring must not change any
  planned seed, ordering or serialized plan byte.
- Any `alpha_cli` edit changes `_identity.execution_fingerprint` for new runs (expected; state it).
- Crypto acquisition receipts and bounded transport behaviour (timeouts, page limits, refusals)
  stay identical.

## Proof required at each step

- Before: a characterisation test of the function's observable output on representative inputs
  (serialized suite plans for `build_suite_plan`; full D1/D2 command outputs on fixtures; recorded
  receipts with an injected transport for the crypto fetchers), unless an existing golden already
  pins it.
- After: identical outputs, exit codes and receipts; the baseline entry lowered or removed in the
  same change; oracle and bias-guard tiers pass.

## Plan

1. **`build_suite_plan` (889 lines)** first, on its own: a characterisation test over the suite
   specs in the tests, then extract one stage at a time. It is 889 of the unbound group's 12,700 lines and
   touches no approval.
2. **`research_cmds.py`'s six** (`_run_confirm`, `_run_deep`, `run_research`, `_approval_payload`,
   `draft_confirmation`, `draft`): share the confirm and deep scaffolding; covered by the existing
   research CLI tests.
3. **The rest of the unbound group** only when a feature edits the function: the feature's pull
   request splits it below 150 lines (the size test then requires removing its baseline entry).
4. **Bound groups** with the control-store split's renewal window (control store, `_artifacts.py`,
   `artifact_contract.py`, native files) or a research re-approval the owner schedules
   (`research_intake.py`, `alpha_research`).

## Recommendation

Steps 1 and 2 now: together about 2,300 lines in two files that most of the waiting features
read, no approval cost. Everything else as features touch it; the size test already stops growth,
and bound functions wait for a renewal window the owner chooses.
