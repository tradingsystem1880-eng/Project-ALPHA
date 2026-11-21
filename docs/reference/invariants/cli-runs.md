---
owner: command line runs and validation
sources:
  - apps/alpha-cli/src/alpha_cli/_artifacts.py
  - apps/alpha-cli/src/alpha_cli/artifact_contract.py
  - apps/alpha-cli/src/alpha_cli/_identity.py
  - apps/alpha-cli/src/alpha_cli/_seeds.py
  - apps/alpha-cli/src/alpha_cli/_runner.py
  - apps/alpha-cli/src/alpha_cli/_gauntlet.py
  - apps/alpha-cli/src/alpha_cli/_optim.py
  - apps/alpha-cli/src/alpha_cli/_mcpt.py
  - apps/alpha-cli/src/alpha_cli/_synth.py
  - apps/alpha-cli/src/alpha_cli/_surrogate.py
  - apps/alpha-cli/src/alpha_cli/run_*.py
  - apps/alpha-cli/src/alpha_cli/*suite*.py
  - apps/alpha-cli/src/alpha_cli/figure*.py
  - apps/alpha-cli/src/alpha_cli/figures/*.py
  - apps/alpha-cli/src/alpha_cli/rules_cmds.py
  - apps/alpha-cli/src/alpha_cli/scan_cmds.py
  - apps/alpha-cli/src/alpha_cli/chart_cmds.py
  - apps/alpha-cli/src/alpha_cli/validate_cmds.py
  - apps/alpha-cli/src/alpha_cli/setup_cmds.py
  - apps/alpha-cli/src/alpha_cli/test_cmds.py
  - apps/alpha-cli/src/alpha_cli/results_cmds.py
  - apps/alpha-cli/src/alpha_cli/*lookalike*.py
  - apps/alpha-cli/src/alpha_cli/spine/**
  - tests/unit/test_spine_spec.py
  - tests/smoke/test_rule_*_smoke.py
  - tests/unit/test_run*.py
  - tests/unit/test_gauntlet*.py
  - tests/unit/test_suite_*.py
  - tests/unit/test_figure*.py
  - tests/integration/test_validate_*.py
  - tests/integration/test_backtest_*.py
verified: 437c8c8604ecf113
---

# Command line runs invariants
Run composition and publication follow [immutable artifacts](research-integrity.md#immutable-hash-bound-artefacts)
and [deterministic identity](research-integrity.md#deterministic-seeds-and-identity).
## Composition
- `alpha_cli` is the only layer that composes the engine with the gauntlet; engine imports stay lazy.
  [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md), [engineering § Import layers](engineering.md#import-layers)
- Strategies use `_runner.load_bars` with `as_of` ([timeframes](data-bar-timeframes.md#reading-intraday-bars)); decide at close, fill next open.
  [Point-in-time reads](research-integrity.md#point-in-time-reads); [fills](research-integrity.md#decide-at-close-fill-at-next-open).
- `_gauntlet.py`, `_optim.py`, `_runner.py`, `_synth.py`, `_surrogate.py`, `_seeds.py` and `_identity.py` are high-risk statistical or identity code; follow
  [engineering § Quant tier](engineering.md#quant-tier). They sit outside `gate.py::matches_quant` (packages only), so CI runs no mutation gate on them: their
  tests and the oracles are the binding check; ask the `reviewer` agent to review the diff (advisory, ADR-0039; stage 04 of the delivery pipeline).
- `_schemas.py` is the one canonical home of strategy parameter definitions, bounds and defaults; `_strategies.py` and `_runner.parse_strategy_params` read
  from it, and values are normalised to the stable floats stored in `RunSpec`.
- Slash symbols (`BTC/USD`) are crypto pairs and need `--account-type MARGIN`; a CASH account fails loud (`_runner.py`).
## Run identity
- A run id is a deterministic 16-hex digest of the canonical payload plus identity version 3, the execution fingerprint, the strategy fingerprint and the
  verified snapshot hash (`_runner.run_identity_for`, `_identity.py`). No wall-clock value may enter it.
  [ADR-0013](../../adr/0013-run-identity-v3-and-causal-artifacts.md)
- The execution fingerprint hashes every `.py` file in `alpha_core`, `alpha_data`, `alpha_backtest`, `alpha_strategies`, `alpha_patterns`, `alpha_validation`,
  `alpha_forecast` and `alpha_cli`. Any byte edit there, including this CLI, gives new runs a new id. Old runs are never rewritten.
- Execution-only knobs stay out of identity: `max_workers` is removed before hashing (`validate_cmds.py`).
- Seeds: `_seeds.semantic_seed(master, namespace)`; adding/reordering namespaces must not shift other seeds.
  [ADR-0007](../../adr/0007-deterministic-run-id-and-seeds.md) is superseded for v3 by ADR-0013.
- A rule strategy's canonical spec bytes go into `params.rules_spec`, so changing a saved rule makes a new run id and overwriting a rule name never changes a
  past run. The `rules` strategy fingerprint covers `rules.py` and `rule_strategy.py` (`_identity.py`).
- An owner research-gate override and the Workstation run context both fork identity; see [command line research § Strategy promotion and
  overrides](cli-research.md#strategy-promotion-and-overrides). `run_context.py` accepts only a schema-1 `standalone_sandbox` or `governed_project` context
  and fails loud otherwise.
## Artifacts and run directories
- `run_store.RUN_DIRS` (`runs`, `portfolio`, `cross_sectional`, `optim`, `propfirm`, `forecast`) lists every run directory; the package root re-exports it.
  Keep `run_store.py` and `catalog.py` free of Polars and engine imports so web and MCP import them cheaply (`tests/unit/test_public_seams.py`).
- `_artifacts.publish_artifact`: identical rewrites are no-ops, different bytes fail; nothing may be added after the manifest exists.
- The manifest is the completion marker: `write_manifest` hashes every sidecar (schema, sha256, size, rows), publishes last and refuses different bytes.
- V1/v2 runs stay readable with `trace_unavailable`; never migrate or rewrite. No mutable state belongs in run directories.
## Validation and optimisation
- `_gauntlet.py`/`_optim.py` refuse `--size-on-equity` and `--halt-drawdown`: the Tier-1 surrogate cannot model equity-path-dependent sizing.
- `--allow-short` on CASH fails loud (defaults: short-allowed MARGIN, long-flat CASH); `train_size` below the strategy warm-up floor fails loud.
- `--snapshot` verifies and reads the frozen snapshot, never the live store.
- The headline null must be beaten in every null tier that runs. [ADR-0006](../../adr/0006-two-tier-null-model.md); method rules in [research integrity §
  Statistical evidence](research-integrity.md#statistical-evidence).
- `alpha optim mcpt` is an in-sample overfitting test only; its manifest carries a caveat that it is never OOS evidence. It has no MCP tool. Seed namespace
  `validation.bar_permutation_is`; the walk-forward Tier 3 uses `validation.bar_permutation_wf`, and `--tier3-paths` is a run-identity input.
- Basket runs (`backtest portfolio`, `backtest cross-sectional`) sort symbols into canonical order before running, so ranking ties and float sums do not
  depend on argument order. Inverse-volatility weights are causal: each date uses only trailing OOS returns realised strictly before it, never full-sample
  volatility (`_portfolio.py`).
- `alpha propfirm run` takes exactly one of SYMBOL or `--from-run`. Firm presets are illustrative, never authoritative firm terms
  (`alpha_validation.propfirm.FIRM_PRESETS`).
- Classical Monte Carlo resamples the run's OOS account returns (IID empirical, a two-state Markov regime chain with a training-frozen causal volatility
  boundary, Student-t); Kronos replays its synthetic tails through the full engine.
- Monte Carlo path risk (`monte_carlo_cmds.py`) answers a different question from the null tests and is not edge proof; a warning stage needs the CLI-only
  owner review. [ADR-0029](../../adr/0029-four-family-monte-carlo-validation.md)
## General rule trials
- `alpha test` accepts a TOML/JSON idea or rule flags, evaluates each asset long/flat with all-in sizing, and publishes ordinary `validate` artifacts under
  the home data directory, even for another store's bars. Scored equity stores per-bar gross returns and fill costs ([cost check](cli-investigation-tools.md)).
- `spec.json` is included before the immutable manifest. The manifest's `spine` key records the test id, spec hash, name, idea, rule, store, integrity labels
  and an annualisation basis (daily: elapsed years snapped to 252/365; intraday: median bars per trading date times 365 if 20% or more of bar dates are
  weekends, else 252 on weekdays; outside identity); `source` identifies the resolved provider.
- The test id hashes the spec hash and sorted prepared run ids. An identical retry verifies existing artifacts without rewriting them and appends a `repeat`
  trial; so does the same test after a code change ([test key](cli-trial-ledger.md#rule-test-counting));
  the manifest retains its original test association. `idea_id` hashes spec and data without code; `alpha results --idea-id` filters by it.
- `alpha test` reads bars and dividends only up to 2023-12-31 ([reserved period](../project/reserved-period.md)).
  With held-back bars it adds the label `reserved-period-held-back`, prints one sentence, records `spine.reserve`
  and puts `research_cutoff` 2023-12-31 into the run identity. Without them the run id is unchanged.
  `alpha results show` and run facts derive `reserved-period-seen` for an older run whose last bar is on or after
  2024-01-01; stored runs are never rewritten. `alpha tool` reads a held-back run only up to its `research_cutoff`.
- `alpha optim`, `validate`, `backtest` (oos, run including `--manifest-id`, portfolio, cross-sectional), `scan run`, `scan hypotheses`, `rules
  explain`, `lookalike`, `unusual`
  and `labels barrier` hold the period back the same way (`reserve.Hold`): same cut-off, label, sentence and identity rule.
  With `--json` the result carries a `reserve` field and no sentence. `scan check` is forward use and is not held back.
  A hypothesis scan with held-back bars freezes `research_cutoff`, `reserve` and the label in its spec; the trial count is unchanged.
  The crypto lane counts rows (bars, funding, open interest): its record is `held_back_rows` and its sentence says so.
- `ledger/trials.jsonl` is append-only `AlphaTrialV1` (lock file, strict JSON, fsync); `trial_index` and `total_trials` equal the 1-based line number and
  corruption fails loud. Errors count as trials with an `error` label and null unavailable metrics; the command output explains them.
- `quick` = 20/4/4 null paths, 50 resamples. Every run carries `all-in`, `dev-machine-data`, a data-health label; defaulted sources and short history too.
- CASH equity-sized long entries from flat are capped at the affordable size step including fees at the open; the existing buffer stays. The manifest/result
  counts `resized_entries` in scored execution and prints a line above zero; older runs load without it.
- Runs recorded before the entry-gap fix may contain late entries. Hashing inputs/rules stay unchanged; source edits change the fingerprint.
- Minimum warm-up, the validation default five-bar embargo and anchored near-annual folds score almost all remaining history. These exploratory results and
  trial counts grant no research or owner authority.
## Stored facts and diagnostics
- Rule tests store cost/parameter re-runs and a returns-level delay; `--no-diagnose` skips them (labelled) but keeps the dated `spine.periods` facts.
- Diagnostics and the manifest are staged together and the completed run directory is renamed into place. `diagnostics.json` stores benchmark comparisons,
  drawdowns, calendar returns, trade concentration, variants, family-counted Sharpe and verdict ([counting](cli-trial-ledger.md)), flags and a macro window
  (stored FRED at the worst drawdown start/trough, as known at the trough; `spine/macro.py`). Flags are observations, never a verdict; unavailable numbers are
  null with a plain reason and separate detail. `share_explained` is a ratio (benchmark fall / strategy fall); a top-three profit above 1 is a multiple.
- `inverted_signal` shorts where the rule was long (same engine, bars, costs, next-open fills), re-sized to 100% of equity net of short dividends each bar;
  CASH shorts are hypothetical, no borrow or funding cost; no ledger, variant or family count ([card](../../../research/tools/inverted-signal-control.md)).
- `walk_forward_efficiency`: per fold, OOS CAGR over the full-sample CAGR on its recorded train window (warm-up trimmed); median of defined folds. Rule of
  thumb, not a test; folds without OOS trades are counted and null it when most: [WFE card](../../../research/tools/walk-forward.md).
- Under 30 closed OOS trades, `too-few-trades` labels the run, facts and verdict/DSR headlines (`results check` needs "too few trades"); grade A/B reads C
  in the manifest and ledger row, D/F and numbers kept. The HTML tear sheet does not yet carry the too-few-trades caveat.
- A rule test also stores a `reading` beside `verdict`: [readings](cli-rule-readings.md).
- [`price_noise`](../../../research/tools/price-noise.md): 50 run-id-seeded price-feed controls, no ledger trial; `implausibly-good` never improves a verdict.
- Audit entries are independent PASS / FLAG / NOT-CHECKED, no overall grade; traces use walk-forward artifacts; fill ranges allow recorded slippage
  (NOT-CHECKED without cost settings); the manifest verifies every sidecar. `data_period` / `traded_period` facts: loaded-bar and stored-equity endpoints.
- `alpha results` lists the ledger ([all trials](cli-trial-ledger.md)); `show` reads facts, flags, audit, figures and [`alpha
  tool`](cli-investigation-tools.md) outputs (for a test id, failed or unreadable assets under `failed` with a reason); `cite` quotes a stored field; `alpha
  diagnose` never re-runs a strategy. Metric vocabulary: `spine/facts.py:METRICS`; facts carry run id, basis, source file/field, labels and a reason exactly
  when the value is null. Dated rows and price basis live in `spine.periods` ([benchmark card](../../../research/tools/benchmark-and-drawdowns.md)).
- These commands and `alpha test` exit 1 with a structured error (`code`, `message`, `known`, imperative `next`; JSON under `--json`), even when every asset
  fails. Ledger schema stays `AlphaTrialV1`; optional `variants_evaluated` counts sensitivity re-runs apart from the append-only row index.
## Draft checks, lookalikes and novelty
- `results check|compare`: [checks](cli-results-check.md); `lookalike|unusual`: [patterns](patterns.md#lookalikes-and-novelty).
## Suites
- `alpha suite` runs only the declared actions in `SUITE_ACTIONS` through durable attempt and job lineage; it polls heartbeat and cancellation every 5 seconds
  and reaps child process groups. Plan building lives in `_suite.py` (`build_suite_plan`), the step and plan types in `_suite_types.py`, per-action step
  builders in `_suite_actions.py`.
- Suite Qlib, Kronos and Monte Carlo kinds share the heavyweight capacity class; see [command line control plane § Jobs, leases and
  capacity](cli-control-store.md#jobs-leases-and-capacity).
## Figures
- Figures are a derived cache under `data_dir/figures/<run_id>/`, never run artifacts. Writing into a run directory would break the manifest's exact file set.
- The cache key hashes renderer identity plus the run's declared artifact digests. Legacy runs fall back to size and mtime and are tagged so the two kinds of
  key cannot collide (`figure_cache.input_digest`).
- Write the image first and the JSON sidecar last; the sidecar marks completion. Forced re-renders must be byte-identical.
- `figure_cache.py` must not import Polars, numpy, matplotlib or the renderer. Enforced by `tests/unit/test_figure_cache.py`.
- `figures list --json` without `--run` publishes the key environment, so the web computes keys without the renderer.
- Builders read declared artifacts only and report an honest unavailability reason instead of guessing.
- RD-Agent [journeys](../../../research/tools/rdagent-journey.md) publish only under the selected journey folder and exclude reserved-period observations.
- A run's price figure and chart candles read its snapshot at the run's own bar size: the manifest's `timeframe`, `source_timeframe` and `session` pass to
  `alpha data candles` as single `--option=value` arguments; a daily manifest has none, so its call is unchanged
  (`tests/unit/test_run_projection_security.py`).
## Rules, scans and chart overlays
- `alpha_strategies.rules` is the only rule parser; the CLI stores canonical JSON and interprets nothing.
- `resolve_rules_spec` pairs the flags fail-closed: `--strategy rules` needs `--rules NAME`, `--rules` with any other strategy fails, and a frozen
  `--rules-file` needs a matching `--rules-sha256`, canonical bytes and at most 1,000,000 bytes.
- `rules explain` reads canonical bars through `load_bars` cut at the end of `--as-of`, saves nothing and reports `authority: none`. Missing history or an
  invalid operand is an unavailable signal, never a flat one.
- `scan run` evaluates each symbol on bars cut at the end of `--as-of`, so a later bar never changes an as-of result. Its universe is the symbols stored now
  (`universe_as_of` is wall-clock), so a scan is not survivorship-safe.
- `scan run` writes nothing. `scan check` appends only changed signals to `scans/alerts.jsonl`. A scan is a screen, never evidence.
- `scan hypotheses` screens a frozen snapshot (equity) or frozen crypto manifests, records every attempt under `scans/hypotheses/` and has no authority. Its
  cost-adjusted spread charges `4 x horizon_turnover x` the one-way cost, where `horizon_turnover` is the bucket replacement between dates one horizon apart
  (a book rebalanced every horizon); `turnover` keeps the one-row figure. Equity outcomes are split-adjusted price returns without dividends. Checked against
  pandas and SciPy by `tests/oracles/test_differential_hypothesis_screen.py`.
- `alpha chart overlays` reads the same point-in-time window as `alpha data candles`, nulls warm-up values only at the head, filters patterns through their
  `*_known_by(last)` check, and fails loud on any other non-finite value. Only the indicators in `_NAN_AFTER_WARMUP` may null a legitimately undefined later
  window. Each indicator refuses a window shorter than its longest lookback, and each pattern names in `reason` the bar it became drawable. Enforced by
  `tests/unit/test_chart_overlays_bias_guard.py`.
- `figures`, `chart` and `scan` produce no run and stay out of `alpha info commands` (`info_cmds._NON_RUN_COMMAND_PREFIXES`).
## Setup find
Moved to [cli-setups.md § Setup find](cli-setups.md#setup-find).

## Setup study
Moved to [cli-setups.md § Setup study](cli-setups.md#setup-study).

## Setup trade
Moved to [cli-setups.md § Setup trade](cli-setups.md#setup-trade).

## Nightly real run
Moved to [cli-nightly.md](cli-nightly.md).
