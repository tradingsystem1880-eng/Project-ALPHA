**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Reject invalid recorded-equity clocks before risk metrics",
  "context": "Bounded RR05/EX05 consumer correction: raw parquet row order is not evidence of a chronological return path. Enforce established UTC and strictly increasing producer contract before risk scenario computation. Combined successor integrates preserved d8338bd0 disclosure/live acceptance with46971c39 clock validation using actual local bytes; neither original is modified.",
  "assumptions": [
    {
      "statement": "Existing read_equity returns row order unchecked; risk derives path metrics from that order",
      "verified_by": "_artifacts.py:1111-1124; risk_cmds.py:39-43; pre-change public CLI red receipt7failed2passed"
    },
    {
      "statement": "Canonical mirror v3 RR05 and EX05 apply; full canonicalv9 acceptance is not established",
      "verified_by": "docs/context/feature-readiness-checklist-2026-10-27.md:705,747; mirror header"
    },
    {
      "statement": "Producer contract already writes UTC strictly increasing rows; ragged increasing UTC rows remain valid",
      "verified_by": "_artifacts.py:355-378; CLAUDE fail-on-disordered invariant; navigator read-only audit"
    }
  ],
  "alternatives_considered": [
    "Do not sort or repair immutable recorded observations silently",
    "Do not modify shared artifact reader, native code, frontend or stored schemas",
    "No new metric, return observation, initial wealth assumption or annualization rule"
  ],
  "pre_mortem": [
    "UTC object identity rejects equivalent timezone objects: compare actual offset instead",
    "Path metrics computed before validation: regression must use real CLI/parquet path",
    "Irregular clocks mistaken for invalid cadence: keep increasing ragged path accepted",
    "Disclosure predecessor accidentally altered: separate main-based worktree with only three owned files"
  ],
  "slices": [
    {
      "title": "Public CLI defect discriminator and known path values",
      "verify": "Focused public test file before correction",
      "expected": "Invalid clock cases fail; existing known UTC level paths pass",
      "rollback": "Remove new test file",
      "files": [
        "tests/integration/test_risk_equity_clocks.py"
      ],
      "status": "done"
    },
    {
      "title": "Enforce clock precondition before computing returns",
      "verify": "Focused public CLI regressions plus existing risk CLI and web risk API compatibility; scoped ruff/mypy and independent review",
      "expected": "Fixed BadParameter for malformed clocks; legacy good outputs unchanged",
      "rollback": "Revert risk_cmds guard and remove this test and plan",
      "files": [
        "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
        "tests/integration/test_risk_equity_clocks.py",
        "docs/work/2026-11-08-risk-equity-clocks/02-plan.md"
      ],
      "status": "done"
    },
    {
      "title": "Compose actual preserved source and verify combined behavior",
      "verify": "Five focused public Python files; RiskMetricBasis SSR; risk-basis Chromium4cases; isolated SPA build/live risk6cases; scopedlint/types; independent actualdiff advisoryreview",
      "expected": "Clock rejection before returns with/without opt-in; legacy/numerical/model/render contracts intact; originals preserved",
      "rollback": "Discard combined worktree; both original stagedtrees preserved",
      "files": [
        "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
        "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.json",
        "apps/alpha-web/frontend/e2e/risk-live.spec.ts",
        "apps/alpha-web/frontend/e2e/risk-metric-basis.html",
        "apps/alpha-web/frontend/e2e/risk-metric-basis.spec.ts",
        "apps/alpha-web/frontend/e2e/riskMetricBasisHarness.tsx",
        "apps/alpha-web/frontend/openapi.json",
        "apps/alpha-web/frontend/playwright.risk-basis.config.ts",
        "apps/alpha-web/frontend/playwright.risk-live.config.ts",
        "apps/alpha-web/frontend/src/api/client.ts",
        "apps/alpha-web/frontend/src/api/generated.ts",
        "apps/alpha-web/frontend/src/panels/RiskMetricBasis.test.ts",
        "apps/alpha-web/frontend/src/panels/RiskMetricBasis.tsx",
        "apps/alpha-web/frontend/src/panels/RiskMonitor.tsx",
        "apps/alpha-web/frontend/src/panels/rundetail/Risk.tsx",
        "apps/alpha-web/src/alpha_web/_risk.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/src/alpha_web/api/risk.py",
        "docs/work/2026-11-08-c04-risk-anchor-disclosure/02-plan.md",
        "docs/work/2026-11-08-risk-equity-clocks/02-plan.md",
        "scripts/run_c04_risk_live_acceptance.py",
        "tests/integration/test_c04_risk_anchor_disclosure.py",
        "tests/integration/test_c04_web_metric_basis.py",
        "tests/integration/test_risk_equity_clocks.py"
      ],
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/work/2026-11-08-risk-equity-clocks/02-plan.md"
  ],
  "out_of_scope": [
    "Metric formulas/defaults, calendar annualization inference, baseline/flows provenance and statistical or promotion authority",
    "Shared artifact reader, other consumers, native paths, frontend/shell/models/generated assets and BUILD-STATUS",
    "Protected tests/oracles/holdouts, realdata/studies/fits/provider/model calls, installs/full qualification, commit/publication/transfer/live trading"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
    "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.json",
    "apps/alpha-web/frontend/e2e/risk-live.spec.ts",
    "apps/alpha-web/frontend/e2e/risk-metric-basis.html",
    "apps/alpha-web/frontend/e2e/risk-metric-basis.spec.ts",
    "apps/alpha-web/frontend/e2e/riskMetricBasisHarness.tsx",
    "apps/alpha-web/frontend/openapi.json",
    "apps/alpha-web/frontend/playwright.risk-basis.config.ts",
    "apps/alpha-web/frontend/playwright.risk-live.config.ts",
    "apps/alpha-web/frontend/src/api/client.ts",
    "apps/alpha-web/frontend/src/api/generated.ts",
    "apps/alpha-web/frontend/src/panels/RiskMetricBasis.test.ts",
    "apps/alpha-web/frontend/src/panels/RiskMetricBasis.tsx",
    "apps/alpha-web/frontend/src/panels/RiskMonitor.tsx",
    "apps/alpha-web/frontend/src/panels/rundetail/Risk.tsx",
    "apps/alpha-web/src/alpha_web/_risk.py",
    "apps/alpha-web/src/alpha_web/api/models.py",
    "apps/alpha-web/src/alpha_web/api/risk.py",
    "docs/work/2026-11-08-c04-risk-anchor-disclosure/02-plan.md",
    "docs/work/2026-11-08-risk-equity-clocks/02-plan.md",
    "scripts/run_c04_risk_live_acceptance.py",
    "tests/integration/test_c04_risk_anchor_disclosure.py",
    "tests/integration/test_c04_web_metric_basis.py",
    "tests/integration/test_risk_equity_clocks.py"
  ]
}
```

**Delivery state:** Completed — bounded production input correction and focused public engineering checks only; formal qualification remains separate.

Baseline: main snapshot3f7b23185c29b2542605bd41b9485016c2ef3e79, separate codex/risk-equity-clocks-20261108 worktree. Preserved d8338bd0 and predecessors remain unchanged and are not prerequisites for this independent correction. Parent serializes any plan landing; this local plan does not supersede other owners in their worktrees.

The risk consumer must reject duplicate/disordered clocks and null/date/string/naive/nonzero-offset timestamps before to_returns. It must not silently sort. Zero-offset equivalent timezone objects are accepted. Known values [100,95,100] imply a -5% maximum drawdown and zero total return; the same pairs shuffled must not be reported as a different strategy path. Irregular increasing UTC timestamps remain accepted; periods_per_year stays explicitly caller-selected/default252 and is not inferred from elapsed time. No legitimate initial wealth is inferred from these test fixtures.

README review: no change; this enforces an existing invalid-input contract without a new command or setup requirement. Shared README/manual/BUILD-STATUS remain untouched by owner scope. Formal/full acceptance and broader consumer protection are not established.


## Results and limits

The12-line production guard runs inside the existing DataError-to-BadParameter boundary before to_returns. It checks datetime type and zero UTC offset, then strict increase. It does not sort or rewrite artifacts, infer sampling frequency, verify cash-flow/capital provenance or alter metric definitions/defaults. The global shared reader is deliberately unchanged, so other consumers are not claimed protected. Existing risk API forwards the real CLI rejection through its existing422 error contract without any backend edits.

The initial public discriminator run returned7failed/2passed before the guard: disordered, duplicate, null, naive, date, string and human-output rejection cases failed; known ordered/flat cases passed. Final focused run returned18passed:12new cases plus3existing CLI and3existing web-risk compatibility cases. New cases include nonzero-offset clocks and real API-to-CLI accepted/rejected paths. These are synthetic fixtures with direct level-path arithmetic expectations, not statistical calibration or protected oracle execution.

First compatibility attempt returned14passed/2failed because alpha was absent from PATH. The rerun explicitly selected the existing virtualenv executable and this worktree's complete source roots via PYTHONPATH; it returned16passed before the final2HTTP regressions were added. Both failed and final receipts are preserved under /workspace/scratch/risk-equity-clocks-20261108. No dependency install occurred. Ruff check/format and production-source mypy pass. Broader mypy including the test's main-app import reports an unrelated imported-module error: apps/alpha-cli/src/alpha_cli/_crypto_acquisition.py:20: Module alpha_data.crypto.providers.bybit has no attribute parse_funding_page. No change to that owned path was attempted and no all-types pass is claimed.

Independent Codex advisory review is requested on the exact staged tree and retained outside source in the receipt directory. It is not a formal review-gate attestation. No protected tests, full/component gate, scientific qualification, actual fit/study, market/provider data, commit, publication, transfer or live action was performed. Formal integration and any broader verification remain parent-owned. The canonical source available here is the localv3 mirror; fullv9 parity and complete RR05/EX05 acceptance are not claimed.


## Combined successor — 2026-11-08

Separate branch codex/c04-combined-20261108 at main snapshot3f7b23185c29b2542605bd41b9485016c2ef3e79 first reproduced d8338bd02ec28b5d4ac57eb057a7d11f91cfce2c exactly from Git objects. Actual test/plan bytes and the clock guard came from46971c395c94e6f305fa9ac97dc9ca5157d5285c. The conflict was confined to composing imports in risk_cmds.py: retain typing.Annotated and add datetime/timedelta and pairwise. Both original worktrees/trees remain unchanged; there is no unavailable-source reconstruction.

Combined coverage explicitly exercises ordered ragged acceptance and every malformed clock with and without the CLI disclosure flag, plus genuine HTTP-to-CLI negotiation. A public test replaces only to_returns with a tripwire and proves no call occurs on invalid clocks in either flag mode. Actual CLI/HTTP numerical tests and all disclosure/model tests ran fresh:55passed. RiskMetricBasis rendered8cases; source-mounted browser cases4passed (including malformed cached metadata and stale-run/loading); actual compiled-SPA/live-backend browser cases6passed, including a new disordered-clock synthetic run returning422 under the production opt-in client. The live response is not mocked. Legacy fallback still uses deliberate outgoing request downgrade and genuine backend response. Fixed current producer cannot naturally emit malformed disclosure fields; those remain scoped to model and source-mounted consumer checks, not relabeled live acceptance.

Fresh TypeScript noEmit and isolated Vite build succeeded. Build output /workspace/scratch/c04-combined-20261108/spa contains only disposable assets; the canonical normalizer/shared static/app/freshness and full gates remain unrun. Existing Bokeh eval and chunk-size warnings remain. Scoped Ruff/format and frontend lint passed. Mypy including the server helper traversed unrelated CLI imports and failed at _crypto_acquisition.py:20 because alpha_data.crypto.providers.bybit has no attribute parse_funding_page. The standalone production-risk-source check is recorded separately; no combined/all-types pass or unrelated Bybit repair is claimed.

Actual logs, build/byte manifests, candidate patch and exact-tree independent Codex advisory review are retained under /workspace/scratch/c04-combined-20261108 and the separate review receipt directory. Review must examine the real combined source diff; original review passes are historical only. This source composition includes only locally available science source, not reserved native/inspector/other-owner candidates. Shared source/generated assets, BUILD-STATUS and README remain untouched. README no-change rationale remains valid for this invalid-input contract and private acceptance-only setup. No formal/full, scientific, real-data or combined-platform qualification is claimed.
