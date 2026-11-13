# Consolidate canonical-JSON, hash and strict-validator helpers

**Risk:** H

## Scope

Private helpers are re-defined per module. Measured on 2026-11-13 with `git grep` over tracked
`*.py` (definitions = `def <name>(`; call sites = `<name>(` excluding definitions):

| Helper | Definitions | Call sites |
| --- | ---: | ---: |
| `_canonical` | 13 | 52 |
| `_canonical_json` | 5 | 97 |
| `canonical` | 4 | 72 |
| `_sha` | 10 | 62 |
| `_sha256` | 8 | 39 |
| `_hash` | 10 | 118 |
| `_digest` | 9 | 55 |
| `sha256_file` | 4 | 104 |
| `_text` | 13 | 220 |
| `_number` | 11 | 116 |
| `_object` | 11 | 177 |
| `_integer` | 9 | 82 |
| `_finite` | 7 | 42 |
| `_utc` | 5 | 20 |
| `_reject_constant` | 4 | 4 references (passed as `parse_constant=`) |

123 definitions across 82 files: 46 in `apps/alpha-cli`, 8 each in `packages/alpha-data` and
`packages/alpha-research`, 6 in `apps/alpha-web`, 2 each in `alpha-strategies`, `alpha-study` and
`tests/unit`, 1 each in `alpha-mcp`, `alpha-backtest`, `alpha-validation`,
`scripts/rdagent_foundation_contract.py` and `workers/literature`, and 3 in `workers/qlib`. A further
150 lines call `json.dumps(..., separators=(",", ":"))` inline (115 of them with `sort_keys=True`, in
96 files). Counts were adjusted on 2026-11-13 for the files removed with ADR-0040. Same-named helpers are not all equivalent (some sort keys, some reject NaN, some allow
floats); each must be classified before merging.

## Why

Duplicated encoders and validators drift: a fix to one copy (for example NaN rejection or key
ordering) does not reach the others, and reviewers cannot tell which variant a hash used.

## Invariants at risk

- Every hash-bound output (receipts, manifests, execution traces, research contracts, ControlStore
  ledger rows, fixture provenance) must stay byte-identical; changing an encoder silently breaks
  verification of stored artifacts.
- Worker copies (`workers/qlib`, `workers/literature`, `workers/rdagent`) stay separate by design:
  they are isolated projects with their own locks and may not import `alpha-*` packages; the
  literature worker's `_acquisition.py` is a byte-pinned copy (`tests/unit/test_literature_worker_pin.py`).
- Every byte of the `alpha_research` tree and several `alpha_data` modules feed runtime identity
  hashes (`research_cmds._implementation_hashes`, `comparison_acquisition._policy_hash`), and all
  execution packages feed `_identity.execution_fingerprint`; touching them changes those identities.

## Proof required before/after

- Before: golden tests that re-encode existing committed receipts and fixtures (for example
  `apps/alpha-web/frontend/e2e/fixtures/*.provenance.json`, `tools/alpha-eval/results/**`) with each
  current helper and assert byte equality, plus a classification table mapping each definition to
  one canonical variant.
- After: the same golden tests pass unchanged against the shared helper; bias guards, oracles and the
  full gate pass; identity-hash changes are listed and accepted by the owner where unavoidable.

## Suggested slicing

1. Inventory and classify all 123 definitions; add golden tests (no production change).
2. Introduce one shared module per layer (`alpha_core` for pure encoders) with the variants found.
3. Migrate one package at a time, starting where no identity hash covers the file.
4. Leave worker copies and identity-bound files for last, each with an explicit owner decision.
