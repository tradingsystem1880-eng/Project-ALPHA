# Break up oversized CLI functions

**Risk:** M

## Scope

Measured with `ast` on 2026-11-13 (lines = `end_lineno - lineno + 1`):

| Function | File | Lines | Branch nodes | Parameters |
| --- | --- | ---: | ---: | ---: |
| `build_suite_plan` | `apps/alpha-cli/src/alpha_cli/_suite.py` (2,275 lines) | 889 | 104 | 6 |
| `_run_confirm` | `apps/alpha-cli/src/alpha_cli/research_cmds.py` (4,216 lines) | 291 | 25 | 2 |
| `_run_deep` | `research_cmds.py` | 275 | 26 | 2 |
| `run_research` | `research_cmds.py` | 232 | 21 | 3 |
| `_fetch_binance` | `apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py` (4,692 lines) | 272 | 34 | 12 |
| `_acquire_result` | `crypto_data_cmds.py` | 256 | 36 | 22 |

Across `apps/` and `packages/` (excluding tests), 41 functions exceed 200 lines and 187 exceed 100.

## Why

Functions of this size are hard to review and test in isolation; `_acquire_result` takes 22
parameters.

## Invariants at risk

- D1/D2 seeds, suite plans and execution fingerprints are frozen: refactoring must not change
  any planned seed, ordering or serialized plan byte.
- `alpha_cli` is an execution package, so any edit changes `_identity.execution_fingerprint` for new
  runs (expected, but must be stated).
- Crypto acquisition receipts and bounded-transport behavior (timeouts, page limits, refusals) must
  stay identical.

## Proof required before/after

- Before: characterization tests that serialize `build_suite_plan` output for representative
  specs and the full D1/D2 command outputs on fixtures; recorded receipts for `_fetch_binance` and
  `_acquire_result` with an injected transport.
- After: identical serialized plans, receipts and exit codes; oracle and bias-guard tiers pass.

## Suggested slicing

1. Characterization tests first (no production change).
2. Extract pure helpers from `build_suite_plan` stage by stage.
3. Introduce a parameter object for `_acquire_result` / `_fetch_binance`.
4. Share the confirm/deep scaffolding in `research_cmds`.
