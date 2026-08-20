---
paths:
  - "tests/**"
---
# Test-layer rules

- Placement: `tests/unit/` (pure), `tests/integration/` (CLI/engine), `tests/bias_guards/` (every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test; each guard has a must-fail leaky twin so a vacuous guard is itself detected — see `tests/bias_guards/test_future_poison_pattern.py`), `tests/oracles/` (metamorphic / calibration / differential; `oracle`, `slow_oracle`), `tests/holdout/` (hidden behaviour tests the authoring agent never reads or edits).
- Markers are strict (`--strict-markers`): `bias_guard`, `network`, `oracle`, `slow_oracle`, `holdout`. Goldens live in `tests/fixtures/`; statistical goldens carry tolerances, never exact float equality.
- `tests/unit/test_claude_harness_*.py`, `tests/bias_guards/**`, `tests/oracles/**`, and `tests/holdout/**` are protected control plane (`gate.py ack` per edit).
- A test that cannot run is reported `UNVERIFIED:`; failing output is quoted verbatim.
- Agents never read, edit, or shell-write `tests/holdout/`. To propose a holdout test, stage it under `tests/holdout_seed/` (unprotected) and tell the owner to `git mv` it in.
- Quant-rigor sweeps (`scripts/gate.py`): `mutate [modules|--all]` (mutmut per module in a staged tree; kill-rate ≥ 0.90 or the module's recorded `.claude/mutation-baseline.json` floor, whichever is lower; baseline writes need an ack), `semgrep [--changed]` (`.semgrep/alpha.yml`), `determinism` (goldens/identity/determinism tests twice under perturbed `PYTHONHASHSEED`/`TZ`), `raise-cov [--fail]` (unexercised `raise` sites in quant modules; 177/576 unreached at the 2026-08-19 baseline, so nightly runs it report-only). The fast gate runs semgrep on changed files; the full gate adds slow oracles + the mutation gate only when a quant SOURCE module changed; `.github/workflows/nightly.yml` runs everything (mutation sweep with `--timeout 5400`; a module's `timeout`/`no_tests` mutants are never credited as kills, so renderer-heavy modules carry low but honest floors).
