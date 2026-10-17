# Finish outstanding work and establish a documented clean baseline

```json
{
  "schema_version": 1,
  "title": "Finish outstanding work and establish a documented clean baseline",
  "context": "Owner requests repo-wide cleanup, completion and integration of outstanding work, resolution of recent failures, and accurate documentation. Initial root HEAD 454c940f is reconciled main. Chart and weekly mutation changes are uncommitted in separate worktrees. Owner expanded cleanup to every worktree, branch, stash and GitHub PR. History audit found completed CASH affordability fix 73fb2a94 absent from main; port that bounded bugfix without enabling unfinished research features.",
  "assumptions": [
    {
      "statement": "Finish and integrate both outstanding workstreams through green CI, preserve behavior for hygiene changes.",
      "verified_by": "Owner selected both defaults in planning and requested implementation."
    },
    {
      "statement": "Main branch protection requires seven contexts; regular main CI passed, nightly mutation sweep was cancelled after six hours.",
      "verified_by": "GitHub branch protection and run 37611439271 job details read 2026-10-08."
    }
  ],
  "alternatives_considered": [
    "Major package restructuring rejected in favor of behavior-preserving hygiene; retaining outstanding changes indefinitely rejected by owner."
  ],
  "pre_mortem": [
    "Parallel writers invalidate receipts; freeze each worktree and review its exact tree before committing.",
    "Missing hidden holdout suite prevents full acceptance; never infer a new exception from an old plan.",
    "Generated assets conflict during integration; regenerate from merged sources rather than hand-merge."
  ],
  "slices": [
    {
      "title": "Validate and finish weekly mutation workflow",
      "verify": "uv run pytest -q tests/unit/test_mutation_report.py; uv run python scripts/gate.py full",
      "expected": "Assigned module report validation and all six components pass; independent approval; green PR CI",
      "rollback": "Revert workflow commit",
      "status": "in_progress"
    },
    {
      "title": "Finish technical charts and preserve PNG display layers",
      "verify": "npm run test:e2e; uv run python scripts/gate.py full",
      "expected": "Header, UTC labels and legends retained in downloads; functional browsers pass; timing limitations recorded",
      "rollback": "Revert chart commit",
      "status": "in_progress"
    },
    {
      "title": "Repair dependency boundary and current documentation",
      "verify": "uv run pytest -q tests/unit/test_research_boundary.py; uv run lint-imports; uv run python scripts/gate.py full",
      "expected": "Core-only research boundary enforced; current docs agree with source",
      "rollback": "Revert cleanup commit",
      "status": "in_progress"
    },
    {
      "title": "Recover the completed CASH fee-affordability fix from the undelivered lineage",
      "verify": "uv run pytest tests/integration/test_order_rejection.py tests/bias_guards/test_cash_fee_affordability_future_poison.py -q; uv run python scripts/gate.py full",
      "expected": "Unaffordable CASH buys reject before execution with typed evidence; close-time decisions and MARGIN behavior preserved; current-tree independent approval",
      "rollback": "Restore pre-port source from the verified combined patch archive",
      "status": "in_progress"
    },
    {
      "title": "Cull offscreen volume painting without changing native observations",
      "verify": "npx vitest run src/components/technical/technicalModel.test.ts; ALPHA_PERF_BUDGETS=1 npx playwright test e2e/scientific-performance.spec.ts --project=chromium-reference-only --no-deps; uv run python scripts/gate.py full",
      "expected": "Every volume rectangle intersecting the viewport is drawn with its original index/value/colors; pan and fit restore exact admitted bars; screenshots/export preserved; unchanged timing budgets measured",
      "rollback": "Remove only the volume CDSView/filter and visible-index helper/tests",
      "status": "in_progress"
    },
    {
      "title": "Translate malformed PIT bars into typed data errors",
      "verify": "uv run pytest tests/unit/test_pit_source.py tests/bias_guards/test_source_future_poison.py tests/holdout_seed/test_holdout_benchmark_defects.py -q; uv run python scripts/gate.py full",
      "expected": "Invalid visible bars fail with symbol/timestamp/reason and chained cause; future invalid bars stay excluded; CLI exits 2 without publishing a run; independent review",
      "rollback": "Revert only the typed validation translation and its regressions",
      "status": "in_progress"
    },
    {
      "title": "Remove repeated full-source volume color parsing",
      "verify": "npx vitest run src/components/technical/technicalModel.test.ts; npx playwright test e2e/technical-chart.spec.ts; ALPHA_PERF_BUDGETS=1 ALPHA_SCIENTIFIC_PROFILE=1 npx playwright test e2e/scientific-performance.spec.ts --project=chromium-reference-only --no-deps; uv run python scripts/gate.py full",
      "expected": "Complementary native up/down viewport subsets preserve every bar and its original scalar colors; profile eliminates volume CSS color-array parsing; thresholds unchanged; fresh final aggregate and independent review",
      "rollback": "Restore single per-row-color volume renderer and its exact mask",
      "status": "in_progress"
    },
    {
      "title": "Integrate and verify final main and scheduled checks",
      "verify": "gh pr checks; uv run python scripts/gate.py full; gh run view",
      "expected": "Combined exact tree passes and main aligns remote; revised schedules have reports; every leftover documented",
      "rollback": "Revert individual delivered commits",
      "status": "pending"
    }
  ],
  "tier_impact": [
    "protected",
    "dag"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/BUILD-STATUS.md",
    "docs/superpowers/plans/2026-10-05-clean-reconcile-main.md"
  ],
  "out_of_scope": [
    "New features and major reorganizations",
    "Owner data, secrets, immutable research evidence and hidden-test contents",
    "Mutation baseline changes and weakened timing/screenshot thresholds"
  ]
}
```

**Delivery state:** In progress (2026-10-08).

## Initial work inventory (before expanded cleanup)

| Item | Disposition |
|---|---|
| Root checkout, initially `ci/nightly-mutation-shards` at `454c940f` | Initially clean; hygiene branch `chore/repo-hygiene-2026-10-08` |
| `ci/nightly-shards` worktree | Weekly workflow, rules, plan and Atlas changes; stale stamp; finishing |
| `feat/technical-chart-language` worktree | Chart implementation and baselines; initial valid stamp; PNG regression being fixed |
| `integrate/main-2026-10-05` | Clean historical reconciliation branch; PR #53 merged |
| `claude/trader-github-integration-c307d1` | Clean historical integration worktree; retained |
| `worktree-research-triple-tap-inverse-hs` | Clean earlier research checkout; retained |
| Two existing stashes | Preserved; prior cleanup inventory remains authoritative |
| PR #52, draft cloud environment setup | Separate unfinished work; retain without integrating in this cleanup |

## Verification constraints

The hidden `tests/holdout/` directory is absent (existence checked only). Owner restoration requested; no new exception assumed. Provider/live-data readiness and full archive byte integrity are outside this engineering cleanup.

## Historical branch inventory

At the initial inventory, clean ancestor branches (integration, crypto-terminal, trader integration and research worktree) were retained. Six historical research/benchmark branches contain commit ancestry not represented verbatim on main: `feat/agentic-benchmark`, `feat/codex-research-runtime`, `feat/research-investigation-demo`, `feat/research-investigation-efficiency`, `feat/research-judgment-cases`, and `feat/research-teammate`. Their patches required comparison before integration; no branch was deleted or assumed disposable at that checkpoint. The expanded disposition below supersedes this initial inventory and retains the unique source lineage.

## Failure resolution evidence

- CI run [37459522391](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/37459522391) on `6c9c811b` failed Chart/Builder screenshot comparisons at about 3%. Platform-specific baselines landed in `c0d703ca`; subsequent integration CI [37608670168](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/37608670168) and main CI [37611319452](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/37611319452) passed. Tolerance remains 2%.
- Nightly [37611439271](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/37611439271) on `454c940f` passed semgrep, determinism and raise-site coverage, then cancelled its mutation step at six hours. Weekly per-module scheduling remains prepared until merged and run.
- Independent weekly-report review reproduced empty/wrong-module/unknown-status acceptance; eighteen validator cases now pass.
- The research dependency regression failed on the omitted `alpha_patterns` prohibition, then passed after correction.
- Chart export review identified dropped DOM annotations. Focused downloaded-PNG verification now passes; earlier full receipt predates this fix.

## Verification interruption

The first workflow full gate passed backend and frontend unit/API checks but was interrupted by the session permission-mode transition before the browser step completed. It did not produce aggregate acceptance. Its log was retained at `/tmp/alpha-cleanup-weekly-full-interrupted.log` and then archived. A subsequent unchanged-tree canonical run passed all six components on the prior weekly tree; this is not final-tree acceptance.

## Combined candidate (2026-10-08)

The initial `integrate/cleanup-2026-10-08` candidate in `.claude/worktrees/cleanup-integration` preserved the three workstreams together. Documentation conflicts retained all appended records; Atlas and SPA artifacts were regenerated from combined source. That prior combined tree passed all six available canonical components; chart independent review remained BLOCK because hidden tests were absent. The candidate was subsequently archived and consolidated into the primary checkout as recorded below. No merge or protected commit bypass is authorized.

## Manual size regression

The first hygiene full gate passed 5,245 tests with 93.20% coverage but failed `test_core_is_small`: combined CLAUDE.md/AGENTS.md size was 6,041 bytes against the existing 6,000-byte limit. The redundant dependency sentence was removed and the core-only wording compacted; no test or budget was weakened. A focused rerun verifies the correction; final combined full verification remains required.

## Expanded branch, stash and GitHub cleanup checkpoint

The owner expanded this cleanup on 2026-10-08 to the entire repository and GitHub inventory. Three clean ancestor worktrees (`infallible-kalam-2f15ea`, `integrate-main`, `research-triple-tap-inverse-hs`) were retired after byte-verifying archives of their ignored local state. Five merged local branches and three merged GitHub branches were retired. The existing off-site `backup/local-main-2026-09-28` branch is deliberately retained.

The six research/benchmark checkpoint branches were not delivered by PR #53. All thirteen unique commits remain reachable from `backlog/research-runtime` at `b18cf921`; each original tip remains in `refs/archive/cleanup-2026-10-08/heads/`. This includes the completed CASH execution fix `73fb2a94`, which is being recovered separately from the unfinished research feature program.

Both stashes were superseded: Phase C panel code/tests landed at `b1b7510e` and were subsequently hardened; the old SVG wrapping/assertion changes target files removed by SPA delivery `cf831bf7`. Their full snapshots, including untracked stash parents, remain in archive refs and the verified history bundle before their stash entries were removed.

Draft PR #52 was closed without merging its obsolete hook architecture or dependency fallbacks. Its exact source is preserved on GitHub at tag `archive/2026-10-08/cloud-environment-setup`; its old head branch was retired. Any later cloud setup must preserve locked dependencies, pinned browser identity and failure status against the current harness.

Recovery records, binary patches, full Git history and byte-verified local-state archives are private under the primary checkout's `.alpha/state/cleanup-archive/2026-10-08/`. No owner data, credentials, immutable research evidence or hidden-test source was changed. The previous combined tree `1472220c` passed all six canonical components and had a valid full stamp; additional bugfix/docs changes require a new aggregate run. Hidden-suite acceptance remains BLOCK.

## Primary-checkout consolidation and current acceptance state

The primary checkout is now the only registered worktree, on `integrate/cleanup-2026-10-08`. All original changed source/workflow paths matched the combined candidate byte-for-byte before retirement; the transferred staged tree matched Git index tree `930f38e64aca7d4d2f45810a41b523c95d395f68` exactly. All six auxiliary worktrees are retired. Three additional redundant preparation branches were removed, leaving only `main`, the active integration branch and the undelivered `backlog/research-runtime`. GitHub has no open PRs; its backup branch and the cloud source archive tag are retained.

The recovered CASH bugfix first reproduced seven failures and five passes, including engine truncation when commission exceeded free cash. The source port, typed CLI rejection sidecar and a deliberate leaky comparator control now pass 41 focused tests with one pre-existing expected failure. The two absent research-digest files were excluded because they belong to the undelivered feature program. No fee guard, test budget, mutation floor or hidden-suite requirement was weakened.

All consolidated changes remain staged. A fresh canonical full gate and independent risk review are required on this final primary tree. The real `tests/holdout/` suite is still absent, so final independent acceptance and commit/merge remain blocked. Optional timing failures in the technical-chart record and acceptance of the deployed weekly mutation schedule remain unresolved; the workflow has not been deployed. Current local receipts and recovery manifest are under `.alpha/state/`; they are deliberately private rather than committed owner/environment evidence.

## Timing investigation and unregistered worktree discovery

On an isolated local browser run, the unchanged optional four-panel timing limit failed at p99 42.8 ms (34 ms budget); a diagnostic profiled run measured 50.5 ms. Installed Bokeh's VBar/LRTB implementation does not spatially mask volume glyphs and paints all 25,000 rows despite a roughly 100-bar initial window. The bounded correction is an exact intersecting-index CDSView, retaining the full native source and including partial edge bars; no aggregation, sparse price-line filtering or timing-threshold change is permitted. Fresh screenshots, linked range/cursor behavior, PNG export, timing and aggregate verification remain required.

A directory named `agent-af82ecdbdecd4dbbd` remained under `.claude/worktrees/` with a `.git` pointer to missing metadata. It is not a registered worktree or a valid repository. Its noncache source snapshot must be archived and byte-verified before retirement; it is not assumed merged.

## Exact-volume mask verification checkpoint

The four new model regressions failed before the helper existed, then all 23 technical-model tests passed after the width-0.8 intersection mask was implemented. Bokeh uses the same index subset for geometry and color vectors, retaining the full native source. All seven focused technical browser tests passed, including unchanged Classic/Default snapshots, UTC cursor/zoom/all-data fit, gap marks and actual PNG download. Type checks, lint and build passed.

The first post-correction isolated timing run passed at p99 28.5 ms. Three single-worker repeats measured 26.3, 26.2 and 43.0 ms: two passed, one still failed the unchanged 34 ms limit. Thus offscreen workload is corrected, but intermittent timing acceptance remains unresolved and is not claimed complete. The benchmark remains opt-in under the existing reference-machine policy; its failures are retained separately from the canonical functional gate.

The unregistered orphan source folder was retired only after its 181 noncache files were archived and byte-verified. Its archive is retained without claiming those partial files were merged. The obsolete `workflow-delivery/completion` tracking ref had no configured remote; its unique tip is retained under an archive ref and both recovery bundles. The auxiliary worktree directory is now empty.

## Final primary gate and P09 follow-on (2026-10-09)

The consolidated primary tree `88c9ead8` passed all six canonical components, including the full browser suite; `gate.py check --tier full` confirmed the stamp. Independent acceptance remains BLOCK because the genuine hidden suite is absent. This functional pass does not clear the separately recorded intermittent timing failure.

The remaining public P09 seed regression is an error-translation gap: `PointInTimeSource.as_of` leaks Pydantic `ValidationError` from invalid visible bars, while the CLI handles only `DataError`. Add failing-first nonfinite/invariant cases, future-poison/leaky/in-window controls, and a stronger CLI seed regression; translate only bar construction errors after PIT filtering. No row dropping, coercion, statistical formula, price or cutoff changes. Source/rule/build-record changes and regenerated Atlas precede fresh aggregate verification.

The P09 failing-first run produced 20 failures and seven passes; after the bounded translation, all 27 focused tests pass. The CLI includes the bad row date and invariant reason, exits 2, and creates no runs directory. Nonfinite OHLCV, negative prices/volume and inconsistent OHLC retain chained validation causes. New-tree aggregate verification and independent review remain required.

## Remaining volume color materialization hotspot

Post-mask CPU profiling attributed roughly 165.5 ms directly to `_from_css_array` and another 90 ms to its parser over 855 ms of samples. Bokeh materializes full-source CSS color columns before applying viewport subsets. Keep the exact mask and split volume into complementary up/down views with scalar style colors over the same full x/volume source; preserve previous-close classification (including unchanged closes), partial edge bars, width, scales, cursor and exports. Add failing-first partition tests, unchanged screenshot/export verification and a diagnostic profile before evaluating unchanged performance limits. The in-flight P09 aggregate was intentionally stopped after its backend and frontend unit/API steps passed so final verification can cover this further measured correction; no aggregate pass is claimed for the interrupted run.


**2026-10-09 — Exact volume color views (unmerged).** Post-mask profiling exposed full-source CSS color materialization on every view update. Complementary up/down views now share the full native x/volume source with scalar style colors, retaining previous-close classification, equal-close bars, partial viewport intersections, width, scales, cursor and exports. Three failing-first partition tests are covered by 26 passing model tests; seven focused browser tests pass with unchanged screenshots and PNG export. The new profile recorded zero `_from_css_array` samples, versus about 165.5 ms directly before the change. Profiled/ordinary p99 passed at 27.2/27.3 ms; a fixed three-repeat run passed at 27.2/27.3/27.2 ms against the unchanged 34 ms limit. This evidence improves the previously intermittent timing lane without promising every future machine/run will pass. Fresh final aggregate and independent acceptance remain required; hidden-suite execution stays UNVERIFIED/BLOCK. [Cleanup plan](2026-10-08-repository-hygiene.md).

## Standing private engineering availability correction (2026-10-09)

The prior final candidate `f7d6ae8c` passed all six canonical components with a valid full stamp. Its independent BLOCK was caused solely by an unconditional private-suite requirement despite original manual owner provisioning and absence in this checkout. The owner then requested root-cause repair and recurrence prevention. The standing contract repair (`2026-10-09-engineering-holdout-policy.md`) aligns full/CI/review: absent coverage is UNVERIFIED without a synthetic pass; any provisioned suite must explicitly pass, including nonempty collection. Public regressions and all source/authority boundaries remain. Historical unavailable receipts are preserved. The changed candidate requires fresh aggregate verification and independent review; no commit, merge or production/provider readiness is inferred.

**Reference availability (2026-10-16):** At inspected base
`9d9d6a57083231e39bd7fca84adc8b0aad8a82c2`, the named target was unavailable in the
tracked tree and accompanying worktree. Only public path metadata was checked.
The dated claim above is preserved as history; the unavailable contents were not
opened, recovered or verified and supply no current policy authority. Consult the
current [operating manual](../../../CLAUDE.md) and [commit guard](../../../scripts/git_guard.py)
for current requirements.
