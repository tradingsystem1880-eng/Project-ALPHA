# ADR-0049: ALPHA, not RD-Agent's built-in Qlib backtest, judges RD-Agent's factors

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** AI build agents, under the owner's standing instruction to act on what serves the
goal and the architecture the owner stated: "RD-Agent runs the research loop; Qlib supplies
research tools and models; Nautilus runs execution-aware backtests; ALPHA connects and governs them"

## Context

The first real RD-Agent loop (2026-11-14, pinned `484776c`, 15 Binance coins) ran end to end but
its run step measured nothing: RD-Agent's factor runner (`QlibFactorRunner`) trains Qlib's
LightGBM with settings tuned for about 300 Chinese stocks (`lambda_l1` 205.7, `lambda_l2` 581.0),
which gave every coin the same score every day, so the backtest and the model's "improved" verdict
were noise. Its conventions are also wrong for crypto: 252 trading days, Chinese costs (0.05% buy,
0.15% sell), a top-50 portfolio from 15 names, trades at the next day's close, and an unpinned
10.9 GB Docker image that needs `MLFLOW_ALLOW_FILE_STORE=true`
([verification](../work/archive/2026-11/2026-11-14-rdagent-first-real-loop/04-verify.md)).
RD-Agent's templates must stay unmodified.

What the pinned source offers, read file by file:

- `rdagent/app/qlib_rd_loop/conf.py:FactorBasePropSetting` is a pydantic settings class with
  `env_prefix="QLIB_FACTOR_"`; its fields `scen`, `hypothesis_gen`, `hypothesis2experiment`,
  `coder`, `runner` and `summarizer` are dotted class paths.
- `rdagent/components/workflow/rd_loop.py:RDLoop.__init__` builds each with
  `rdagent.core.utils.import_class`. So `QLIB_FACTOR_RUNNER`, `QLIB_FACTOR_SUMMARIZER` and
  `QLIB_FACTOR_SCEN` replace a step with a class supplied from outside RD-Agent's tree. This is
  RD-Agent's own configuration surface (it is how its model, quant and Kaggle loops differ), not
  an edit.
- `FactorRDLoop.running` calls `runner.develop(exp)` and stores what it returns;
  `feedback` calls `summarizer.generate_feedback(exp, trace)` and stores the
  `HypothesisFeedback`, whose `decision` decides which factors RD-Agent carries forward.
- `rdagent/scenarios/qlib/developer/utils.py:process_factor_data(exp)` runs each accepted
  `factor.py` on the full data folder and returns the factor values; RD-Agent's own runner uses it.
- The factor coder runs generated code with `FACTOR_CoSTEER_python_bin` through `LocalEnv`; its
  conda lookup (`CondaConf._update_bin_path`) only fills a PATH prefix and yields an empty prefix
  when `conda` is absent, so an absolute `python_bin` plus any `CONDA_DEFAULT_ENV` value needs no
  conda and no stand-in.

## Decision

1. **Extension point.** ALPHA supplies three classes through RD-Agent's settings, in a worker
   module `workers/rdagent/alpha_factor_judge.py` that runs inside RD-Agent's process and imports
   RD-Agent and pandas but no ALPHA package:
   - `AlphaFactorScenario` (subclass of `QlibFactorScenario`): replaces only the descriptions of
     the simulator and the experiment setting with the true ones (15 Binance USDT spot coins,
     daily bars, ALPHA's evaluation below); proposal and coding prompts are otherwise RD-Agent's.
   - `AlphaFactorRunner` (replaces `QlibFactorRunner`): gets factor values with RD-Agent's own
     `process_factor_data`, runs the look-ahead check (point 4), writes the values to Parquet and
     calls ALPHA's evaluator as a subprocess in ALPHA's own environment. No Qlib model, no Docker,
     no MLflow.
   - `AlphaFactorFeedback` (replaces `QlibFactorExperiment2Feedback`): gives the model ALPHA's
     result, with the disclosures, in RD-Agent's own feedback prompt, and records the model's
     observations and next hypothesis. **The `decision` is ALPHA's rule, not the model's**; the
     model's suggestion is recorded beside it.
   RD-Agent's proposer, coder, loop engine, trace and checkpoints are used as they are.
2. **Evaluator.** `alpha_cli.rdagent_factor_eval` (Python 3.12, ALPHA's environment) judges one
   experiment's factors against one frozen panel. Per factor, on the exploration window only:
   - the daily cross-sectional rank IC between the factor at the close of day t and the
     open-to-open return from day t+1 to day t+2 (decide at close, fill at next open), with
     `alpha_research.panel.cross_sectional_ic`; its mean with a seeded stationary-bootstrap
     interval (`alpha_validation.bootstrap.block_bootstrap_ci`) and a p-value from the
     autocorrelation-adjusted sample size (`alpha_validation.proportion.autocorrelation_effective_size`);
   - an execution-aware long-only replay through ALPHA's canonical synchronized engine
     (`alpha_backtest.portfolio_replay.run_weight_replay`): equal weight in the top third of coins
     by the factor, rebalanced daily at the next open, 10 bps fee and 6 bps half-spread plus
     slippage per side (the crypto economics of the daily rule study), against the equal-weight
     basket of all coins; net excess return, annualised with 365 days, turnover and Sharpe.
   Not Nautilus: ALPHA has no Nautilus cross-sectional replay yet; that stays a backlog item.
3. **Data, point-in-time by construction.** ALPHA freezes one panel per run from the qualified
   Binance manifests (each artifact re-hashed) and writes RD-Agent's `daily_pv.h5` from the same
   panel, so factors and evaluation see the same bars. A row dated d is the bar opened at d and is
   known at its close (d + 24 h). **RD-Agent is never given data on or after the reserved
   confirmation window's start (2024-01-01)**; that window is not evaluated by the loop at all, so
   neither the model nor ALPHA's rule can be tuned on it. The exploration window is 2021-01-01 to
   2023-12-31, where all 15 coins trade (the replay needs a full rectangle).
4. **Look-ahead guard.** RD-Agent's generated code sees the whole debug and full frames, so it is
   not point-in-time by construction within the exploration window. The runner catches look-ahead
   by prefix invariance: it re-runs each `factor.py` on the frame truncated at three fixed cut
   dates and requires that every value at or before a cut is unchanged; a factor that fails is
   marked `LOOKAHEAD`, is not evaluated and counts as a test. The reserved window is protected by
   construction (point 3).
5. **Multiple testing.** Every factor RD-Agent produces in a run enters one family, in order:
   evaluated, failed and `LOOKAHEAD` factors alike (the last two with p = 1). Each result carries
   the family size so far, Benjamini–Hochberg q-values over the whole family
   (`alpha_validation.proportion.benjamini_hochberg`) and the Deflated Sharpe of the replay with
   all the family's Sharpe ratios as trials (`alpha_validation.dsr.deflated_sharpe`).
6. **ALPHA's decision rule, fixed before the first run.** `decision = True` only when a factor has
   BH q < 0.10 on mean rank IC, passed the look-ahead check and has positive net excess return in
   the replay. Otherwise `False`, whatever the model says.
7. **Records and labels.** Each iteration appends one JSON record to the run's
   `evaluations.jsonl`: input hashes (panel, factor values, `factor.py`, evaluator source
   fingerprint, configuration), the metrics, the look-ahead result, the family size and q-values,
   ALPHA's decision and the model's suggestion. Every record and every feedback text carries:
   label `exploratory, not admitted, not yet confirmed`; survivorship: "15 coins chosen in
   2026-11 from today's survivors; coins that were delisted or collapsed (for example LUNA, FTT)
   are absent, which biases results upward"; the family size; the windows and costs. Nothing the
   loop produces is evidence, and nothing here can admit, approve or promote.

## Options considered

| Option | Verdict |
|---|---|
| Keep RD-Agent's Qlib backtest, retune it | Rejected: its templates must stay unmodified; its conventions (252 days, Chinese costs, next-close fills) are wrong for crypto |
| A wider universe (about 300 coins) for the built-in model | Rejected for now: needs a large download, keeps the wrong conventions, and the judge would still be RD-Agent's |
| Route RD-Agent's factors into ALPHA's Qlib worker (W09) | Not now: W09 is a shelved, LightGBM-specific fit DAG with no factor schema; a factor's rank IC needs no model fit. W09's patterns (content-hashed identity, worker fingerprint, all-False authority flags) are reused |
| Patch or copy RD-Agent's runner | Rejected: forbidden, and unnecessary because the settings take class paths |
| **ALPHA classes through RD-Agent's settings, ALPHA evaluator by subprocess** | **Chosen** |

## Consequences

- RD-Agent's unpinned Qlib image, MLflow switch and LightGBM are no longer needed for the factor
  loop; the factor runtime is a hash-pinned Python 3.11 lock without Qlib.
- RD-Agent's feedback now reflects a measurement: a null result says "no detectable rank IC"
  instead of an arbitrary portfolio return.
- Harder: three classes depend on RD-Agent's internal interfaces at `484776c` (`process_factor_data`,
  `HypothesisFeedback`, the scenario properties); a new pin must re-check them.
- Not covered: Nautilus fills, a survivorship-free universe, the reserved window's confirmation
  (an owner-run step, outside the loop), and supervision by `alpha`'s job supervisor (see the
  task record).

## Implementation anchors

- `workers/rdagent/alpha_factor_judge.py`: `AlphaFactorScenario`, `AlphaFactorRunner`,
  `AlphaFactorFeedback`, the prefix-invariance check.
- `apps/alpha-cli/src/alpha_cli/rdagent_factor_eval.py`: panel freezing and evaluation.
- Task record: [2026-11-14 ALPHA-judged RD-Agent loop](../work/archive/2026-11/2026-11-14-rdagent-alpha-judged-loop/01-brief.md).
