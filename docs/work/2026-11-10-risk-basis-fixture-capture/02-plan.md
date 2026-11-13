**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Complete deferred synthetic risk-basis fixture",
  "context": "The 174-path authored handoff explicitly deferred its synthetic response fixture. Complete fresh versioned capture using existing real TestClient/CLI and artifact seams; do not claim historical recovery or a general numerical oracle.",
  "assumptions": [
    {
      "statement": "Inputs and visible expectations are public synthetic contracts, not owner or protected data.",
      "verified_by": "C04 public plan and test_c04_risk_anchor_disclosure.py/test_c04_web_metric_basis.py; preserved handoff explicitly defers generation."
    },
    {
      "statement": "Existing four-case browser assertions and dedicated Vite configuration remain unchanged.",
      "verified_by": "Exact predecessor/final byte comparison."
    }
  ],
  "alternatives_considered": [
    "Recover authentic bytes first: exact preserved manifest omits the fixture and explicitly defers it.",
    "Capture real responses with independent checks rather than hand-authoring scenario numbers or adding a new framework."
  ],
  "pre_mortem": [
    "Captured output could be mistaken for a numerical oracle: separate fixed independent checks from unverified transport inputs in provenance.",
    "Environment or output drift could leak owner state or replace evidence: use temporary store/home/cache, source-bound identities, strict validation and immutable publication.",
    "Default browser collection uses the wrong server for this source harness: preserve and disclose the separate routing issue."
  ],
  "slices": [
    {
      "title": "Specify and implement bounded capture",
      "verify": "New explicit public producer tests, including real capture, repeatability, validation and immutable publication negatives.",
      "expected": "Documented two synthetic curves produce legacy/disclosed pairs only after independent and schema checks.",
      "rollback": "Remove new producer/test/fixture/sidecar from this separate successor.",
      "files": [
        "scripts/capture_c04_risk_basis_fixture.py",
        "tests/integration/test_c04_risk_basis_fixture.py",
        "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.json",
        "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.provenance.json"
      ],
      "status": "done"
    },
    {
      "title": "Record provenance and scoped delivery",
      "verify": "Scoped lint/type checks, manifest and patch binding, manual budget and original browser byte preservation; independent review and dedicated browser execution delegated separately.",
      "expected": "Fresh generated fixture identity, honest limitations, unchanged application source and browser assertions.",
      "rollback": "Remove this successor; preserved 6bc source and historical evidence remain unchanged.",
      "files": [
        "docs/work/2026-11-10-risk-basis-fixture-capture/02-plan.md",
        "docs/BUILD-STATUS.md"
      ],
      "status": "done"
    }
  ],
  "tier_impact": [
    "determinism"
  ],
  "docs_to_update": [
    "docs/work/2026-11-10-risk-basis-fixture-capture/02-plan.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "Application source, formulas, defaults and authority changes",
    "Default browser-suite routing, full gates, protected tests, historical result bodies, models, providers, owner data, installs, commits and publication"
  ],
  "files": [
    "scripts/capture_c04_risk_basis_fixture.py",
    "tests/integration/test_c04_risk_basis_fixture.py",
    "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.json",
    "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.provenance.json",
    "docs/work/2026-11-10-risk-basis-fixture-capture/02-plan.md",
    "docs/BUILD-STATUS.md"
  ]
}
```

**Delivery state:** Completed for bounded fixture capture and public producer checks. Independent final review and the unchanged dedicated browser lane remain pending; normal-suite/full qualification is not claimed.

## Provenance and scope

The preserved `combined-authored-handoff-v3-risk3551` handoff explicitly deferred the
science synthetic-response fixture to an authorized combined build. Its 174-path
source manifest and 191-member bundle inventory contain no original fixture bytes.
The handoff text has SHA256 `0a91184a8981208f03aef7a1bf8f0f179309722fbe91752b12e66ff99c262ff3`.
This completes that deferred deliverable as a **fresh synthetic capture, producer
version 1**, not historical recovery. Existing browser filenames, assertions,
selectors, waits and timeouts are unchanged.

The command uses the existing artifact publisher and versioned run identity to
create two artificial UTC equity series, then calls the real FastAPI TestClient,
HTTP route, strict response model and CLI subprocess. No route or CLI result is
mocked. Both legacy and opted-in payloads are captured for `[900,950,1000]` and
`[1000,900,1000]`, at January 1–3, 2024 UTC. Declared starting cash 1000 deliberately
does not establish true initial-capital or external-cash-flow coverage.

Independent expectations come from the pre-existing public C04 plan and tests:
anchors 900/1000; exact version-1 convention literals and unknown states; base
compounded returns `1000/900 - 1 = 1/9` and `1000/1000 - 1 = 0`; drawdowns 0 for the
monotone path and `900/1000 - 1 = -1/10` for the loss path. Numeric absolute tolerance
is 1e-12 with zero relative tolerance. The entire legacy payload must equal the
opted-in payload after removing only `metric_basis`. Every response is strict
schema validated; duplicate JSON keys and all non-finite numbers are rejected.
Other scenario fields are **captured UI inputs**, not independent numerical goldens.
Nothing here establishes scientific validity, complete risk-metric correctness,
research admission or trading authority.

The sidecar records producer/version/hash, exact inputs, no random seed (there is
no sampling), request options, source/run/artifact fingerprints, runtime versions,
independent checks and fixture hash. Case records are recomputed from fixed inputs,
current execution source and synthetic Parquet bytes before publication; missing,
extra or forged record fields fail. Existing run identity deliberately tracks
execution-source changes. IDs, timestamps and payload fields are never normalized
or scrubbed to obtain repeatability. Identical bytes are expected only with the
same source and relevant runtime; changed output requires an explicitly reviewed
new generation, never an automatic golden update.

## Capture and verification

Use a **fresh process** in an existing approved project Python environment with its
`alpha` executable. Do not install dependencies merely to run this command.
From the repository root, substituting that environment's absolute Python path:

```bash
/path/to/existing/.venv/bin/python -B scripts/run_owned_test.py --timeout 120 -- \
  /path/to/existing/.venv/bin/python -B scripts/capture_c04_risk_basis_fixture.py \
  --output-dir apps/alpha-web/frontend/e2e/fixtures
```

The output directory receives `riskMetricBasis.json` and
`riskMetricBasis.provenance.json` only after validation. Both existing outputs are
preflighted; identical writes are no-ops, differing files and symlinks are rejected.
Each file uses the existing immutable atomic publisher. The pair is not a
cross-file transaction: an I/O failure can leave one valid file, and an identical
retry can finish publication without overwriting it.

Capture and publication use temporary data, bulk, working, home and cache paths,
clear inherited configuration and credentials, and restore the calling environment
on exit. The candidate source takes precedence over older editable installations;
preloaded ALPHA modules from another checkout are rejected. The existing CLI relay
keeps its own command-scoped environment policy: it forwards source PYTHONPATH,
temporary working/storage context and permitted runtime variables, but not the
caller's HOME or PYTHONDONTWRITEBYTECODE. This is bounded test composition, not an
OS sandbox or a guarantee of zero library/bytecode writes. No owner `.env` or store
is read, no provider/model is invoked, and no production data is created.

Focused producer tests are in `tests/integration/test_c04_risk_basis_fixture.py`.
Run only that explicit path through the existing owned-test wrapper, with the
candidate packages/apps source roots on PYTHONPATH and disposable home/cache/tmp.
They cover real capture, same-source repeatability, closed provenance, immutable
publication and schema/convention/math/parity rejection. Corrupted fixtures exercise
the semantic validator directly before publication, so a stale output hash cannot
make a missing semantic check appear covered.

The four original source-mounted browser cases still require the existing
`playwright.risk-basis.config.ts` and its Vite harness. **Default browser-suite
routing remains unresolved:** bare Playwright also discovers this spec but starts
the integrated backend, not the dedicated source-harness server. This slice does
not skip tests, change selection, repair that routing, or claim normal-suite/full
gate acceptance. Dedicated browser execution and independent source review are
separate checks on this exact candidate. No cloud browser attempt is included.

## Documentation decisions

README reviewed: no change. The application, setup, dependencies, production
commands and architecture are unchanged; this bounded test-only capture command
and its limitations belong in this dated operational plan. CLAUDE.md and AGENTS.md
remain byte-identical to the 5,985-byte predecessor, below the unchanged 6,000-byte
combined limit. BUILD-STATUS receives an appended scoped record; prior evidence and
historical source plans are preserved, not rewritten.

## Scoped verification

The final producer source passed 31 explicit public cases, including direct
non-vacuous validation negatives, missing/forged fingerprints and foreign-source
rejection. Scoped Ruff check/format and strict mypy on the two new Python files
passed. The standalone command generated the fixture through a fresh actual
HTTP/CLI process; its SHA256 is
`9f0ba5d3d44537f2a919e9cf88afee922492a25eccd4eab293eb1eb3ff7f297e`.
An independently started second capture is byte-compared with both output files
in the delivery receipt. No existing application/runtime component is relabeled
as freshly qualified by these focused tests.
