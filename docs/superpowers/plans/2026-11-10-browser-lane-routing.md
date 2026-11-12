```json
{
  "schema_version": 1,
  "title": "Route mandatory browser tests to their existing fixtures",
  "context": "Bare default Playwright discovery imported source-harness, synthetic risk-live and descriptor-owned native specs under the wrong server. Pair exactly three exclusions with mandatory positive routes; preserve all original browser assertions and configuration policies.",
  "assumptions": [
    {
      "statement": "The three handoffs already have dedicated configs and the native fixture has an authoritative public driver.",
      "verified_by": "Source assessment of frozen b38 candidate; byte-preservation checks for all original specs and dedicated configs/drivers."
    },
    {
      "statement": "Native source/runtime inputs are explicit installed assets, not optional test coverage.",
      "verified_by": "Original NativeWebJourney skip guard and StockFixtureLaunch source/runtime validator."
    }
  ],
  "alternatives_considered": [
    "Config-only exclusions rejected because they omit mandatory coverage.",
    "Fixed existing-config dispatcher chosen over projects/dependency redesign or a new registry/count framework."
  ],
  "pre_mortem": [
    "Exit zero can hide a skipped native class: require fresh exact one-case JUnit with no skipped/error/failure.",
    "A nonempty partial Playwright run can look successful: compare fresh original-config listing identities with actual reports, retaining project multiplicity.",
    "Raw risk-live assets can be altered by normal production normalization: build directly to its separate fresh spa directory."
  ],
  "slices": [
    {
      "title": "Implement explicit routing and negative contracts",
      "verify": "Only the new public routing tests and exact original frontend command-contract test through run_owned_test.py; scoped Ruff/mypy and package/config syntax.",
      "expected": "Mandatory positive routes, honest failures, fresh separate evidence and unchanged original browser contracts. Stub successes prove orchestration only.",
      "rollback": "Remove this distinct successor; frozen predecessor remains untouched.",
      "files": [
        "apps/alpha-web/frontend/package.json",
        "apps/alpha-web/frontend/playwright.config.ts",
        "scripts/run_frontend_browser_lanes.py",
        "tests/unit/test_frontend_browser_lanes.py",
        "tests/unit/test_gate_components.py"
      ],
      "status": "done"
    },
    {
      "title": "Bind scoped evidence and document remaining acceptance",
      "verify": "Read README/manual, validate plan schema, freeze manifest/patch/index; independent source review before delivery.",
      "expected": "5,994-byte manual under unchanged 6,000-byte limit, preserved 149 omitted bodies, exact changed-path set and explicit unrun full gates.",
      "rollback": "Discard successor documentation only; never overwrite historical records.",
      "files": [
        "CLAUDE.md",
        "README.md",
        "apps/alpha-web/frontend/README.md",
        "docs/BUILD-STATUS.md",
        "docs/operations/development-loop.md",
        "docs/superpowers/plans/2026-11-10-browser-lane-routing.md"
      ],
      "status": "done"
    }
  ],
  "tier_impact": ["none"],
  "docs_to_update": [
    "CLAUDE.md",
    "README.md",
    "apps/alpha-web/frontend/README.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/development-loop.md",
    "docs/superpowers/plans/2026-11-10-browser-lane-routing.md"
  ],
  "out_of_scope": [
    "Production behavior, numerical/scientific acceptance, original browser assertions/selectors/timing/retries/workers",
    "Protected gate/CI code, protected or historical-result bodies, full/default/native execution, Atlas/preflight",
    "New installs, model/provider calls, owner data, credentials, publication, commits, history repair"
  ],
  "files": [
    "CLAUDE.md",
    "README.md",
    "apps/alpha-web/frontend/README.md",
    "apps/alpha-web/frontend/package.json",
    "apps/alpha-web/frontend/playwright.config.ts",
    "docs/BUILD-STATUS.md",
    "docs/operations/development-loop.md",
    "docs/superpowers/plans/2026-11-10-browser-lane-routing.md",
    "scripts/run_frontend_browser_lanes.py",
    "tests/unit/test_frontend_browser_lanes.py",
    "tests/unit/test_gate_components.py"
  ]
}
```

**Delivery state:** Bounded implementation and focused checks only. Independent exact-source review and all full/default/native browser acceptance remain pending; this is not project completion.

## Contract and scope

This is a distinct, uncommitted successor of frozen tree
`b38bda23a9db0ecdc6b7c5fc55889bc4e69b7901`, not a modification of that candidate.
Canonical HEAD remains `3f7b23185c29b2542605bd41b9485016c2ef3e79`.
Missing Git history/objects are not repaired or represented as complete.
The curated materialization preserves 77 protected and 72 historical-result entries
as metadata only. Their bodies are neither read nor materialized. No gate/CI
control-plane code is changed, and no acceptance waiver is introduced. Application
DAG, point-in-time/look-ahead and numerical determinism contracts are untouched.

The default config excludes only `risk-metric-basis.spec.ts`, `risk-live.spec.ts`
and `native-result-real.spec.ts`. In the same candidate, the existing mandatory npm
built command invokes a fixed stdlib adapter. Its normal default lane retains the
four projects, ordinary/reference filtering, dependency order, worker/retry/timing
settings and opt-in performance policy. Self-owned retained and investigation
selector suites remain there. Every original browser spec and all three dedicated
configs, risk server and native driver remain byte-identical.

The adapter runs default → source-mounted risk basis → raw-Vite synthetic risk live
→ exact existing native pytest driver. The normal production build remains a
prerequisite. Risk-live additionally builds into its own fresh `spa` directly with
Vite; no normalizer or copied normal bundle is used. The original native driver
creates the actual synthetic fixture descriptor, pinned upstream execution and
browser owner. No descriptor or receipt is invented or borrowed from history.

## Prerequisites and evidence

Installed Node, Playwright, Vite, Chromium, controller Python dependencies, uv and
ALPHA CLI are required. Linux retained-child supervision is mandatory. Nonempty
`ALPHA_RDAGENT_SOURCE` and `ALPHA_STOCK_PYTHON` must select already-authorized native
assets; the latter retains the lexical `runtime/venv/bin/python` path because the
existing driver derives its runtime from `parents[2]`. Its lock and pyvenv config
must be present. The original `StockFixtureLaunch` validator measures the pins
before any lane; the adapter does not reproduce its cryptographic policy. Checks
of file/module/browser-binary presence are not runtime qualification. Native's
fresh HOME receives the same explicit installed browser cache.

Each run allocates a new external temporary evidence root. Existing process owners
supervise child commands. Config-resolved Playwright listings are retained separately
before execution, without starting servers or browsers. Execution reports must
return the same `(projectName, spec.id, file)` set, with every original configured
project retained. Dedicated memberships must be exact and disjoint from default.
Listings are not browser passes. Existing optional skips/retries are preserved;
no fixed count manifest is introduced. Any child, selection or report error stops
the sequence, preserves outputs and records completed versus unrun lanes.
Native requires exactly one fresh JUnit testcase matching the original driver node,
with zero skipped/error/failure entries; exit zero alone cannot pass the aggregate.
Native output is a newly allocated child, never an inherited evidence path.

The installed frontend dependencies and controller used for scoped checks are reused
read-only. Candidate source is placed before older editable imports, with private
home/cache/tmp directories. No dependency resolution/install or remote operation is
performed. The npm launcher passes `--offline --no-python-downloads --no-sync`
to uv before Python starts, and children inherit equivalent uv controls. The 4-case risk-basis browser pass belongs to the independent predecessor
run; unchanged bytes may establish narrow applicability but do not establish this
successor's complete browser sequence. Prior risk-live/retained reports similarly
remain historical scoped evidence, not newly executed aggregate acceptance.

## Verification and limitations

Public unit tests use subprocess stubs to verify routing, independent paths,
prerequisite negatives, explicit selector propagation, source binding, raw build,
selection equality, report errors, unsupported arguments, child statuses and honest
aggregation. They prove orchestration contracts, not actual browser/native success.
Exact check logs, failed attempts, final diff and identities are retained outside
source in this successor's evidence directory. The repository's independent review
and full qualification requirements remain unchanged. No full/default/native browser
execution, protected tests, Atlas, preflight, model/provider activity, owner data,
GPU work, installs, commits or publication are claimed.

Native selectors were absent in this cloud checkout; no verified current installed
native assets were found in the narrow authorized project receipt lookup. This is
not a statement about every computer. Hosted frontend CI currently provisions
root/frontend/Chromium dependencies but must also supply native source/runtime
inputs. The command intentionally remains blocked rather than claiming coverage
through a skipped driver.

Generic Claude design advice informed the explicit lane/fail-loud approach. It was
not exact-source review or runtime verification. The independent local reviewer
reviews the exact frozen source separately. No further private project disclosure
was performed.

## Documentation review

Root README and frontend README now disclose native prerequisites and mandatory
lane behavior. Development-loop guidance replaces the obsolete filtered npm example
with the existing focused evidence workflow and documents raw risk builds and
retained fresh outputs. CLAUDE.md changes only “build before browsers” to “build
before all browser lanes”; combined AGENTS + CLAUDE size is 5,994/6,000 bytes.
BUILD-STATUS is appended, never rewritten. Production/science/authority claims and
the original gate ordering are unchanged.

The self-owned retained browser fixtures keep their original interpreter selection:
`ALPHA_TEST_PYTHON` when set, otherwise the candidate's `.venv/bin/python`. The
adapter checks executable presence without replacing that selector. This and the
other prerequisite diagnostics are not exhaustive runtime qualification; actual
fixture/browser execution is still required.
