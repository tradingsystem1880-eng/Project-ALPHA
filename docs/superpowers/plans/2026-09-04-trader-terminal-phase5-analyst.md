**Delivery state:** In progress (2026-09-04; S1–S6 on `feat/trader-terminal-phase5-analyst`).

# Trader Terminal — Phase 5 "Analyst": everything doable in the UI, live desk, chart-first analysis, rule strategies, scanner + alerts

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 5 (Analyst): everything doable in the UI, live desk for whatever the AI does, chart-first indicators/patterns, rule-based strategy builder + tester, stored-universe scanner + alerts",
  "context": "The owner (2026-09-04) uses the web terminal as the main surface and the AI CLI/MCP only as a chat helper that does backend work; the UI must therefore let the owner perform every action not forbidden by an ADR and must display everything the AI does. They also asked for TrendSpider-like capability (chart-first analysis, a no-code strategy builder + tester, a scanner with alerts) while keeping the approved artboard chrome (AskUserQuestion 2026-09-04). Four navigator maps established: (1) the SPA renders nothing for ownerStep kind 'review' so an exploration/confirmation contract cannot be approved or rejected from the cockpit; ~30 routed actions (evidence draft/review, stage links, attempts, holdout seal, experiment decisions, ML prepare/train/import/evaluate/replay, development jobs) are never called by the SPA; CLI/MCP jobs never appear in the Toolbox because _invoke.JOBS is per-process and _activity.py only diffs the run store; menu items for crypto-data/quantpad-data/provider/strategy-candidate always 422 because classify_generic_command returns unknown; four of five Toolbox tabs have no panel. (2) alpha_patterns already holds bias-guarded SMA/EMA/RSI/Bollinger/ATR/MACD, swings, trendlines, wedges, H&S, order blocks, fib levels but no app consumer (import-linter forbids alpha_web/alpha_mcp; alpha_cli has no contract yet); the bar store is daily-only so M15/H1/H4/W1 stay honestly disabled; Lightweight Charts 5.2 supports panes. (3) No generic rule strategy exists; strategies are hard-coded classes + STRATEGY_PARAM_SCHEMA; strategy_versions.definition_json already stores a JSON definition; run identity hashes RunSpec + strategy_fingerprint. (4) alpha_screener is finnhub-only and contract-forbidden from alpha_data/alpha_patterns; no scheduler exists in the web process; the only tick is the launchd paper scheduler; saved-scan JSON fits the data_dir/web slug-JSON pattern while an alert log is operational state and must be CLI-written.",
  "assumptions": [
    {
      "statement": "No import-linter contract forbids alpha_cli -> alpha_patterns today (only alpha_mcp/alpha_web are forbidden), so chart/scan commands may import alpha_patterns lazily without a pyproject change; the DAG line in CLAUDE.md and .claude/rules/alpha-patterns.md are updated to say alpha_cli is its first consumer.",
      "verified_by": "invariants-auditor finding (pyproject.toml:258/264 only); uv run lint-imports; tests/unit/test_public_seams.py AST guard that only chart_cmds/scan_cmds import alpha_patterns"
    },
    {
      "statement": "Dropping the alpha_strategies -> alpha_patterns forbidden contract is DAG-valid (patterns -> core only, so core <- patterns <- strategies has no cycle); rules.py then reuses the bias-guarded alpha_patterns primitives instead of duplicating them, and alpha_patterns joins _identity._EXECUTION_PACKAGES so its bytes enter the execution fingerprint.",
      "verified_by": "invariants-auditor finding; gate.py ack for the pyproject/CLAUDE.md edits; uv run lint-imports; tests/unit/test_run_identity_rules.py"
    },
    {
      "statement": "A rule spec's canonical bytes hashed into the run identity payload and the strategy fingerprint make two runs with different rule files never share a run_id, and byte-identical specs (20 vs 20.0) hash identically.",
      "verified_by": "tests/unit/test_run_identity_rules.py"
    },
    {
      "statement": "Overlay and scan reads are point-in-time: every series value at bar t depends only on bars <= t, pattern anchors carry ts <= as_of, and swings use confirmed_index.",
      "verified_by": "future-poison bias guards with must-fail leaky twins under tests/unit (marker bias_guard)"
    },
    {
      "statement": "The web layer stays a relay: overlays, rules, scans and alerts are alpha ... --json subprocesses; the SPA computes no indicator or condition and the mtime-based store_changed events read no SQLite and no run-dir bytes.",
      "verified_by": "uv run lint-imports (15 contracts) + tests/integration/test_web_api_overlays.py / test_web_api_scans.py with monkeypatched relays"
    },
    {
      "statement": "Touch-ID-receipted web dispatch of research pause/resume/cancel is consistent with ADR-0030 once the three CLI verbs accept --actor (today pause hard-codes actor codex, resume/cancel owner) and OWNER_ACTION_TYPES gains the three names; project override-research-gate stays CLI-only (ADR-0030 line 14 grants no override path) and is rendered as CopyCommand; paper run/stop/reconcile stay CLI-only per ADR-0017/0031.",
      "verified_by": "invariants-auditor finding; tests/unit/test_web_owner_action_argv.py; tests/unit/test_web_owner_actions_drift.py"
    }
  ],
  "alternatives_considered": [
    "Compute indicators in the browser from the candles the SPA already has (rejected: CLAUDE.md forbids SPA analytics; values would not be PIT-provenanced or reusable by the scanner and rule strategies).",
    "Move alpha_patterns primitives into alpha_core so alpha_strategies can import them instead of re-implementing five functions (rejected for this phase: touches the quant tier and every alpha_patterns consumer; a parity test pins the duplicate instead).",
    "A daemon in the web process evaluating alerts on a timer (rejected: no scheduler may live in alpha_web; scan check is a generic job triggered after each data pull and on demand).",
    "A TrendSpider-style dark chrome rewrite (rejected by the owner: keep the artboards, add capabilities).",
    "Widening classify_generic_command so every CLI command launches from the menu (rejected: owner_only roots stay 422; menu items with a typed document open that document instead)."
  ],
  "pre_mortem": [
    "A rule spec drifts out of run identity (loaded after the payload is hashed) and two different strategies share a run_id -> identity test asserts the hash changes with the spec bytes.",
    "Overlay series leak: rolling windows centred or pattern pivots confirmed with future bars -> future-poison guards on every overlay id and on swings/trendlines anchors.",
    "The mtime scanner hammers the disk or emits an event storm when a pull rewrites parquet -> coalesced per poll tick, one event per area, clamp_poll unchanged.",
    "Toolbox Alerts implies real-time monitoring the system does not have -> the tab states 'checked after each pull / on demand; last check <ts>' and never claims live.",
    "The commit guard (1000 non-docs lines) or the review gate blocks a slice -> every slice is split into <1000-line commits; _runner/_identity edits are one small commit with /review-gate APPROVE.",
    "Lightweight Charts panes re-create on every control change and lose zoom -> pane series are keyed and the effect deps are split (overlays vs controls).",
    "Playwright baselines churn for every document because the chart gains a legend -> legend hidden in the harness until overlays are chosen; baselines re-taken once at the end of S3.",
    "alpha_cli importing alpha_patterns pulls numpy into the polars-free catalog seam used by the web -> chart_cmds imports lazily inside the command body.",
    "Overlay, scanner and backtest disagree on an EMA/RSI value because recursions are seeded on different history -> every operand declares a fixed trailing history K, evaluate_rules slices exactly K bars and restarts recursions there, and all three consumers call the same evaluate_rules (parity test scan-hit(d) == backtest-signal(d)).",
    "A cross operator silently never fires against NaN warmup -> evaluate_rules raises DataError when any operand is non-finite at the decision bar; the scanner reports insufficient_history, never no-hit.",
    "Pattern anchors dated <= as_of are still unknowable (fractal pivots confirm lookback bars later) -> overlays emit only swings_known_by / fib_levels_at / trendlines with active_from <= last bar and carry known_at_ts.",
    "The overlay cache serves one indicator set for another -> the cache key includes a hash of the canonical overlay argv beside the parquet mtime.",
    "A historical scan reads as edge evidence -> scan output carries authority: none and universe_as_of (survivorship flag) and is never admissible as research evidence."
  ],
  "slices": [
    {
      "title": "S1 live desk: store_changed SSE areas, per-area versions and refetch hooks, real Toolbox panels (Backtests, Data pulls, Log, Trades)",
      "verify": "uv run pytest -q tests/unit/test_web_activity_areas.py tests/integration/test_web_api_activity.py; cd apps/alpha-web/frontend && npx vitest run && npx playwright test --project=chromium-minimum",
      "expected": "a touched research project dir, control sqlite, bars parquet, paper journal or alerts log yields one store_changed event per area per tick; panels refetch on their area; all five Toolbox tabs render real rows",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-web/src/alpha_web/_activity.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/frontend/src/state/activity.ts",
        "apps/alpha-web/frontend/src/shell/Toolbox.tsx",
        "apps/alpha-web/frontend/src/shell/documents.ts",
        "apps/alpha-web/frontend/src/panels/JobMonitor.tsx",
        "apps/alpha-web/frontend/src/panels/jobTableModel.ts",
        "apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx",
        "apps/alpha-web/frontend/src/panels/ResearchBacklog.tsx",
        "apps/alpha-web/frontend/src/panels/V3Workbenches.tsx",
        "apps/alpha-web/frontend/src/panels/CodexBench.tsx",
        "apps/alpha-web/frontend/src/panels/MarketWatch.tsx",
        "apps/alpha-web/frontend/src/panels/Navigator.tsx",
        "apps/alpha-web/frontend/src/panels/DataManager.tsx",
        "apps/alpha-web/frontend/src/panels/PaperMonitor.tsx",
        "tests/unit/test_web_activity_areas.py",
        "tests/integration/test_web_api_activity.py"
      ],
      "status": "in_progress"
    },
    {
      "title": "S2 owner completes everything: approve/reject buttons, pause/resume/cancel owner actions (CLI verbs gain --actor; OWNER_ACTION_TYPES extended), evidence + development + ML + data + sources + notes affordances over existing or thin new routes, precise classification of the crypto-data/quantpad-data/provider/strategy-candidate roots, menu items open documents, sandbox test from the Lab, CopyCommand for ADR-bound CLI steps incl. override-research-gate",
      "verify": "uv run pytest -q tests/unit/test_web_owner_actions_drift.py tests/unit/test_cli_catalog_classification.py tests/integration/test_web_api_owner_auth.py tests/integration/test_web_api_data.py tests/integration/test_web_api_research.py && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py; frontend vitest + chromium-minimum e2e",
      "expected": "every action in the inventory table is DOABLE, VIEW-ONLY by nature, or CLI-ONLY with a CopyCommand citing its ADR; no menu item 422s",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-web/src/alpha_web/api/owner_auth.py",
        "apps/alpha-web/src/alpha_web/api/catalog.py",
        "apps/alpha-web/src/alpha_web/api/research.py",
        "apps/alpha-web/src/alpha_web/_catalog.py",
        "apps/alpha-web/src/alpha_web/_research.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-cli/src/alpha_cli/catalog.py",
        "apps/alpha-web/frontend/src/api/client.ts",
        "apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx",
        "apps/alpha-web/frontend/src/panels/researchCockpitModel.ts",
        "apps/alpha-web/frontend/src/panels/V3Workbenches.tsx",
        "apps/alpha-web/frontend/src/panels/MlDiagnostics.tsx",
        "apps/alpha-web/frontend/src/panels/DataManager.tsx",
        "apps/alpha-web/frontend/src/panels/EvidenceHub.tsx",
        "apps/alpha-web/frontend/src/panels/CodexBench.tsx",
        "apps/alpha-web/frontend/src/panels/PaperMonitor.tsx",
        "apps/alpha-web/frontend/src/panels/StrategyLab.tsx",
        "apps/alpha-web/frontend/src/shell/MenuBar.tsx",
        "apps/alpha-web/frontend/src/shell/menuModel.ts",
        "tests/unit/test_cli_catalog_classification.py",
        "tests/integration/test_web_api_owner_auth.py",
        "apps/alpha-cli/src/alpha_cli/research_cmds.py",
        "apps/alpha-cli/src/alpha_cli/control_store.py",
        "tests/unit/test_web_owner_action_argv.py",
        "tests/unit/test_generic_command_catalog.py"
      ],
      "status": "pending"
    },
    {
      "title": "S3 chart-first analysis: alpha chart overlays --json over alpha_patterns (lazy import; no contract change), GET /api/candles/{symbol}/overlays (argv-hashed cache), known-by pattern anchors, indicator/pattern overlays with panes and legend, Insert > Indicators dialog, tiled chart windows",
      "verify": "uv run lint-imports && uv run pytest -q tests/unit/test_chart_overlays.py tests/unit/test_chart_overlays_bias_guard.py -m 'not network' && uv run pytest -q -m bias_guard tests/unit/test_chart_overlays_bias_guard.py tests/integration/test_cli_chart_overlays.py tests/integration/test_web_api_overlays.py; frontend vitest + e2e",
      "expected": "overlays for BTC/USDT with sma:20, ema:50, bbands:20:2, rsi:14, macd, swings, trendlines, levels are PIT (poison after as_of changes nothing), warmup nulls only at the head, drawn on the price pane or own panes with a legend naming params and the as_of date",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-cli/src/alpha_cli/chart_cmds.py",
        "apps/alpha-cli/src/alpha_cli/main.py",
        "apps/alpha-web/src/alpha_web/_candles.py",
        "apps/alpha-web/src/alpha_web/api/candles.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/frontend/src/panels/chartOverlaysModel.ts",
        "apps/alpha-web/frontend/src/components/PriceChartCanvas.tsx",
        "apps/alpha-web/frontend/src/panels/PriceChart.tsx",
        "apps/alpha-web/frontend/src/shell/menuModel.ts",
        "apps/alpha-web/frontend/src/shell/mdiModel.ts",
        "apps/alpha-web/frontend/src/shell/DocumentArea.tsx",
        "apps/alpha-web/frontend/src/state/settings.ts",
        "tests/unit/test_chart_overlays.py",
        "tests/unit/test_chart_overlays_bias_guard.py",
        "tests/integration/test_cli_chart_overlays.py",
        "tests/integration/test_web_api_overlays.py",
        "tests/unit/test_public_seams.py"
      ],
      "status": "pending"
    },
    {
      "title": "S4 rule strategies: drop the alpha_strategies->alpha_patterns forbidden contract (ack), alpha_strategies/rules.py (strict RuleSpec, canonical bytes, evaluate_rules over a fixed trailing history K reusing alpha_patterns, RuleStrategy) with future-poison guards, registry entry + --rules flag + rules_spec_sha256 in RunSpec/identity payload/strategy fingerprint + alpha_patterns in _EXECUTION_PACKAGES, alpha rules save|list|show|validate, GET/POST /api/rules, Strategy Builder document",
      "verify": "uv run pytest -q tests/unit/test_rules_spec.py tests/unit/test_rules_indicators_parity.py tests/unit/test_run_identity_rules.py tests/integration/test_cli_rules.py tests/integration/test_web_api_rules.py && uv run pytest -q -m bias_guard tests/unit/test_rules_bias_guard.py; /review-gate APPROVE for _runner.py/_identity.py; frontend vitest + e2e",
      "expected": "a saved rule spec backtests through alpha backtest run --strategy rules --rules <id> with the spec in the manifest and the run_id changing with the spec bytes; the builder round-trips rows <-> JSON and launches sandbox or governed runs whose report opens",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-strategies/src/alpha_strategies/rules.py",
        "packages/alpha-strategies/src/alpha_strategies/__init__.py",
        "apps/alpha-cli/src/alpha_cli/_strategies.py",
        "apps/alpha-cli/src/alpha_cli/_schemas.py",
        "apps/alpha-cli/src/alpha_cli/_runner.py",
        "apps/alpha-cli/src/alpha_cli/_identity.py",
        "apps/alpha-cli/src/alpha_cli/backtest_cmds.py",
        "apps/alpha-cli/src/alpha_cli/validate_cmds.py",
        "apps/alpha-cli/src/alpha_cli/rules_cmds.py",
        "apps/alpha-cli/src/alpha_cli/main.py",
        "apps/alpha-web/src/alpha_web/_rules.py",
        "apps/alpha-web/src/alpha_web/api/rules.py",
        "apps/alpha-web/src/alpha_web/app.py",
        "apps/alpha-web/frontend/src/panels/ruleBuilderModel.ts",
        "apps/alpha-web/frontend/src/panels/StrategyBuilder.tsx",
        "apps/alpha-web/frontend/src/shell/documents.ts",
        "apps/alpha-web/frontend/src/shell/profiles.ts",
        "tests/unit/test_rules_spec.py",
        "tests/unit/test_rules_indicators_parity.py",
        "tests/unit/test_rules_bias_guard.py",
        "tests/unit/test_run_identity_rules.py",
        "tests/integration/test_cli_rules.py",
        "tests/integration/test_web_api_rules.py",
        "pyproject.toml"
      ],
      "status": "pending"
    },
    {
      "title": "S5 scanner + alerts: alpha scan run|save|list|delete|check|alerts (classified safe; authority none; universe_as_of) over PIT reads and evaluate_rules, /api/scans + /api/alerts relays, Scanner document, Toolbox Alerts tab, scan check after each pull",
      "verify": "uv run pytest -q tests/unit/test_scan_engine.py tests/integration/test_cli_scan.py tests/integration/test_web_api_scans.py && uv run pytest -q -m bias_guard tests/unit/test_scan_bias_guard.py; frontend vitest + e2e",
      "expected": "a saved scan lists matching stored symbols with the matched bar date and values; scan check appends deduped alerts that the Toolbox shows with the last-check timestamp; the same scan run twice yields the same rows",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-cli/src/alpha_cli/scan_cmds.py",
        "apps/alpha-cli/src/alpha_cli/main.py",
        "apps/alpha-web/src/alpha_web/_scans.py",
        "apps/alpha-web/src/alpha_web/api/scans.py",
        "apps/alpha-web/src/alpha_web/app.py",
        "apps/alpha-web/src/alpha_web/_activity.py",
        "apps/alpha-web/frontend/src/panels/scannerModel.ts",
        "apps/alpha-web/frontend/src/panels/Scanner.tsx",
        "apps/alpha-web/frontend/src/panels/Alerts.tsx",
        "apps/alpha-web/frontend/src/shell/Toolbox.tsx",
        "apps/alpha-web/frontend/src/shell/documents.ts",
        "apps/alpha-web/frontend/src/panels/DataManager.tsx",
        "tests/unit/test_scan_engine.py",
        "tests/unit/test_scan_bias_guard.py",
        "tests/integration/test_cli_scan.py",
        "tests/integration/test_web_api_scans.py"
      ],
      "status": "pending"
    },
    {
      "title": "S6 prove and ship: full gates, real-backend acceptance (both profiles, overlays, builder sandbox run to report, scan + alert), rule rows via ack, spec addendum, BUILD-STATUS, CLAUDE.md MCP/DAG lines if the contract changes, PR, CI, merge",
      "verify": "uv run python scripts/gate.py full; cd apps/alpha-web/frontend && npm run test:e2e; node acceptance script exit 0; gh pr checks green",
      "expected": "everything in the inventory is doable or honestly CLI-only, the AI's work appears live, and the chart/builder/scanner work against the real store",
      "rollback": "revert the merge commit",
      "files": [
        ".claude/rules/alpha-web.md",
        ".claude/rules/alpha-cli.md",
        ".claude/rules/alpha-strategies.md",
        ".claude/rules/alpha-patterns.md",
        "CLAUDE.md",
        "docs/BUILD-STATUS.md",
        "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md"
      ],
      "status": "pending"
    }
  ],
  "tier_impact": [
    "risk",
    "protected",
    "dag",
    "bias",
    "determinism"
  ],
  "docs_to_update": [
    ".claude/rules/alpha-web.md",
    ".claude/rules/alpha-cli.md",
    ".claude/rules/alpha-strategies.md",
    ".claude/rules/alpha-patterns.md",
    "CLAUDE.md (DAG line for alpha_cli -> alpha_patterns; 'Where do I add X' rule strategies)",
    "docs/BUILD-STATUS.md",
    "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md (Phase 5 addendum)",
    "docs/governance/capability-authority-matrix.md (generated)"
  ],
  "out_of_scope": [
    "Intraday timeframes (the bar store is daily-only; M15/H1/H4/W1 stay disabled with the reason)",
    "Paper run/stop/reconcile, data repair/rollback, holdout reveal, owner-auth recovery, asset-master creation from the browser (CLI-only by ADR-0014/0017/0030/0031/0032; CopyCommand instead)",
    "A background daemon or push/email notifier (ADR-0011 evidence-gated provider; alerts are checked after pulls and on demand)",
    "New statistics or validation gates",
    "Any MCP tool change (pinned at 62)",
    "Dark TrendSpider-style chrome",
    "Drawing tools persisted as data authority (chart drawings are UI state only if added later)"
  ],
  "files": []
}
```

## Context

See the JSON block. Owner decisions (AskUserQuestion 2026-09-04): chart-first analysis, no-code strategy builder + tester, scanner + alerts; keep the artboard chrome. The four navigator maps (UI coverage inventory; chart/indicator seams; strategy-spec seams; scanner/alert seams) are summarised in the context field; the inventory's per-command table drives S2 and is reproduced in the S6 docs commit as the acceptance checklist.

## Slices

Each slice: failing tests → minimal code → vitest/oxlint/tsc/build → chromium-minimum e2e → fast gate → full gate → commits ≤ 1000 non-docs lines (unstage in a separate command) → push. Risk-tier edits (S4 `_runner.py`, `_identity.py`) are one small commit with `/review-gate` APPROVE bound to the tree. Protected edits (`pyproject.toml` import-linter contract in S3, rule files in S6) go through `gate.py ack --path` + the Edit tool.

## Test plan

The test-architect specification (2026-09-04, 50 tests) is the ordered list the slices implement; the invariants-auditor's thirteen findings are folded into the pre-mortem and slice titles above; bias guards use the future-poison + leaky-twin idiom and live under `tests/unit/` with the `bias_guard` marker.

## DAG / look-ahead / determinism impact

- DAG: no contract forbids `alpha_cli → alpha_patterns` (alpha_web/alpha_mcp stay forbidden); S4 drops the `alpha_strategies → alpha_patterns` forbidden contract (patterns → core only, no cycle) and adds `alpha_patterns` to the execution fingerprint packages. All web additions are subprocess relays.
- Look-ahead: overlays and scans read through `_runner.load_bars(as_of)`; series values at t use bars ≤ t; pattern anchors ts ≤ as_of; swings use `confirmed_index`.
- Determinism: rule spec canonical bytes enter `RunSpec`, the identity payload and the strategy fingerprint; manifests record the spec verbatim; no new seeds.
