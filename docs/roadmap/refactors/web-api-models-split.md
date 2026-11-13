# Split alpha_web/api/models.py per router and unify StrictModel

**Risk:** M

## Scope

`apps/alpha-web/src/alpha_web/api/models.py`: 3,407 lines, 320 classes, imported by 30 Python
files. `StrictModel` (`BaseModel` with `extra="forbid"`) is defined three times with identical bodies:
`api/models.py:15`, `api/ml.py:25` and `api/v3.py:19`. The API package has 28 modules. Downstream
generated artifacts: `apps/alpha-web/frontend/openapi.json` (36,714 lines) and
`apps/alpha-web/frontend/src/api/generated.ts` (20,415 lines).

## Why

One 3,400-line module couples every router's schema; three `StrictModel` copies can drift in
configuration.

## Invariants at risk

- OpenAPI component names and schemas must not change: Pydantic qualifies colliding class names by
  module, so moving classes can rename components and break `generated.ts` consumers.
- `scripts/check_openapi_operations.py` classification and the governance matrix must stay in sync.
- `models.py` is in the `source_sha256` set of `scripts/capture_c04_risk_basis_fixture.py`; the
  committed `riskMetricBasis.provenance.json` records its hash, so the C04 fixture must be re-captured
  (and reviewed) after the split.

## Proof required before/after

- Before: snapshot of `openapi.json` and `generated.ts`.
- After: regenerated `openapi.json`/`generated.ts` are byte-identical to the snapshot (or every diff
  is a reviewed, intended rename); `check_openapi_operations.py --write` produces no change; web unit,
  integration and Playwright suites pass; the C04 fixture is re-captured with its test passing.

## Suggested slicing

1. Make `api/ml.py` and `api/v3.py` import the single `StrictModel` (no schema change).
2. Move one router's models at a time into `api/models/<router>.py`, re-exporting from
   `api/models.py` so imports keep working; regenerate and diff OpenAPI after each move.
3. Remove the re-export shim once all importers are updated.
