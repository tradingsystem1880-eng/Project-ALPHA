# Verification: an RD-Agent loop that ALPHA judges

Run on the Dell on 2026-11-14, 10:54:45 to 11:01:41 UTC, by one command (below). Records:
`/home/hunta/alpha-clean-base/runs/2026-11-14-rdagent-alpha-judged-loop/` (outside every git
tree) and the shared trial ledger
`/home/hunta/alpha-clean-base/runs/rdagent-trial-ledger/rdagent-factor-trials.jsonl`.
Labels: **exploratory, not admitted, not yet confirmed.** 15 coins chosen in 2026-11 from today's
survivors; delisted or collapsed coins (for example LUNA, FTT) are absent, which biases results
upward. Nothing here is evidence.

## Verdict

The loop ran three iterations end to end with every step real: RD-Agent (pinned `484776c`,
unmodified) proposed and coded five factors through the model gateway on the Codex route; ALPHA
checked each for look-ahead, screened each on the exploration window, replayed the two that passed
the screen, and gave RD-Agent its verdicts. **No factor became a candidate.** Two factors had a
strong, well-measured rank relationship with next-open-to-next-open returns, but a long-only
portfolio built from them lost money against the equal-weight basket after costs. That is a real
measurement, unlike the first loop's, and a null for the loop's decision rule.

## The run, step by step

| Step | What happened | Record |
|---|---|---|
| Verify | Factor runtime profile re-verified (identity `4bc3fec4…`); RD-Agent source tree digest `0266b2d6…` | `launch.jsonl`, `receipt.json` |
| Freeze | 1,426 qualified Binance spot daily manifests re-hashed (one equal recapture counted once), 15 coins, 27,656 bars up to 2023-12-31, no gaps; panel sha256 `6442e00e…` | `panel/panel-receipt.json` |
| Prepare | RD-Agent's `daily_pv.h5` (full, debug 2021–2022) and 13 truncated copies for the look-ahead check | `factor_data/prepare-receipt.json` |
| Gateway | Codex route, 60-call cap, `temperature` waived as the owner accepted | `logs/gateway.stderr.log` |
| Loop | 3 iterations; RD-Agent's proposer saw the ledger summary from iteration 2 on | `work/log`, `evaluations/iter-*` |
| Stop, receipt | Gateway and loop stopped; exit 0 | `receipt.json` |

## What was measured

Exploration window: decisions 2021-01-01 to 2023-12-24 (1,088 scored days, all 15 coins every
day); outcome = open(d+2)/open(d+1) − 1; screen threshold BH q < 0.10 over the ledger; replay:
long the top third by the factor in the direction of its mean rank IC (chosen in-sample),
equal-weight, daily at the next open, 10 bps fee and 6 bps spread plus slippage per side, against
the equal-weight basket of the 15 coins.

| Iter | Factor | Look-ahead check | Mean rank IC (95% bootstrap) | p | q (family size) | Stage, status |
|---|---|---|---|---|---|---|
| 0 | `momentum_7d` | pass, 13 cuts | −0.018 (−0.034, −0.001) | 0.070 | 0.106 (3) | screen fail |
| 0 | `range_fraction_7d` (7-day mean of (high − low)/close) | pass | −0.077 (−0.098, −0.057) | about 4e-11 (z −6.6) | about 1e-10 (3) | replayed, **replay fail** |
| 0 | `relative_volume_7d` | pass | −0.015 (−0.033, +0.003) | 0.118 | 0.118 (3) | screen fail |
| 1 | `volume_weighted_close_location_7d` | pass | −0.001 (−0.016, +0.015) | 0.871 | 0.871 (4) | screen fail |
| 2 | `range_fraction_28d` | pass | −0.068 (−0.090, −0.048) | about 3e-9 (z −6.0) | about 1e-8 (5) | replayed, **replay fail** |

Replays (calmest third of coins, annualised with 365 days):

| Factor | Net excess, arithmetic | Net excess, compounded over the window | Net Sharpe | Max drawdown | Mean daily turnover | Gross excess, arithmetic |
|---|---|---|---|---|---|---|
| `range_fraction_7d` | −5.5% a year | −31.3% | −0.14 | −59.8% | 0.19 | +5.8% a year |
| `range_fraction_28d` | −34.3% a year | −69.3% | −1.09 | −69.3% | 0.07 | −30.0% a year |

Deflated Sharpe: 0.41 and 0.003 (replayed trials 1 and 2); against the whole family of five,
0.0001 for the 28-day factor. Effective sample sizes were close to n (little serial correlation in
the daily IC series).

What this does and does not show:

- It shows that, day by day, calmer coins tended to beat wilder ones on the next open-to-open
  return in 2021–2023 (the same pattern the first loop's side check saw in a 20-day volatility
  factor). The rank IC treats every coin-day equally.
- It shows that the long side alone does not pay on these 15 coins: the arithmetic gross edge of
  the 7-day factor (+5.8%) is eaten by costs (turnover 0.19 a day), and in compounded terms it
  already lost before costs. The 28-day factor lost heavily. A likely reason, **not measured
  here**: the rank IC weighs every coin-day equally, while the portfolio's return is dominated by
  a few very large moves of the wildest coins (2021 especially), which a calm-coins long-only book
  misses and cannot short. Decomposing this (by year, by long and short side) is the obvious next
  measurement, and it would itself be another trial.
- It does not show a tradable edge, it says nothing about 2024 onward (locked), and five factors
  from one family of ideas on 15 surviving coins are a narrow search.

## Model use and cost

37 gateway calls, all status 200: 29 chat on the Codex route (`gpt-6.1-sol`, effort medium,
`temperature` waived on every call) and 8 embeddings on Ollama `nomic-embed-text`; 156,895 input
and 7,162 output tokens; 0 USD. Cap 60 per run. The model's own "replace best result" answer was
"no" in all three iterations, agreeing with ALPHA's decision (`feedback.jsonl`).

## Determinism and integrity checks on the real run

- Re-running ALPHA's evaluator on iteration 0's request with an empty scratch ledger gave a
  byte-identical record and byte-identical ledger lines. That re-check appended a duplicate of the
  record to the run's `evaluations.jsonl` by mistake (the evaluator writes the run's record file
  as well as the ledger); the duplicate line was removed and the file's sha256 again equals the
  receipt's (`NOTE-determinism-check.txt` in the run folder). The trial ledger was not touched.
- No factor tripped the look-ahead check; the check itself was shown on the Dell to catch a
  one-day forward shift and a whole-sample z-score (`tests/unit/test_rdagent_factor_judge.py`).
- No ALPHA factor was evaluated outside the loop, so the ledger's five trials are the whole search.

## Tests

- `tests/unit/test_rdagent_factor_eval.py` (root environment, synthetic panels): a planted signal
  is a candidate with q < 0.10 and positive net excess; noise factors never reach the replay; the
  screen's false-positive rate on pure noise is about its nominal level (calibration: 4.0% of 300
  noise factors at p < 0.05, 9.0% at p < 0.10, 1.3% at p < 0.01; the test asserts at most 20% at
  0.10 over 80); byte-identical records; repeats across runs; failures, look-ahead and degenerate
  factors count in the family; one failing factor is recorded as ERROR without losing the others;
  a day with too few names is degenerate; reserved-window values, a panel reaching 2024 and a
  tampered panel are refused.
- `tests/unit/test_rdagent_factor_judge.py`: prefix comparison; with `ALPHA_FACTOR_PYTHON` and
  `ALPHA_RDAGENT_SOURCE` set (run on the Dell, skipped elsewhere): data preparation, look-ahead
  caught, the classes subclass upstream's, ALPHA's decision overrides the model's, and the runner
  gives RD-Agent's proposer a result with the three labels it reads.
- `tests/unit/test_rdagent_factor_launch.py`: refusals (more than 60 calls, existing run folder,
  inside a git tree, missing runtime), the exact loop environment, process-group cleanup, a gateway
  start with fake routes, the token kept out of logs and receipt.
- A launcher run with fake model routes on the real data got through verify, freeze, prepare,
  gateway start and RD-Agent's scenario set-up, then stopped at the first model answer as expected
  (fake answers are not RD-Agent's JSON).
- `uv run python scripts/gate.py check`: all checks passed.

## Not verified

- `freeze`'s refusals of gapped or overlapping artifacts have no test (the real-data freeze ran).
- The launcher's wall-clock timeout path and a cancel by signal were not exercised end to end.
- Resume of a crashed loop from RD-Agent's checkpoint.
- Whether the screen's inference stays calibrated for factors with strong serial correlation in
  their daily IC (the calibration used independent noise).

## Review findings and how each was handled

Independent Claude review of the code diff (four high, four medium, four low):

- High, fixed: a day with fewer than five names crashed the replay and lost the whole request's
  trials (now `DEGENERATE` before replay, and any per-factor error is recorded as `ERROR`, p = 1);
  a failed evaluation collided with the next iteration's folder (now numbered by folders made);
  some launcher failures wrote no receipt (now every failure stops the children and writes one,
  and a second signal cannot abort the clean-up); a process group whose leader had exited was not
  stopped (now every group is signalled).
- Medium, fixed: the Deflated Sharpe counted only replayed trials (a second figure now deflates
  against the whole family's size); a multi-column factor crashed the loop (now `FAILED`);
  generated factor code could read the gateway token (now stripped from its environment). Medium,
  partly open: missing tests for `freeze` refusals and the timeout path (listed above).
- Low, fixed: ledger rows' status and stage are validated; the proposer's ledger summary reads only
  complete lines; the receipt's gateway figures are this run's. Low, accepted: verdicts in the
  ledger are as of their time (later trials can only raise a q-value; the record says so); a factor
  that once failed is a repeat for ever (conservative). Low, disclosed: `scripts/gate.py` (a
  protected file) gained one doctor item, outside the builder's scope, built by Claude.
- Earlier, on the decision record: two Codex review findings (look-ahead cut coverage; BH over an
  adaptive family claims no error control), both fixed in ADR-0049.
