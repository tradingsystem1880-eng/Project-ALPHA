# Trader Terminal — Phase 1 "Work": crypto data pulling that works

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 1 (Work): make crypto data pulling work end-to-end from the Workstation",
  "context": "Owner walkthrough on 2026-09-01 (docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md #1-#7) showed a trader cannot pull XRP data from the UI: the job card hid the real CLI error behind a Rich box border, free-text dates accepted 2026-06-31, symbol forms like xrp-usdt were passed verbatim to ccxt, a start date before the pair's listing aborted the whole pull with no hint, two unrelated data panels competed for the same task, and XRP is not a reviewed crypto-house asset. Phase 1 of docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md (section 4.3, section 7) fixes exactly that path: plain-text CLI errors surfaced by the web job runner, symbol normalisation and calendar/date-order validation in the CLI, a read-only `alpha data first-bar` projection used both by a pre-listing guard in `data pull` and by an Estimate button, a display-only `profile` setting whose only consumer is data defaults, one Data Manager panel replacing the Market Data and Research Data tabs, and XRP/SOL as reviewed native assets under ADR-0032. No authority, DAG edge, MCP tool, statistic, or point-in-time reader changes.",
  "assumptions": [
    {
      "statement": "Typer 0.26.x renders BadParameter through Rich only when TYPER_USE_RICH is truthy; setting TYPER_USE_RICH=0 in the allowlisted subprocess environment yields plain `Error: ...` lines.",
      "verified_by": "navigator read of .venv/lib/python3.12/site-packages/typer/core.py:26,203-208 and alpha_web/_catalog._cli_environment (allowlist, lines 30-31/60-77) on 2026-09-01; slice W1's env-scoping test pins it."
    },
    {
      "statement": "ccxt `fetch_ohlcv(symbol, '1d', since=0, limit=1)` returns the earliest available daily bar on Binance and Coinbase, so the first-listed date needs no bar history download.",
      "verified_by": "UNVERIFIED until slice W3's @pytest.mark.network live test passes for XRP/USDT (binance) and XRP/USD (coinbase); contingency in the prose if an exchange ignores since=0."
    },
    {
      "statement": "All `alpha data *` commands except repair/rollback-promotion classify as `safe` for the web job launcher, so no launch allowlist changes are needed; the Estimate call is a synchronous `_run_json` projection like /api/symbols, not a job.",
      "verified_by": "navigator read of alpha_cli/catalog.py:31-59 classify_generic_command and alpha_web/api/jobs.py:26-78, api/catalog.py:29-30 on 2026-09-01."
    },
    {
      "statement": "No Phase 1 change touches PointInTimeReader.as_of, _runner.load_bars, snapshots, or strategy reads; pull and first-bar are raw ingestion/metadata, so no new bias_guard test is required and tests/bias_guards is untouched.",
      "verified_by": "test-architect and navigator maps on 2026-09-01; re-checked in slice W8 by grepping the diff for as_of/load_bars."
    },
    {
      "statement": "The builtin reviewed-native asset master is identified by the version string `reviewed-native-v1`, referenced by existing frozen CryptoSnapshotV1 bindings and tests; adding XRP/SOL therefore requires a new `reviewed-native-v2` builtin while v1 remains resolvable, never a silent content change under the v1 id.",
      "verified_by": "navigator grep on 2026-09-01: crypto_data_cmds.py:624-629 stamps reviewed-native-v1; tests/integration/test_research_cli.py:201,280, test_crypto_crowding_snapshot.py:76,132, test_crypto_crowding_composition.py:162, test_hedged_basis_composition.py:163 reference it. Exact v1-compatibility mechanics are confirmed in slice W7 with the invariants-auditor before code."
    },
    {
      "statement": "The current shell keeps six fixed screens in Phase 1; only the side panes of the Research screen change (DataExplorer + ResearchDataExplorer -> DataManager), so .claude/rules/alpha-web.md needs a module-table update but not a shell-model rewrite.",
      "verified_by": "spec section 7 Phase 1 scope; shell/screens.tsx:82-83 and screens.test.ts:68-69 read on 2026-09-01."
    }
  ],
  "alternatives_considered": [
    "Parse the Rich box in _invoke (join the `│` lines) instead of disabling Rich in the subprocess: rejected because it hard-codes Rich's box layout and wrap width; TYPER_USE_RICH=0 removes the box at the source for every subprocess and every error.",
    "Silently clamp a pre-listing start date to the first available bar: rejected (fail-loud rule); the pull must refuse and name the first-listed date so the owner chooses.",
    "Guess the quote asset of compact symbols like XRPUSDT by longest-suffix match over all exchange markets: rejected in favour of a closed quote list (USDT, USD, USDC, BTC, ETH, EUR) that fails loud on anything else, so no silent mis-split.",
    "Add XRP/SOL by editing the reviewed-native-v1 identities in place: rejected because frozen snapshots and tests bind to that id; a v2 builtin keeps v1 byte-compatible (ADR-0032 immutability).",
    "Build the whole Phase 3 Data Manager dock/window now: rejected; Phase 1 ships the panel inside the existing Research-screen side area so the six-screen rule and e2e harness need only a tab rename.",
    "Fix only the date-validation bug as a one-file change without a plan: rejected because Phase 1 spans alpha_data, alpha_cli, alpha_web backend and frontend, and the governed asset master."
  ],
  "pre_mortem": [
    "TYPER_USE_RICH=0 changes error text for every web subprocess and some existing tests assert Rich-box fragments or the generic `alpha process exited N` reason; run the full web test set in W1 and update assertions to the plain message deliberately.",
    "Binance or Coinbase ignores since=0 and returns the most recent bar, making first-bar report a wrong (late) listing date and the pre-listing guard reject valid pulls; the network test asserts first_bar_ts.date() <= 2019-05-01 for XRP/USDT and the guard is ccxt-only and bypassable by exact start-at-first-bar.",
    "The normaliser rewrites an equities symbol with punctuation (BRK.B) or a ccxt pair with an unusual quote (XRP/TRY) into something the vendor rejects; equities are upper-cased only, ccxt compact forms split only on the closed quote list, and anything else fails loud listing accepted forms.",
    "Replacing two side panes breaks the Playwright crypto-data journey (Research Data tab, Crypto Data Center region) and explore-screen screenshot baselines; W6 keeps CryptoDataCenter mounted inside the new panel and re-snapshots deliberately.",
    "Adding a reviewed-native-v2 builtin changes asset-master hashes consumed by frozen snapshots or research bindings; W7 first proves with a test that every v1-stamped fixture still resolves and verifies byte-for-byte, and the invariants-auditor reviews the diff before commit.",
    "The rebuilt static/app bundle plus generated API types exceed the 1000 changed non-docs lines commit guard; W6 commits source and the asset rebuild as separate conventional commits if needed, never with --no-verify.",
    "The Expansion SSD is unmounted during implementation, so the Data Manager's SSD table cannot be exercised live; the model test covers blocker states and the live check is reported honestly as the environment state."
  ],
  "slices": [
    {
      "title": "W1 web job failures carry the real CLI error message",
      "verify": "uv run pytest -q tests/unit/test_web_invoke.py tests/integration/test_web_api_jobs.py tests/integration/test_web_api_catalog.py -m \"not network\" && cd apps/alpha-web/frontend && npx vitest run src/panels/jobProgress.test.ts && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "A failed `data pull` job's current_step, summary reason, and SSE failed payload equal the plain Typer message (e.g. `Invalid value: --start/--end must be YYYY-MM-DD: day is out of range for month`); no box-drawing glyphs; running jobs unchanged; one ANSI stripper shared by _invoke and _catalog.",
      "rollback": "Revert the two alpha_web modules and their tests; no data or contract change.",
      "files": ["apps/alpha-web/src/alpha_web/_invoke.py", "apps/alpha-web/src/alpha_web/_catalog.py", "tests/unit/test_web_invoke.py", "tests/integration/test_web_api_jobs.py", "apps/alpha-web/frontend/src/panels/jobProgress.ts", "apps/alpha-web/frontend/src/panels/jobProgress.test.ts"],
      "status": "pending"
    },
    {
      "title": "W2 CLI symbol normalisation and date-order validation in data pull",
      "verify": "uv run pytest -q tests/unit/test_data_symbol_normalisation.py tests/integration/test_data_cli.py -m \"not network\" && uv run python scripts/gate.py fast",
      "expected": "`xrp-usdt`, `XRPUSDT`, `xrp/usdt` normalise to `XRP/USDT` for ccxt before the adapter is called and stored; equities upper-case only; garbage or unknown quote fails loud listing accepted forms; `--end` before `--start` and impossible calendar dates fail before any adapter call with a message naming the problem.",
      "rollback": "Revert data_cmds.py and the two test files.",
      "files": ["apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_data_symbol_normalisation.py", "tests/integration/test_data_cli.py"],
      "status": "pending"
    },
    {
      "title": "W3 CCXTAdapter.first_bar, alpha data first-bar --json, and the pre-listing guard",
      "verify": "uv run pytest -q tests/unit/test_ccxt_first_bar.py tests/integration/test_data_cli.py -m \"not network\" && uv run pytest -q tests/integration/test_ccxt_live.py -m network -k first_bar && uv run python scripts/gate.py fast",
      "expected": "`alpha data first-bar xrp-usdt --source ccxt --exchange binance --json` prints {symbol, exchange, first_bar_ts, timeframe} without downloading history; unknown pair or empty history fails loud; `data pull` with a start before the first bar exits 2 with `No data before <date> (first listed). Start there?` and writes nothing; a start exactly at the first bar succeeds; non-ccxt sources skip the probe; the live network test confirms Binance and Coinbase honour since=0.",
      "rollback": "Revert ccxt_adapter.py, data_cmds.py and the tests; the store format is untouched.",
      "files": ["packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_ccxt_first_bar.py", "tests/integration/test_data_cli.py", "tests/integration/test_ccxt_live.py"],
      "status": "pending"
    },
    {
      "title": "W4 web first-bar projection route and generated API types",
      "verify": "uv run pytest -q tests/integration/test_web_api_catalog.py -m \"not network\" && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && cd apps/alpha-web/frontend && npm run generate:api && git diff --exit-code src/api/generated && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "`GET /api/data/first-bar?symbol=XRP/USDT&source=ccxt&exchange=binance` relays `alpha data first-bar --json` through _run_json with a strict FirstBar response model; CLI errors map to the existing request_invalid envelope with the plain message; OpenAPI and generated TypeScript are regenerated and clean; alpha_web imports no ccxt.",
      "rollback": "Revert the router, model, client method and regenerated contracts.",
      "files": ["apps/alpha-web/src/alpha_web/api/catalog.py", "apps/alpha-web/src/alpha_web/api/models.py", "apps/alpha-web/src/alpha_web/_catalog.py", "apps/alpha-web/frontend/src/api/client.ts", "apps/alpha-web/frontend/src/api/generated/**", "tests/integration/test_web_api_catalog.py", "docs/openapi/**"],
      "status": "pending"
    },
    {
      "title": "W5 profile setting and the pure Data Manager model",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/state/settings.test.ts src/panels/dataManagerModel.test.ts src/panels/controlPlane.test.ts && npm run lint -- --deny-warnings",
      "expected": "`profile: 'crypto' | 'equities'` persists in alpha.settings (default crypto, garbage falls back), mirrors to html[data-profile], and has a row in the Settings menu; dataManagerModel exports pullDefaults (crypto -> XRP/USDT, ccxt, binance; equities -> AAPL, tiingo), validateDates (impossible dates, non-ISO, end<start named), storageRow (blocker -> `Expansion SSD not mounted`, amber), and listingHint (listed date, bar estimate, retryFrom); buildDataPullArgs refuses invalid dates.",
      "rollback": "Revert settings.ts, App.tsx menu row, the new model and tests.",
      "files": ["apps/alpha-web/frontend/src/state/settings.ts", "apps/alpha-web/frontend/src/state/settings.test.ts", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/panels/dataManagerModel.ts", "apps/alpha-web/frontend/src/panels/dataManagerModel.test.ts", "apps/alpha-web/frontend/src/panels/controlPlane.ts", "apps/alpha-web/frontend/src/panels/controlPlane.test.ts"],
      "status": "pending"
    },
    {
      "title": "W6 one Data Manager panel replaces Market Data and Research Data",
      "verify": "cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "The Research screen side area has one `Data Manager` tab: pull form with native date inputs, symbol combobox (stored pairs + profile starter list), venue select, Estimate (first-bar route) with listing hint, failure text with a one-click `Start there` retry; stored pairs table; Expansion SSD datasets table from coverage/storage with honest not-mounted state; reviewed assets with the CLI recipe (no mutation); the existing CryptoDataCenter mounted inside a second tab so the crypto-data e2e journey passes; screens.test and the Playwright harness renamed from `Research Data` to `Data Manager`; screenshot baselines re-snapshotted deliberately; static/app rebuilt and committed.",
      "rollback": "Restore DataExplorer/ResearchDataExplorer in screens.tsx and the previous static/app; the backend is untouched by this slice.",
      "files": ["apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/DataExplorer.tsx", "apps/alpha-web/frontend/src/panels/ResearchDataExplorer.tsx", "apps/alpha-web/frontend/src/shell/screens.tsx", "apps/alpha-web/frontend/src/shell/screens.test.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "W7 XRP and SOL as reviewed native assets (reviewed-native-v2, v1 kept)",
      "verify": "uv run pytest -q tests/unit/test_crypto_asset_master.py tests/integration/test_crypto_data_cli.py tests/integration/test_web_api_crypto_data.py tests/integration/test_research_cli.py tests/unit/test_crypto_crowding_snapshot.py -m \"not network\" && uv run lint-imports && uv run python scripts/gate.py fast",
      "expected": "with_reviewed_native_assets() gains XRP (coingecko `ripple`) and SOL (coingecko `solana`) under a new `reviewed-native-v2` builtin; every fixture stamped reviewed-native-v1 still resolves and re-verifies byte-for-byte; `alpha crypto-data asset XRP --as-of ... --json` and `GET /api/crypto-data/assets/XRP` resolve (was 422); DOGE still fails with the reviewed-mapping message; the v2 master hash is pinned by a golden; the owner then regenerates the cross-provider asset master with the existing `asset-master-create` and records the receipt in the findings log.",
      "rollback": "Revert asset_master.py, crypto_data_cmds.py and tests; no immutable bytes are rewritten because v1 is never edited.",
      "files": ["packages/alpha-data/src/alpha_data/crypto/asset_master.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_asset_master.py", "tests/integration/test_crypto_data_cli.py", "tests/integration/test_web_api_crypto_data.py", "tests/fixtures/crypto/**"],
      "status": "pending"
    },
    {
      "title": "W8 docs honesty, rule updates, full gate",
      "verify": "uv run python scripts/gate.py full && uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py -m \"not network\" && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md",
      "expected": ".claude/rules/alpha-cli.md (pull normalisation, first-bar), alpha-data.md (ccxt first_bar), alpha-web.md (DataManager, JobMonitor failure text) updated under gate.py ack; docs/BUILD-STATUS.md gains a dated Phase 1 record; the spec marks Phase 1 done; findings #1-#7 statuses updated with the fixing commit; this plan's slices marked done; full gate green including the 14-wheel smoke.",
      "rollback": "Docs-only; revert the doc commit.",
      "files": [".claude/rules/alpha-cli.md", ".claude/rules/alpha-data.md", ".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md", "docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["protected", "dag", "determinism"],
  "docs_to_update": [
    "docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md",
    "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md",
    "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md",
    ".claude/rules/alpha-cli.md",
    ".claude/rules/alpha-data.md",
    ".claude/rules/alpha-web.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "Phase 2 (report tree, figure fullscreen, governance window, run display names) and Phase 3 (terminal_classic.json theme, menu/toolbar/status anatomy, docks, MDI documents, Equities profile gating)",
    "Removing the five catalog-derived contract identities from the existing cross-provider asset master (separate ADR-0032 decision)",
    "Merging the legacy snapshot path and the crypto house into one data path",
    "New providers, dependencies, MCP tools, REST routes beyond the single first-bar projection, or any Touch ID / authority change",
    "Paper, broker, live-capital, or alert functionality",
    "Kronos/ML/Qlib surfaces"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/data_cmds.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py",
    "packages/alpha-data/src/alpha_data/crypto/asset_master.py",
    "apps/alpha-web/**",
    "tests/unit/**",
    "tests/integration/**",
    "tests/fixtures/**",
    "docs/**",
    ".claude/rules/alpha-cli.md",
    ".claude/rules/alpha-data.md",
    ".claude/rules/alpha-web.md"
  ]
}
```

## Context

Spec: `docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md` §4.3 (Data Manager) and §7
Phase 1. Evidence: `docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md` #1–#7 and the
2026-09-01 reproduction (`data pull xrp-usd … --end 2026-06-31` → hidden error; valid dates →
`ccxt returned no data for XRP/USD 2015-01-01…`; `--start 2023-08-01` → 1,065 bars).

Maps (navigator, test-architect, 2026-09-01):

* `alpha_cli/data_cmds.py:132-187` — `pull`; symbol passed verbatim to `adapter.fetch` (:157);
  dates parsed :153-155; `DataError → BadParameter` :186-187; `--json` pattern :194-204/:329-359.
* `alpha_data/adapters/ccxt_adapter.py:160-202` — `fetch_timeframe`; "no data" raise :200-201;
  pagination :22-52; no `load_markets`/first-bar helper today.
* `alpha_web/_invoke.py:88-95,127-134,136-179,459-462,498-502`; `_catalog.py:60-82`
  (`_cli_environment` allowlist, `_strip_ansi`); Typer Rich switch `typer/core.py:26,203-208`.
* `alpha_web/api/jobs.py:26-78` launch; `alpha_cli/catalog.py:31-59` classifier (`data *` safe).
* Frontend: `panels/controlPlane.ts:9-47`, `DataExplorer.tsx:20-24,58-65,122-135`,
  `ResearchDataExplorer.tsx:14,45-46,103-107` (mounts `CryptoDataCenter`), `state/settings.ts:10-52`,
  `App.tsx:47-115`, `shell/screens.tsx:82-83,97`, `screens.test.ts:68-69`,
  `researchDataModel.ts:161-180` (blocker → canonical action).
* Crypto house: `asset_master.py:173-207,277,284`; `crypto_data_cmds.py:196 (_NATIVE_NETWORKS),
  624-629 (reviewed-native-v1 stamp), 963-1017 (storage blocker), 1158, 3689-3739
  (asset-master-create: plain CLI + REST, not Touch ID)`.
* Blast radius: `tests/integration/test_data_cli.py:52-148`, `test_web_api_jobs.py:258-272`,
  `tests/unit/test_web_invoke.py:47,89`, `test_crypto_asset_master.py:84-87,130`,
  `test_crypto_data_cli.py:173-189,317`, `test_web_api_crypto_data.py:689`;
  e2e `workstationHarness.ts:2582-2604,2347-2376,2733-2769`; rules `alpha-cli.md:16,21-22`,
  `alpha-web.md:37,39`.

## Slices

Order W1 → W8 as in the block; each slice is red → green → `/gate fast` → one conventional
commit (`fix(web):`, `feat(cli):`, `feat(data):`, `feat(web):`, `feat(frontend):`, `feat(crypto):`,
`docs:`). W3's contingency if an exchange ignores `since=0`: read Binance `markets[symbol]["info"]
["onboardDate"]` where present and otherwise fail loud with "first-listed date unavailable for
<exchange>" — never guess. W7 starts with a red test that every `reviewed-native-v1` fixture still
resolves, and dispatches `invariants-auditor` on the diff before commit.

## Test plan

Test-architect specification (2026-09-01), 31 tests; the numbers below are its items:

* W1 → #1–#4 (`test_web_api_jobs.py`, `jobProgress.test.ts`) plus `test_web_invoke.py:47` env
  scoping gains `TYPER_USE_RICH`.
* W2 → #5–#11 (`tests/unit/test_data_symbol_normalisation.py` new; `test_data_cli.py` extend).
* W3 → #12–#19 (`tests/unit/test_ccxt_first_bar.py` new with a fake `ccxt` module as in
  `test_crypto_ccxt_timeframe.py:13-29`; `test_data_cli.py`; `test_ccxt_live.py` network).
* W4 → route test beside `test_web_api_catalog.py:39`; OpenAPI/TS generation checks.
* W5 → #20–#24 (`controlPlane.test.ts`, `settings.test.ts`, `dataManagerModel.test.ts` new).
* W6 → #25 (`screens.test.ts`), #30–#31 (Playwright: rename tab, new failed-job-row assertion,
  `expectReleaseAccessibility`, re-snapshot `explore-screen.png`).
* W7 → #26–#29 (`test_crypto_asset_master.py`, `test_crypto_data_cli.py`,
  `test_web_api_crypto_data.py`) plus a v1-compatibility test across the fixtures listed in
  assumption 5.
* Markers: `network` only on the live first-bar test; **no `bias_guard`** (no PIT reader changes;
  re-checked in W8).

## DAG / look-ahead / determinism impact

* **DAG:** `alpha_data.adapters.ccxt_adapter` gains a method (core-only import unchanged);
  `alpha_cli.data_cmds` composes it; `alpha_web` only subprocesses `alpha data first-bar --json`
  and imports no ccxt — `uv run lint-imports` in W7/W8 proves the 15 contracts hold.
* **Look-ahead:** none. `pull`/`first-bar` are raw ingestion/metadata, never `as_of` reads;
  `candles` (bias-guarded) is untouched.
* **Determinism:** the only hashed artefact touched is the builtin reviewed-native asset master;
  v1 bytes/ids are never edited, v2 is a new builtin with a golden hash. Run ids, snapshots,
  manifests, seeds unchanged.
* **Protected:** three `.claude/rules/*.md` edits in W8, each with `gate.py ack --reason`.
* **MCP:** stays 62 (no tool added).
