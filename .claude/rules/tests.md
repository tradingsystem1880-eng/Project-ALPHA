---
paths:
  - "tests/**"
---
# Test-layer rules

- Placement: `tests/unit/` (pure), `tests/integration/` (CLI/engine), `tests/bias_guards/` (every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test; each guard has a must-fail leaky twin so a vacuous guard is itself detected — see `tests/bias_guards/test_future_poison_pattern.py`), `tests/oracles/` (metamorphic / calibration / differential; `oracle`, `slow_oracle`), `tests/holdout/` (hidden behaviour tests the authoring agent never reads or edits).
- Markers are strict (`--strict-markers`): `bias_guard`, `network`, `oracle`, `slow_oracle`, `holdout`. Goldens live in `tests/fixtures/`; statistical goldens carry tolerances, never exact float equality.
- `tests/unit/test_claude_harness_*.py`, `tests/bias_guards/**`, `tests/oracles/**`, and `tests/holdout/**` are protected control plane (`gate.py ack` per edit).
- A test that cannot run is reported `UNVERIFIED:`; failing output is quoted verbatim.
