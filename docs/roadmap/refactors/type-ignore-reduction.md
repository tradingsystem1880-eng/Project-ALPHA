# Reduce `# type: ignore` suppressions

**Risk:** L

## Scope

308 `# type: ignore` comments in tracked Python (measured 2026-11-13): 239 under `tests/` (202 in
73 files of `tests/unit`; most in `test_research_control_store.py` 25, `test_figure_builders_synthetic.py`
18) and 69 elsewhere. Source hot-spots (`alpha_data/quantpad_archive.py`, 6, was removed 2026-11-14): `scripts/mutation_fragment.py` 5,
`alpha_data/adapters/yfinance_adapter.py` 5, `alpha_cli/research_data_audit.py` 5,
`alpha_cli/ibkr_what_if.py` 5, `alpha_cli/figures/_builders.py` 5. By code: `arg-type` 170,
`attr-defined` 32, `misc` 28, `index` 26, `import-untyped` 15.

## Why

Blanket suppressions hide real typing errors under `mypy --strict`, mostly in tests that pass
deliberately malformed values.

## Invariants at risk

- Tests that intentionally pass wrong types (to prove validation) must keep doing so; use `cast` or
  typed helpers rather than weakening assertions.
- `alpha_data/pipeline.py` and other identity-bound files (see the canonical-JSON refactor) change
  runtime identities if edited.

## Proof required before/after

- Before/after: `uv run mypy` clean with fewer ignores; no test assertion changes; protected tiers
  untouched.

## Suggested slicing

1. Tests: replace `arg-type` ignores in malformed-input tests with typed `object` helpers.
2. Source: fix `import-untyped` with stubs where available.
3. Leave identity-bound files for a coordinated change.
