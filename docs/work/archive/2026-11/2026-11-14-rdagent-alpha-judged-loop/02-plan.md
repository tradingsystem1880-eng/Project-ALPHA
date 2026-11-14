# An RD-Agent loop that ALPHA judges: runtime, launcher, judge and evaluator

**Delivery state:** Building — design accepted in ADR-0049; code built from this plan.
**Build class:** hard — more than eight files and a bias-sensitive evaluation path.

Filed straight into the archive, as the previous RD-Agent tasks were: the work-in-progress ceiling
admits no new live plan.

```json
{
  "schema_version": 1,
  "title": "An RD-Agent loop that ALPHA judges: runtime, launcher, judge and evaluator",
  "context": "ADR-0049: RD-Agent's factor loop keeps its proposer and coder; ALPHA supplies the scenario description, the runner and the feedback through RD-Agent's QLIB_FACTOR_* settings, and ALPHA's own evaluator scores factors on a frozen point-in-time panel with a reserved 2024+ window the loop never sees.",
  "assumptions": [
    {"statement": "QLIB_FACTOR_SCEN, QLIB_FACTOR_RUNNER and QLIB_FACTOR_SUMMARIZER take dotted class paths that RDLoop.__init__ imports with rdagent.core.utils.import_class.", "verified_by": "reading rdagent/app/qlib_rd_loop/conf.py and rdagent/components/workflow/rd_loop.py at 484776c"},
    {"statement": "RD-Agent's proposer renders experiment.result.loc[['IC','1day.excess_return_without_cost.annualized_return','1day.excess_return_without_cost.max_drawdown']] and experiment.stdout for past trials, so result must be a pandas Series with those three labels.", "verified_by": "reading rdagent/scenarios/qlib/prompts.yaml hypothesis_and_feedback, last_ and sota_hypothesis_and_feedback"},
    {"statement": "FactorFBWorkspace.execute('All') links every file of FACTOR_CoSTEER_data_folder into the workspace, runs '<FACTOR_CoSTEER_python_bin> factor.py' with cwd=workspace and reads result.h5 (key data) as the factor values.", "verified_by": "reading rdagent/components/coder/factor_coder/factor.py execute()"},
    {"statement": "Without conda, CondaConf._update_bin_path leaves bin_path empty, so an absolute FACTOR_CoSTEER_python_bin and any non-empty CONDA_DEFAULT_ENV string need no conda stand-in.", "verified_by": "reading rdagent/utils/env.py CondaConf and LocalEnv._run"},
    {"statement": "workers/rdagent/factor-requirements.lock (82 hash-pinned packages, Python 3.11, pandas 2.2.3, numpy 2.2.6, tables 3.11.1) installs with --require-hashes --no-deps and imports rdagent.app.qlib_rd_loop.factor and the Qlib factor developer, proposal and experiment modules.", "verified_by": "installed into a fresh venv on the Dell and imported, 2026-11-14"},
    {"statement": "alpha_backtest.portfolio_replay.run_weight_replay replays long-only target weights decided at a close and filled at the next open over a fully aligned daily session rectangle of at least two symbols.", "verified_by": "reading packages/alpha-backtest/src/alpha_backtest/portfolio_replay.py"}
  ],
  "alternatives_considered": [
    "RD-Agent's own Qlib backtest, retuned: forbidden (templates unmodified) and wrong conventions; see ADR-0049.",
    "Running the evaluator inside RD-Agent's Python 3.11 process: would put ALPHA packages into a second environment; a subprocess into ALPHA's own environment keeps one copy.",
    "Supervising the loop through apps/alpha-cli native_supervisor now: its launch types are closed (fixture, rule, stock, daily) and bound to ControlStore reservations; a factor-loop launch type is a separate change (backlog note in 05-handoff)."
  ],
  "pre_mortem": [
    "The evaluator silently uses data from the reserved window: the frozen panel ends 2023-12-31 and the evaluator refuses any panel or request reaching 2024-01-01.",
    "A factor peeks ahead and looks brilliant: prefix-invariance at every quarter end plus 2023-12-24 marks it LOOKAHEAD; tests plant shift(-1) and whole-sample z-score factors.",
    "Ties make the replay arbitrary again, as in the first loop: factors with zero cross-sectional spread on more than 5% of days or under 80% coverage are DEGENERATE, never replayed.",
    "RD-Agent's proposer crashes on iteration 2 because result lacks its three labels: result is a Series with them, tested.",
    "The run quietly exceeds its model budget: the launcher refuses --run-max-calls above 60 and the gateway enforces it."
  ],
  "slices": [
    {"title": "Factor runtime profile and setup flag", "files": ["workers/rdagent/install_stock_profile.py", "scripts/setup_rdagent.sh", "tests/unit/test_setup_rdagent.py", "tests/unit/test_native_stock_profile.py"], "verify": "uv run pytest -q -n 0 tests/unit/test_setup_rdagent.py tests/unit/test_native_stock_profile.py", "expected": "pass", "rollback": "revert the files", "status": "pending"},
    {"title": "Factor loop entry and launcher", "files": ["workers/rdagent/factor_loop_entry.py", "workers/rdagent/factor_loop_launch.py", "tests/unit/test_rdagent_factor_launch.py"], "verify": "uv run pytest -q -n 0 tests/unit/test_rdagent_factor_launch.py", "expected": "pass", "rollback": "delete the files", "status": "pending"},
    {"title": "ALPHA evaluator: panel freeze and factor evaluation", "files": ["apps/alpha-cli/src/alpha_cli/rdagent_factor_eval.py", "tests/unit/test_rdagent_factor_eval.py"], "verify": "uv run pytest -q -n 0 tests/unit/test_rdagent_factor_eval.py", "expected": "pass", "rollback": "delete the files", "status": "pending"},
    {"title": "Judge classes, factor data and look-ahead check", "files": ["workers/rdagent/alpha_factor_data.py", "workers/rdagent/alpha_factor_judge.py", "tests/unit/test_rdagent_factor_judge.py"], "verify": "uv run pytest -q -n 0 tests/unit/test_rdagent_factor_judge.py", "expected": "pass (factor-runtime cases skip without ALPHA_FACTOR_PYTHON and ALPHA_RDAGENT_SOURCE)", "rollback": "delete the files", "status": "pending"},
    {"title": "Gate", "verify": "uv run python scripts/gate.py check", "expected": "All checks passed", "rollback": "revert", "status": "pending"}
  ],
  "tier_impact": ["bias", "determinism"],
  "docs_to_update": ["workers/rdagent/README.md", "docs/roadmap/rd-agent-in-alpha.md", "docs/reference/project/components/rd-agent.md"],
  "out_of_scope": ["RD-Agent source", "packages/alpha-research/src/**", "packages/alpha-validation/src/**", "packages/alpha-backtest/src/**", "research_*.py", "scripts/gate*.py", "workers/rdagent/model_gateway.py", "apps/alpha-cli/src/alpha_cli/native_supervisor.py", "the paid route"],
  "files": [
    "workers/rdagent/README.md"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [ADR-0049](../../../../adr/0049-alpha-judges-rdagent-factors.md) | — | always: this plan implements it exactly |
| [worker invariants](../../../../reference/invariants/workers.md) | RD-Agent worker | always |
| [research integrity](../../../../reference/invariants/research-integrity.md) | Decide at close, fill at next open | the evaluator |

Do not read the RD-Agent tree beyond the files named below; the facts needed are stated here.

## What to build

### 1. Factor runtime (`install_stock_profile.py`, `setup_rdagent.sh`)

- `workers/rdagent/factor-requirements.lock` is committed already (do not edit it).
- Generalise `install_stock_profile.py` with `--profile {stock,factor}` (default `stock`; stock
  behaviour, schema `AlphaStockRuntimeProfileV1` and file names byte-for-byte unchanged). `factor`
  uses `factor-requirements.lock`, schema `AlphaFactorRuntimeProfileV1`, writes
  `factor-profile.json` and `dependencies.lock.txt` in the bundle; same exact-pin and inventory checks.
- `scripts/setup_rdagent.sh --with-factor-runtime`: same shape as `--with-stock-runtime`, bundle
  `$runtime/rdagent-factor-py311` with its `.incomplete` / `.built-<stamp>` markers, Python 3.11
  without downloads, `uv pip install --require-hashes --no-deps -r workers/rdagent/factor-requirements.lock`,
  then the profile helper with `--profile factor` (record, then `--verify`). Print
  `export ALPHA_FACTOR_PYTHON=<bundle>/venv/bin/python` (or a "not provisioned" comment). Update
  the header comment. Extend `tests/unit/test_setup_rdagent.py` the way the stock flag is tested.

### 2. Entry and launcher

`workers/rdagent/factor_loop_entry.py` (runs under the factor runtime, `-I -B`): argv
`<source> <loop_n>`. Verify the source with `source_pin.verify_source`, install a meta-path finder
for `rdagent` exactly like `stock_fixture_entry.SourceFinder` (import it from there if that module
is importable without side effects; otherwise copy the 20-line class), add only the
`workers/rdagent` directory to `sys.path` (for `alpha_factor_judge`), then call
`rdagent.app.qlib_rd_loop.factor.main(loop_n=<loop_n>)`. Never put the source root on `sys.path`.

`workers/rdagent/factor_loop_launch.py` (standard library only, run with the repository's
`.venv/bin/python`): `run` subcommand with `--data-dir` (ALPHA data, read only), `--run-dir`
(absolute, must not exist, must not be inside a git work tree; created by the launcher),
`--gateway-data-dir` (absolute, outside git), `--run-id`, `--loop-n` (1–3), `--run-max-calls`
(default 60, refuse more than 60), `--wall-seconds` (default 5400), `--chat-route` and
`--embedding-route` passed to the gateway (`codex`/`ollama` default), `--accept-unhonoured`
(default `temperature`). Paths from the environment: `ALPHA_RDAGENT_SOURCE`, `ALPHA_FACTOR_PYTHON`
(both required; refuse with a plain message naming `scripts/setup_rdagent.sh --with-factor-runtime`).
Steps, each logged as one JSON line to `<run-dir>/launch.jsonl` with a UTC time:
1. `install_stock_profile.py --profile factor --verify <bundle>` and `source_pin.verify_source`;
   record both identities.
2. Freeze: `<repo>/.venv/bin/python -I -m alpha_cli.rdagent_factor_eval freeze --data-dir D --out <run>/panel`.
3. Prepare: `<factor python> -I -B workers/rdagent/alpha_factor_data.py prepare --panel <run>/panel/panel.parquet --out <run>/factor_data`.
4. Gateway: start `<repo>/.venv/bin/python -B workers/rdagent/model_gateway.py serve --data-dir G --run-id R --run-max-calls N --accept-unhonoured A --chat-route .. --embedding-route ..`
   in its own process group, stderr to `<run>/logs/gateway.stderr.log`; wait (≤ 30 s) for
   `G/model-gateway/session.json` written after the launch began; read `base_url` and `token`.
   Never write the token to any log or receipt.
5. Loop: `env -i`-style minimal environment (HOME, USER, LANG=C.UTF-8, TERM=dumb,
   PATH=`<factor venv bin>:/usr/bin:/bin`) plus exactly: `CHAT_MODEL=lm_studio/alpha-chat`,
   `EMBEDDING_MODEL=lm_studio/alpha-embed`, `LM_STUDIO_API_BASE=<base_url>/v1`,
   `LM_STUDIO_API_KEY=<token>`, `LITELLM_LOCAL_MODEL_COST_MAP=True`, `MAX_RETRY=2`,
   `CONDA_DEFAULT_ENV=alpha-no-conda`, `FACTOR_CoSTEER_python_bin=<factor python>`,
   `FACTOR_CoSTEER_max_loop=1`, `FACTOR_CoSTEER_data_folder=<run>/factor_data/full`,
   `FACTOR_CoSTEER_data_folder_debug=<run>/factor_data/debug`,
   `QLIB_FACTOR_SCEN=alpha_factor_judge.AlphaFactorScenario`,
   `QLIB_FACTOR_RUNNER=alpha_factor_judge.AlphaFactorRunner`,
   `QLIB_FACTOR_SUMMARIZER=alpha_factor_judge.AlphaFactorFeedback`,
   `QLIB_FACTOR_TRAIN_START=2017-08-17`, `QLIB_FACTOR_TRAIN_END=2020-12-31`,
   `QLIB_FACTOR_VALID_START=2021-01-01`, `QLIB_FACTOR_VALID_END=2023-12-24`,
   `QLIB_FACTOR_TEST_START=2023-12-25`, `QLIB_FACTOR_TEST_END=2023-12-31` (only so RD-Agent's
   description renders; ALPHA's windows are in the evaluator), `LOG_TRACE_PATH=<run>/work/log`,
   `ALPHA_FACTOR_RUN_DIR=<run>`, `ALPHA_FACTOR_EVAL_PYTHON=<repo>/.venv/bin/python`.
   Command: `<factor python> -I -B workers/rdagent/factor_loop_entry.py <source> <loop_n>`, cwd
   `<run>/work`, own process group, stdout/stderr to `<run>/logs/loop.*.log`.
6. On exit, timeout (`--wall-seconds`) or SIGINT/SIGTERM to the launcher: terminate the loop's
   process group (SIGTERM, then SIGKILL after 10 s), then the gateway's; always.
7. Receipt `<run>/receipt.json`: schema `AlphaRdagentFactorRunReceiptV1`, label
   `exploratory, not admitted, not yet confirmed`, authority flags all false, identities from
   step 1, panel receipt sha256, gateway `status --data-dir G` output for this run id (calls,
   usd), loop exit status and reason, sha256 of `evaluations.jsonl`, start/end times. Exit status
   non-zero when any step failed.

Tests (`tests/unit/test_rdagent_factor_launch.py`, offline): argument refusals (more than 60 calls,
run dir exists or inside a git tree, missing environment variables); the loop environment is exactly
the listed keys (no token in logs or receipt); process-group cleanup on timeout using a stand-in
loop command (allow the test to inject the loop and freeze/prepare commands through a private
function argument, not a CLI flag); gateway start/stop with `--chat-route fake --embedding-route fake`.

### 3. Evaluator (`apps/alpha-cli/src/alpha_cli/rdagent_factor_eval.py`)

Constants (one place, in the record): `RESERVED_START = 2024-01-01`, `PANEL_END = 2023-12-31`,
`EXPLORATION = 2021-01-01 .. 2023-12-24` (evaluated decision dates, inclusive), `CUTS` = quarter
ends 2020-12-31 … 2023-09-30 plus 2023-12-24, `FEE_BPS = 10.0`, `SLIPPAGE_BPS = 6.0` (half spread 1
+ slippage 5, the daily-rule economics), `TOP_FRACTION = 1/3`, `ANNUAL_DAYS = 365`,
`MIN_NAMES = 5`, `Q_THRESHOLD = 0.10`, `BOOTSTRAP_RESAMPLES = 2000`, the label and the survivorship
text of ADR-0049 point 7 verbatim.

`freeze --data-dir D --out DIR`: read every manifest in `D/crypto/manifests/*.json`; keep
`artifact_kind == "normalized"`, dataset family `market_bars`, venue `binance`, market type
`spot`, frequency `1d`, timestamp convention `interval_start_utc`; require quality state
`qualified` with no failures. Read bytes only through
`alpha_cli.crypto_bulk_store.configured_crypto_bulk_store(D).read_verified_normalized(manifest_id, max_bytes=...)`
(it re-hashes). Equal recaptures (same artifact sha256) count once (ADR-0046); two different
artifacts covering the same instrument-day fail loud. Keep rows with open_time < `PANEL_END + 1 day`.
Per instrument: strictly increasing UTC-midnight days with no gaps, finite positive OHLC, finite
non-negative volumes, else `DataError`. Write `DIR/panel.parquet` (columns `date` (date),
`instrument` (e.g. `BTCUSDT`), `open`, `high`, `low`, `close`, `volume` (base), `quote_volume`,
float64, sorted by date then instrument) and `DIR/panel-receipt.json` (manifest ids, artifact
sha256s, rows and first/last day per instrument, panel sha256). Write files exclusively (refuse to
overwrite).

`evaluate --run-dir RUN --request REQ --out OUT`: REQ is JSON written by the runner
(`AlphaRdagentFactorRequestV1`: iteration, hypothesis text sha256, factors: name, code sha256,
status `OK|FAILED|LOOKAHEAD` with the look-ahead detail, values file `factors.parquet` with
columns `date`, `instrument`, one float column per OK factor). Refuse any value dated on or after
`RESERVED_START`, a panel whose receipt's last day reaches it, or a panel sha256 that differs from
the receipt. For each OK factor, on decision dates d in `EXPLORATION`:
- outcome(d, coin) = open(d+2)/open(d+1) − 1 (both bars must exist; else NaN);
- coverage = finite factor values / coin-days in the window; tie share = days with zero
  cross-sectional spread among finite values; status `DEGENERATE` if coverage < 0.8 or tie share
  > 0.05 (p = 1, not replayed);
- daily rank IC with `alpha_research.panel.cross_sectional_ic(signal, outcome, min_names=MIN_NAMES)`
  on dates × instruments matrices; mean, `n`, effective n from
  `alpha_validation.proportion.autocorrelation_effective_size` of the daily IC series, z = mean /
  (sample sd / sqrt(n_eff)), two-sided normal p; 95% stationary-bootstrap interval of the mean
  from `alpha_validation.bootstrap.block_bootstrap_ci` with a seed derived from the factor code
  sha256 (first 8 hex digits as an integer);
- direction = sign of mean IC (recorded as "chosen in-sample");
- replay with `alpha_backtest.portfolio_replay.run_weight_replay`: bars of all instruments from
  the panel over the window's sessions (the rectangle must be complete, else `DataError`);
  `WeightTarget` per decision date d for every coin: score = direction × factor, weight 1/k for
  the top k = round(TOP_FRACTION × names) by score (ties broken by instrument name, recorded) and
  0 otherwise, origin d's session, target d+1's session, available_at as the engine requires
  (state its close-stamp convention in the record; do not change the engine), fee and slippage
  as above; from `ReplayPeriod`: net and gross excess daily returns; annualised mean × 365,
  compounded, Sharpe × sqrt(365), max drawdown of the compounded excess curve, mean turnover;
- family: the run ledger `RUN/evaluations.jsonl` (all prior records) plus this request; every
  factor of every iteration in order, FAILED/LOOKAHEAD/DEGENERATE with p = 1; q-values by
  `alpha_validation.proportion.benjamini_hochberg` over the whole family; Deflated Sharpe of each
  replayed factor's daily net excess returns with `alpha_validation.dsr.deflated_sharpe`, trials =
  every replayed factor's per-observation Sharpe so far.
- ALPHA decision: True iff some factor of this iteration has q < `Q_THRESHOLD`, status OK and
  annualised net excess > 0; lead factor = lowest q (ties by name).
- `legacy_result` for RD-Agent's proposer: `IC` = lead factor's mean rank IC,
  `1day.excess_return_without_cost.annualized_return` = its gross (no-cost) annualised excess,
  `1day.excess_return_without_cost.max_drawdown` = its gross excess max drawdown (NaN when no
  factor was replayed), plus the same with-cost keys.
- Record `AlphaRdagentFactorEvaluationV1` to OUT and appended to `RUN/evaluations.jsonl` (one
  canonical JSON line, sorted keys): label, authority flags all false (`admitted`, `evidence`,
  `approval`, `promotion`), disclosures (survivorship, multiple testing "screening only, adaptive
  family, no error rate claimed", direction, windows, reserved window, costs, replay engine "ALPHA
  canonical synchronized replay, not Nautilus", look-ahead check scope), inputs (panel sha256,
  request sha256, factors sha256, evaluator fingerprint = sha256 of this module's bytes and the
  repository `uv.lock`), per-factor metrics and statuses, family size, q-values, decision, lead
  factor, `legacy_result`, and `feedback_text`: a short plain-English rendering of all of this that
  begins with the label and includes the survivorship sentence and the family size. No wall-clock
  time in the record: identical inputs and ledger give identical bytes.

Tests (`tests/unit/test_rdagent_factor_eval.py`, synthetic panels written in `tmp_path`, no real
data): oracle — a factor equal to a planted component of the next-open-to-next-open return plus
noise on 15 coins over the window is OK, q < 0.10, positive net excess, decision True; a pure-noise
factor (several fixed seeds) is not significant and decision False; determinism — two evaluations
of the same request and ledger are byte-identical; family grows across iterations and FAILED /
LOOKAHEAD entries count with p = 1; DEGENERATE for a constant factor; refusal of reserved-window
dates and of a tampered panel; the record carries the label, survivorship text and all-false
authority; `freeze` on a two-coin synthetic manifest store (build it through the same store API the
existing crypto tests use) and its gap/overlap refusals.

### 4. Judge (`alpha_factor_data.py`, `alpha_factor_judge.py`), Python 3.11, factor runtime

`alpha_factor_data.py` (pandas only, no rdagent import, also a script):
- `prepare --panel P --out DIR`: `DIR/full/daily_pv.h5` (all panel rows), `DIR/debug/daily_pv.h5`
  (2021-01-01..2022-12-31), key `data`, index `(datetime, instrument)` sorted, columns `$open`,
  `$close`, `$high`, `$low`, `$volume`, `$factor` (= 1.0), float64; a `README.md` in both written
  in RD-Agent's format (how to read; file table; field meanings) that says plainly: 15 Binance USDT
  spot coins, daily bars, row d is the bar that opened at 00:00 UTC on day d and is known at its
  close, `$volume` is base-asset volume, `$factor` is 1 (no adjustments), data ends 2023-12-31;
  and `DIR/cuts/<YYYY-MM-DD>/daily_pv.h5` = full truncated at each cut (inclusive), plus a
  `prepare-receipt.json` with sha256 of every file.
- `check_prefix_invariance(code: bytes, full_values: DataFrame, cuts_dir: Path, python_bin: str, timeout: float) -> dict`:
  for each cut, copy `factor.py` into a fresh temp dir, symlink that cut's `daily_pv.h5`, run
  `python_bin factor.py` (cwd = temp dir, minimal env, timeout), read `result.h5`; compare every
  value dated ≤ cut with `full_values` (same NaN positions; finite values equal within
  rtol 1e-9, atol 1e-12). Return `{"status": "PASS"|"LOOKAHEAD"|"ERROR", "cuts": [...], "first_mismatch": {...}}`.
  A failed truncated run is `ERROR` and is treated as LOOKAHEAD by the runner (fail closed).

`alpha_factor_judge.py` (imports rdagent; read only these upstream files if you need signatures:
`rdagent/scenarios/qlib/experiment/factor_experiment.py`, `rdagent/scenarios/qlib/developer/feedback.py`,
`rdagent/core/developer.py`, `rdagent/core/proposal.py`):
- `AlphaFactorScenario(QlibFactorScenario)`: override the `simulator` and `experiment_setting`
  properties with ALPHA's description (the windows, the next-open label, the replay and costs,
  "a factor is judged by ALPHA's rank IC with inference and a cost-aware replay; there is no Qlib
  model"); everything else inherited.
- `AlphaFactorRunner(Developer)`: `develop(exp)`. An experiment without sub-tasks (RD-Agent's
  baseline) gets a `legacy_result`-shaped Series of NaN and `stdout` "baseline: no factors; ALPHA
  evaluates factors standalone", without calling the evaluator; when `exp.based_experiments[-1]`
  has no result, develop it first (as upstream does). Otherwise for each
  `(workspace, feedback)` in `zip(exp.sub_workspace_list, exp.prop_dev_feedback)`: if both are
  truthy, `workspace.execute("All")` → values or FAILED; prefix-invariance for each OK factor using
  `<run>/factor_data/cuts`; write `<run>/evaluations/iter-<k>/factors.parquet` and `request.json`
  (k = number of lines already in `evaluations.jsonl`), run `ALPHA_FACTOR_EVAL_PYTHON -I -m
  alpha_cli.rdagent_factor_eval evaluate ...` (timeout 1800 s; non-zero exit raises
  `rdagent.core.exception.FactorEmptyError` with the evaluator's last error line), read the record;
  `exp.result = pd.Series(record["legacy_result"])`; `exp.stdout = record["feedback_text"]`;
  keep the record on the experiment as `exp.alpha_evaluation`. If every factor FAILED, raise
  `FactorEmptyError` (upstream's own skip path) after the evaluator recorded the failures.
- `AlphaFactorFeedback(Experiment2Feedback)`: render RD-Agent's own prompts exactly as
  `QlibFactorExperiment2Feedback.generate_feedback` does (same templates, same JSON call), but pass
  `combined_result=exp.stdout` (ALPHA's feedback text) instead of the Qlib comparison; build
  `HypothesisFeedback` from the reply as upstream does, then set `decision` to the record's ALPHA
  decision; append to `<run>/feedback.jsonl` one line with the iteration, the model's
  `Replace Best Result` value, ALPHA's decision and sha256 of the reply (no reply text).

Tests (`tests/unit/test_rdagent_factor_judge.py`): offline unit tests of the pure comparison logic
importable in the root environment if pandas is available (it is); factor-runtime cases skipped
unless `ALPHA_FACTOR_PYTHON` and `ALPHA_RDAGENT_SOURCE` are set, run as subprocesses with that
Python: `prepare` on a tiny synthetic panel; prefix invariance passes a causal 5-day momentum
`factor.py` and marks LOOKAHEAD for a `shift(-1)` factor and a whole-sample z-score factor;
importing `alpha_factor_judge` through the entry's finder succeeds and the three classes subclass
the upstream classes; `AlphaFactorFeedback` with a stubbed `APIBackend` returns ALPHA's decision,
not the model's.

## Test plan

As listed per slice; the gate runs them. The bias guard is the reserved window (refused by
construction) and the prefix-invariance check; determinism is the byte-identical record test.

## Look-ahead, determinism and import impact

Decision at the close of day d, fill at the open of d+1, exit at the open of d+2. Nothing reads
data on or after 2024-01-01. Bootstrap seeds derive from content hashes. `alpha_cli` may import
every package it uses here; `workers/rdagent` imports no ALPHA package (the evaluator is a
subprocess).
