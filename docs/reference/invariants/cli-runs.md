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
  - tests/unit/test_run*.py
  - tests/unit/test_gauntlet*.py
  - tests/unit/test_suite_*.py
  - tests/unit/test_figure*.py
  - tests/integration/test_validate_*.py
  - tests/integration/test_backtest_*.py
verified: 70f15b4e80c4
---

# Command line runs invariants

What must not break when changing how the CLI composes backtests, validation, optimisation, Monte Carlo and figures,
and how it names and publishes immutable runs. Project-wide rules:
[research integrity § Immutable, hash-bound artefacts](research-integrity.md#immutable-hash-bound-artefacts) and
[research integrity § Deterministic seeds and identity](research-integrity.md#deterministic-seeds-and-identity).

## Composition

- `alpha_cli` is the only layer that composes the engine with the gauntlet; engine imports stay lazy.
  [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md), [engineering § Import layers](engineering.md#import-layers)
- Strategies read bars only through `_runner.load_bars` with an `as_of` cutoff, and decisions fill at the next open.
  See [research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads) and
  [research integrity § Decide at close, fill at next open](research-integrity.md#decide-at-close-fill-at-next-open).
- `_gauntlet.py`, `_optim.py`, `_runner.py`, `_synth.py`, `_surrogate.py`, `_seeds.py` and `_identity.py` are
  high-risk statistical or identity code; follow [engineering § Quant tier](engineering.md#quant-tier). They sit outside
  `gate.py::matches_quant` (packages only), so CI runs no mutation gate on them: their tests and the oracles are the
  binding check; ask the `reviewer` agent to review the diff (advisory, ADR-0039; stage 04 of the delivery pipeline).
- `_schemas.py` is the one canonical home of strategy parameter definitions, bounds and defaults; `_strategies.py` and
  `_runner.parse_strategy_params` read from it, and values are normalised to the stable floats stored in `RunSpec`.
- Slash symbols (`BTC/USD`) are crypto pairs and need `--account-type MARGIN`; a CASH account fails loud (`_runner.py`).

## Run identity

- A run id is a deterministic 16-hex digest of the canonical payload plus identity version 3, the execution
  fingerprint, the strategy fingerprint and the verified snapshot hash (`_runner.run_identity_for`, `_identity.py`).
  No wall-clock value may enter it. [ADR-0013](../../adr/0013-run-identity-v3-and-causal-artifacts.md)
- The execution fingerprint hashes every `.py` file in `alpha_core`, `alpha_data`, `alpha_backtest`,
  `alpha_strategies`, `alpha_patterns`, `alpha_validation`, `alpha_forecast` and `alpha_cli`. Any byte edit there,
  including this CLI, gives new runs a new id. Old runs are never rewritten.
- Execution-only knobs stay out of identity: `max_workers` is removed before hashing (`validate_cmds.py`).
- Seeds come from `_seeds.semantic_seed(master, namespace)`; adding or reordering namespaces must not shift any
  other seed. [ADR-0007](../../adr/0007-deterministic-run-id-and-seeds.md) is superseded for v3 by ADR-0013.
- A rule strategy's canonical spec bytes go into `params.rules_spec`, so changing a saved rule makes a new run id and
  overwriting a rule name never changes a past run. The `rules` strategy fingerprint covers `rules.py` and
  `rule_strategy.py` (`_identity.py`).
- An owner research-gate override and the Workstation run context both fork identity; see
  [command line research § Strategy promotion and overrides](cli-research.md#strategy-promotion-and-overrides).
  `run_context.py` accepts only a schema-1 `standalone_sandbox` or `governed_project` context and fails loud otherwise.

## Artifacts and run directories

- `run_store.RUN_DIRS` (`runs`, `portfolio`, `cross_sectional`, `optim`, `propfirm`, `forecast`) lists every run
  directory; the package root re-exports it. Keep `run_store.py` and `catalog.py` free of Polars and engine imports so
  web and MCP import them cheaply (`tests/unit/test_public_seams.py`).
- Publish each artifact once (`_artifacts.publish_artifact`): an identical rewrite is a no-op, different bytes fail,
  and nothing may be added after the manifest exists.
- The manifest is the completion marker. `write_manifest` hashes every sidecar (schema, sha256, size, rows) and is
  published last; a different manifest at the same path fails.
- V1 and v2 runs stay readable and report `trace_unavailable`; never migrate or rewrite them.
- Mutable state (paper sessions, jobs, figures, workspaces, UUIDs, PIDs, heartbeats) never goes into a run directory.

## Validation and optimisation

- The gauntlet and optimiser refuse `--size-on-equity` and `--halt-drawdown`: the Tier-1 surrogate cannot model
  equity-path-dependent sizing (`_gauntlet.py`, `_optim.py`).
- An explicit `--allow-short` on a CASH account fails loud; the default is short-allowed on MARGIN and long-flat on CASH.
- `train_size` below the strategy warm-up floor fails loud.
- `--snapshot` verifies and reads the frozen snapshot, never the live store.
- The headline null must be beaten in every null tier that runs. [ADR-0006](../../adr/0006-two-tier-null-model.md);
  method rules in [research integrity § Statistical evidence](research-integrity.md#statistical-evidence).
- `alpha optim mcpt` is an in-sample overfitting test only; its manifest carries a caveat that it is never OOS evidence.
  It has no MCP tool. Seed namespace `validation.bar_permutation_is`; the walk-forward Tier 3 uses
  `validation.bar_permutation_wf`, and `--tier3-paths` is a run-identity input.
- Basket runs (`backtest portfolio`, `backtest cross-sectional`) sort symbols into canonical order before running, so
  ranking ties and float sums do not depend on argument order. Inverse-volatility weights are causal: each date uses
  only trailing OOS returns realised strictly before it, never full-sample volatility (`_portfolio.py`).
- `alpha propfirm run` takes exactly one of SYMBOL or `--from-run`. Firm presets are illustrative, never authoritative
  firm terms (`alpha_validation.propfirm.FIRM_PRESETS`).
- Classical Monte Carlo resamples the run's OOS account returns (IID empirical, a two-state Markov regime chain with a
  training-frozen causal volatility boundary, Student-t); Kronos replays its synthetic tails through the full engine.
- Monte Carlo path risk (`monte_carlo_cmds.py`) answers a different question from the null tests and is not edge proof;
  a warning stage needs the CLI-only owner review. [ADR-0029](../../adr/0029-four-family-monte-carlo-validation.md)

## Suites

- `alpha suite` runs only the declared actions in `SUITE_ACTIONS` through durable attempt and job lineage; it polls
  heartbeat and cancellation every 5 seconds and reaps child process groups. Plan building lives in `_suite.py`
  (`build_suite_plan`), the step and plan types in `_suite_types.py`, per-action step builders in `_suite_actions.py`.
- Suite Qlib, Kronos and Monte Carlo kinds share the heavyweight capacity class; see
  [command line control plane § Jobs, leases and capacity](cli-control-store.md#jobs-leases-and-capacity).

## Figures

- Figures are a derived cache under `data_dir/figures/<run_id>/`, never run artifacts. Writing into a run directory
  would break the manifest's exact file set.
- The cache key hashes renderer identity plus the run's declared artifact digests. Legacy runs fall back to size and
  mtime and are tagged so the two kinds of key cannot collide (`figure_cache.input_digest`).
- Write the image first and the JSON sidecar last; the sidecar marks completion. A forced re-render with different bytes
  fails because rendering must stay deterministic.
- `figure_cache.py` must not import Polars, numpy, matplotlib or the renderer. Enforced by
  `tests/unit/test_figure_cache.py`.
- `figures list --json` without `--run` publishes the key environment, so the web computes keys without the renderer.
- Builders read declared artifacts only and report an honest unavailability reason instead of guessing.

## Rules, scans and chart overlays

- `alpha_strategies.rules` is the only rule parser; the CLI stores canonical JSON and interprets nothing.
- `resolve_rules_spec` pairs the flags fail-closed: `--strategy rules` needs `--rules NAME`, `--rules` with any other
  strategy fails, and a frozen `--rules-file` needs a matching `--rules-sha256`, canonical bytes and at most 1,000,000
  bytes.
- `rules explain` reads canonical bars through `load_bars` cut at the end of `--as-of`, saves nothing and reports
  `authority: none`. Missing history or an invalid operand is an unavailable signal, never a flat one.
- `scan run` evaluates each symbol on bars cut at the end of `--as-of`, so a later bar never changes an as-of result.
  Its universe is the symbols stored now (`universe_as_of` is wall-clock), so a scan is not survivorship-safe.
- `scan run` writes nothing. `scan check` appends only changed signals to `scans/alerts.jsonl`. A scan is a screen,
  never evidence.
- `scan hypotheses` screens a frozen snapshot (equity) or frozen crypto manifests, records every attempt under
  `scans/hypotheses/` and has no authority. Its cost-adjusted spread charges `4 x horizon_turnover x` the one-way
  cost, where `horizon_turnover` is the bucket replacement between dates one horizon apart (a book rebalanced every
  horizon); `turnover` keeps the one-row figure. Equity outcomes are split-adjusted price returns without dividends.
  Checked against pandas and SciPy by `tests/oracles/test_differential_hypothesis_screen.py`.
- `alpha chart overlays` reads the same point-in-time window as `alpha data candles`, nulls warm-up values only at the
  head, filters patterns through their `*_known_by(last)` check, and fails loud on any other non-finite value.
  Only the indicators in `_NAN_AFTER_WARMUP` may null a legitimately undefined later window. Each indicator refuses
  a window shorter than its longest lookback, and each pattern names in `reason` the bar it became drawable.
  Enforced by `tests/unit/test_chart_overlays_bias_guard.py`.
- `figures`, `chart` and `scan` produce no run and stay out of `alpha info commands`
  (`info_cmds._NON_RUN_COMMAND_PREFIXES`).
