# Verification: one real RD-Agent loop, end to end

Run on the Dell on 2026-11-14 (UTC 09:18:52 to 09:23:14). Everything below comes from the run's
own records in `/home/hunta/alpha-clean-base/runs/2026-11-14-rdagent-first-real-loop/` (outside
every git tree). Labels: **exploratory, not admitted, not yet confirmed.** Nothing here is evidence.

## Verdict

The loop ran end to end once: propose, code, run (Qlib backtest), feedback, record. Every step
was executed by RD-Agent's own unmodified code (pinned `484776c`) on real Binance daily bars, and
every model call went through the model gateway on the Codex route. No step was stubbed and no
answer was supplied.

**But the backtest step measured nothing about the idea.** RD-Agent's built-in Qlib model
(LightGBM with `lambda_l1` 205.7 and `lambda_l2` 581.0, tuned for 300 Chinese stocks) learned
nothing from 15 coins: it gave every coin the identical score on every day, in the baseline and in
the experiment (`pred.pkl`: one unique value in 15,510 rows, IC 3.6e-18, rank IC undefined).
With all scores tied, which coins the portfolio held is arbitrary, so the returns are noise; the
AI's feedback ("improved", decision True) is a judgement of that noise. As a research loop it is
therefore **not yet meaningful**; as plumbing it is complete.

## Step by step

| Step | Time (UTC) | What happened | Evidence |
|---|---|---|---|
| Propose | 09:19:04 – 09:19:46 | Hypothesis: four simple daily factors, tested separately: 5-day reversal, 20-day volatility, 5/20-day relative volume, same-day open-to-close return. Experiment: four factor tasks with formulas. | `work/log/Loop_0/direct_exp_gen` |
| Code (CoSTEER) | 09:19:46 – 09:21:58 | The model wrote four `factor.py` programs. RD-Agent ran each on the real debug window (all 15 coins, 2021–2022) and its execution, format, critic and final-decision checks accepted all four in the first round. Read by hand: each uses only past and same-day values, per coin. | `work/git_ignore_folder/RD-Agent_workspace/{4b30…,4d79…,909d…,ab83…}/factor.py` |
| Run (backtest) | 09:21:58 – 09:22:55 | RD-Agent's `QlibFactorRunner` ran `qrun conf_baseline.yaml` (baseline, 20 default features) then `qrun conf_combined_factors.yaml` (baseline features plus the four factors, full 2017–2026 data) in Docker image `local_qlib:latest`, then read the results. | `…/4ad6…/logs/`, `…/556d…/logs/`, `qlib_res.csv`, `ret.parquet` |
| Feedback | 09:22:55 – 09:23:13 | The model compared the experiment with the baseline (below) and proposed a next factor (a volume-confirmed close location in the day's range). | `work/log/Loop_0/feedback` |
| Record | 09:23:13 | RD-Agent stored the round in its trace. | `work/log/__session__/0` |

Backtest settings (environment variables RD-Agent passes to Qlib): train 2018-01-01 to
2022-12-31, valid 2023, test 2024-01-01 to 2026-10-30. Qlib's own figures (it annualises with 252
days a year; crypto trades 365, so its annual figures are understated):

| Measure | Baseline (in the loop) | Four factors added |
|---|---|---|
| IC / rank IC | 3.6e-18 / undefined | 3.6e-18 / undefined |
| Annualised excess return, with costs | −9.40% | −9.11% |
| Annualised excess return, without costs | +0.71% | −5.53% |
| Max drawdown of excess return, with costs | −44.49% | −47.18% |

The same baseline configuration, run once by hand before the loop on the same data, gave −20.21%
with costs: with tied scores the backtest is not even repeatable.

What the feedback said (summarised): all four factors were implemented and tested together;
annualised excess return after costs "improved" by 0.29 percentage points while drawdown worsened
by 2.7 points; the IC stayed at zero, so stronger prediction is not shown; it asked for unrounded
IC, coverage, timing and cost checks, and leave-one-out tests. It set decision True.

## The model connection

27 gateway calls (19 chat on `gpt-6.1-sol`, effort `medium`; 8 embeddings on Ollama
`nomic-embed-text`), all status 200, every JSON reply valid first time, no tool events, 0 USD.
Chat: 88,728 input and 3,328 output tokens, 161.5 s of model time, longest call 24.8 s.
`temperature` was waived on every chat call, as the owner accepted. Budget file afterwards:
`{"runs": {"rdloop-20261114-1": {"calls": 27, "usd": 0.0}}}` against caps of 60 calls and 10 USD.
Records: `gateway/model-gateway/calls.jsonl` (no prompt or reply text), `logs/gateway.stderr.log`.

## The data

- Source: ALPHA's qualified Binance spot daily bars for 15 coins (ADA, ATOM, AVAX, BCH, BNB, BTC,
  DOGE, DOT, ETH, LINK, LTC, SOL, TRX, XLM, XRP against USDT), read only from
  `/home/hunta/alpha-clean-base/data`. Each of the 1,425 monthly artifacts was re-hashed against
  its manifest; every manifest is "qualified"; no date overlaps, no gaps, no invalid prices;
  43,181 bars from 2017-08-17 to 2026-10-31. Receipt: `qlib-build-receipt.json`.
- Converted with Qlib's own `scripts/dump_bin.py` inside the Qlib image; hashes of every file in
  `logs/qlib-data.sha256`. Read back, BTC closes match the source to 0.004 USD (Qlib stores
  float32). `$vwap` = quote volume / base volume, `$factor` = 1.
- **Name aliases the templates force:** the folder is called `cn_data`, the universe `csi300`
  (= the 15 coins) and the benchmark `SH000300` (= an equal-weight index of the coins trading each
  day). Nothing Chinese is in it. Written down in the run's `ALIASES.md`. There is no `$change`
  field, so Qlib's 9.5% price-limit rule never fires.
- RD-Agent's factor data (`daily_pv.h5`) was made by RD-Agent's own `generate.py`, run in the
  same image, with one change: its debug window moved from 2018–2019 to 2021–2022, because SOL,
  DOT and AVAX did not trade before 2020 and the original window fails on them.

## What was set up, and every deviation from a plain RD-Agent run

- `bash scripts/setup_rdagent.sh --with-stock-runtime` in the main checkout (source digest and
  stock runtime identity verified).
- `local_qlib:latest` built from RD-Agent's own Dockerfile, unchanged (image
  `sha256:c5a349b2…`, 10.9 GB; Qlib at `2fb9380`, LightGBM 4.7.0, pandas 2.3.3). The Dockerfile
  pins Qlib but not its other packages, so the image is not reproducible byte for byte.
- That image's unpinned MLflow refuses Qlib's file store unless `MLFLOW_ALLOW_FILE_STORE=true`;
  passed through RD-Agent's own `QLIB_DOCKER_ENV_DICT` setting. Without it every backtest fails.
- RD-Agent ran in a Python 3.11 environment in the run folder: the hash-pinned stock lock plus
  pandas 2.2.3, scipy 1.14.1, tables 3.10.1, pyarrow, pandarallel and fire, which RD-Agent's Qlib
  scenario imports and the stock lock leaves out (numpy moved from 2.4.6 to 2.2.6 for pandas).
  These extras are not pinned by hash.
- RD-Agent's factor coder asks `conda` for its environment's PATH; this machine has no conda. A
  small `conda` stand-in in the run folder answers only that one question (pointing at the run's
  Python) and fails loudly on anything else. It is an environment adapter, not a research step.
- Settings, all through RD-Agent's own environment variables: `MODEL_CoSTEER_env_type=docker`,
  `FACTOR_CoSTEER_max_loop=2`, `FACTOR_CoSTEER_python_bin`, the two factor data folders,
  `QLIB_DOCKER_BUILD_FROM_DOCKERFILE=False`, `QLIB_DOCKER_ENABLE_GPU=False`,
  `QLIB_DOCKER_EXTRA_VOLUMES` (the crypto folder, read-only), the `QLIB_FACTOR_*` dates, and the
  gateway settings of ADR-0044. Launcher: `scripts/run_loop.sh` in the run folder.

## Diagnostics outside the loop (not evidence)

- Same baseline with the two LightGBM penalties set to 0 (a copy of the template, not RD-Agent's
  file): the model then varies (76 distinct scores), IC 0.0099, rank IC 0.013. So the penalties
  are what flatten the model on this small universe. `diag-lgbm-regularisation/`.
- Daily rank correlation of each factor with Qlib's label, computed directly: 20-day volatility
  about −0.06 in 2018–2022 and −0.07 in 2024–2026; the other three within ±0.02. So at least one
  factor carried a measurable cross-sectional pattern that the backtest never used. On 15 coins
  chosen today (survivors), with naive statistics and no correction for testing four factors,
  this is a lead, not a finding.

## Not verified

- That RD-Agent's loop gives a meaningful backtest on any data; it did not here.
- Repeatability: model answers vary; the tied-score backtest varied between identical runs.
- Qlib's backtest rules versus ALPHA's: Qlib decides on day t and trades at day t+1's close, with
  Chinese-market costs (0.05% buy, 0.15% sell), a holding of up to 50 names from 15, and its own
  sum-based drawdown; ALPHA fills at the next open and uses Nautilus. None of this was reconciled.
- More than one iteration; resume after a crash; the paid route.

## Checks run

- `uv run python scripts/gate.py check`: see the pull request.
- `uv run python scripts/fs.py stale`: 0.
