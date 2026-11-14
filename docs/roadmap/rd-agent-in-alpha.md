# RD-Agent in ALPHA: what is real today and what is still missing

Written 2026-11-14 for the owner, after RD-Agent was installed and run on the Dell for the first
time, and updated the same day after the daily study's Docker image, the stock loop's runtime,
your storage decision and the first full loop through an AI model on real data. Every statement
below comes from the repository or from those runs; anything not checked is marked "not verified".

## What RD-Agent is and what it does in ALPHA

RD-Agent is Microsoft's open-source AI research assistant. It runs a research loop over and over:
come up with an idea, turn it into an experiment, run it, judge the result, remember it, repeat.
ALPHA uses one fixed version of it (upstream commit `484776c`, checked file by file), unchanged.
In ALPHA the jobs are split: RD-Agent drives the loop; ALPHA keeps the budget, the data, the
backtests, the statistics and your approvals.

1. **Your idea.** You write a research question and approve its contract (what will be tested,
   on which data, with what budget).
2. **RD-Agent proposes an experiment.** Normally an AI model writes a concrete hypothesis.
3. **The experiment is built.** Qlib (Microsoft's stock-prediction toolkit) trains a model, or a
   trading rule is written.
4. **ALPHA backtests it** with Nautilus (the trading simulator ALPHA uses), including costs.
5. **ALPHA's statistical checks** judge the result; RD-Agent records the feedback for the next round.
6. **Your decision.** Nothing becomes evidence until you admit it. Every result so far is labelled
   "synthetic" and "not admitted".

## The parts that exist

- **AI stock research loop** (card 7). Starts RD-Agent's own stock research loop on a task and
  afterwards checks exactly what ran and recovers the result. It now runs on the Dell, but only
  on made-up inputs with stand-in steps (no AI model).
- **Daily trading-rule study, "Packet 3"** (card 9). One fixed study you already approved: a
  20-day momentum rule against a "do nothing" control on Binance BTC/USDT daily bars, 2020–2022.
  RD-Agent's loop runs the steps; no AI model is involved. Today it has run only on a 7-bar
  made-up dataset (now including its locked Docker container on the Dell); the real-data run has
  not started.
- **Native job result screen** (card 8). Workstation → View → Research → Native job result: type a
  job number, read its result. On the Dell it now reads made-up stock jobs end to end; no real job
  exists yet.

## What is real today

Run on the Dell on 2026-11-14:

- RD-Agent's own code, byte-identical to the pinned version (all 694 files checked): its loop
  engine (the part that runs the five steps in order, saves a checkpoint after each step and
  reloads it), and its core research records (hypothesis, experiment, trace, feedback, logging).
- ALPHA's controls around it: budget reservation before launch, a single owning process,
  cancellation, signed checkpoints, and refusal to resume twice.
- For the daily rule: ALPHA's real rule code, its real backtest engine and Nautilus 1.228, on the
  made-up bars.
- For the daily study: its one locked Docker image (`python:3.12-slim`, fixed by its SHA-256
  checksum) was downloaded and checked on the Dell. All 13 daily-study tests that used to fail
  here now pass; on a machine without the image they are skipped with a clear reason instead.
- For the stock loop: a fixed list of 60 exact package versions, each with its checksum, now
  lives in the repository (`workers/rdagent/stock-requirements.lock`, Python 3.11, the version
  RD-Agent itself is tested on). Built on the Dell, RD-Agent's own stock research loop runs; 22 of
  its 23 tests pass. The 23rd drives a real browser and fails here only because the web front
  end's test packages are not installed on the Dell (not verified beyond that).
- 85 of the 86 tests that had always been skipped now run and pass here. Both smoke checks (end
  to end through the installed programs) pass: RD-Agent's general loop and its stock loop run,
  then `alpha` and the web app show the job and its result.
- **One full loop with an AI model, on real data — but its backtest saw nothing.** RD-Agent's own
  factor loop, unmodified, ran once end to end through the model gateway on the Codex route: the
  model proposed four simple daily factors, wrote their code, RD-Agent's checks accepted all four,
  Qlib (in RD-Agent's own Docker image) trained its model and backtested, and the model judged
  the result. Data: the real Binance daily bars for 15 coins on the Dell, 2017–2026, read only.
  27 model calls (60 allowed), no money, about 4.5 minutes. The backtest was hollow: RD-Agent's
  built-in model settings, tuned for about 300 Chinese stocks, gave every coin the same score
  every day, so the profit figures are noise and the "keep it" verdict rests on noise. This run
  was set up by hand outside the repository; no ALPHA job runs it
  ([verification](../work/archive/2026-11/2026-11-14-rdagent-first-real-loop/04-verify.md)).

## What is still made-up

- **No AI model in ALPHA-run jobs.** In the fixture and stock loops the "propose" step returns a
  fixed hypothesis. The one model-driven loop above was run by hand, not as an ALPHA job.
- **No real tools or code writing.** In the stock loop the "coding" step writes nothing; model and
  tool calls are counted but fake.
- **No real data in ALPHA-run jobs.** The rule study uses 7 invented daily bars; the stock loop
  uses fixed numbers. (The hand-run loop above used real bars.)
- **Supplied answers.** Outcomes such as SUPPORTED or CONTRADICTED and every metric (for example
  a net return of −12.5%) are typed into the test, not computed from markets.
- **Test approvals.** The approvals in these runs are test records in a throwaway store, not yours.

## What stands between today and RD-Agent researching real ideas

1. ~~A runtime for RD-Agent's full stock loop.~~ Done 2026-11-14: the pinned package list above,
   installed with `bash scripts/setup_rdagent.sh --with-stock-runtime`.
2. ~~An AI model connection.~~ Built 2026-11-14 ([ADR-0044](../adr/0044-rdagent-model-gateway.md)):
   a small local program, `workers/rdagent/model_gateway.py`, that only the Dell can reach. RD-Agent
   asks it for answers; it passes each request to the Codex program you are signed in to with
   ChatGPT and gets text comparisons from Ollama, keeps a hard budget, and records every call
   without its text. No key is stored. Measured answers:
   [verification](../work/archive/2026-11/2026-11-14-rdagent-model-gateway/04-verify.md). You
   accepted, for now, that the Codex route cannot use RD-Agent's "temperature" setting
   ([log](../reference/project/owner-decisions-2.md#2026-11-14-accept-losing-temperature-on-the-codex-route-for-now));
   it is recorded on every call. The paid fallback stays off until you set a key yourself and
   compare it.
2b. **A backtest that can see the idea — new, needs your choice.** The first full loop (see
   "What is real today") showed that RD-Agent's built-in Qlib backtest is tuned for about 300
   Chinese stocks: on 15 coins its model learns nothing, so its numbers are noise. Choose one:
   a wider crypto universe (how wide is enough is untested; needs item 3's data folder and a
   bigger download); ALPHA judging RD-Agent's factors with Nautilus and its statistical checks (the
   intended design; engineering, overlaps item 6); or, as a calibration only, one run on Qlib's
   public Chinese-stock data (a download). RD-Agent's own settings files stay unmodified. Also
   engineering: pin the extra Python packages, the Qlib image and the launcher this run set up by
   hand ([handoff](../work/archive/2026-11/2026-11-14-rdagent-first-real-loop/05-handoff.md)).
3. **A place to keep the data — your decision is in, one command is left.** You decided on
   2026-11-14 to use the Dell's disk for now. The free-space reserve is now a value you set per
   data folder ([ADR-0043](../adr/0043-storage-reserve-is-owner-set.md)): the old rule (keep
   100 GB or 15% free) stays the default, and for the Dell the setting is "keep 10 GB free, warn
   below 20 GB". 10 GB is a hard minimum nobody can set lower. ALPHA still refuses to write data
   that would take free space below the reserve, and `scripts/gate.py doctor` warns when space is
   low. The Docker image is done (see above). *From you:* choose the data folder and run the one
   command in [storage settings](../operations/storage-settings.md); nothing has been created
   for you. Note: the daily study's start checks the storage identity, not free space.
4. **Real market data admitted into the study.** The plans say the real run is "blocked on admitted
   retained storage": the Binance bars may only be downloaded into, and frozen from, storage that
   item 3 sets up. Separately, the map says a data provider for your Mac has been blocked since
   31 August (which one: not verified). *From you:* item 3's decision, then your confirmation of
   the study at the start.
5. **Restart after a crash ("T07").** If the owning process dies mid-study, a new process cannot
   continue it; the job stays unresolved and its budget stays spent. Engineering work only.
6. **RD-Agent driving the Qlib worker ("W09").** Route ALPHA's existing Qlib LightGBM model through
   RD-Agent's experiment, runner and feedback steps. It depends on one real study (item 4) first.
7. **Regular checking.** None of these tests run in CI: CI has no RD-Agent installed and the gate
   has no RD-Agent component (backlog item "Gate coverage for workers/rdagent"). Changing CI is a
   protected change. *From you:* acknowledgement to add it.

## How to see it

From the repository folder on the Dell:

```sh
bash scripts/setup_rdagent.sh --with-daily-container --with-stock-runtime  # once; prints exports
export ALPHA_RDAGENT_SOURCE="$PWD/.alpha/state/runtime/rdagent-source"
export ALPHA_STOCK_PYTHON="$PWD/.alpha/state/runtime/rdagent-stock-py311/venv/bin/python"
export ALPHA_STOCK_RECEIPTS="$(mktemp -d)"
uv run python scripts/run_owned_test.py -- uv run pytest -q -m smoke -n 0 tests/smoke/test_rdagent_smoke.py
```

Both checks pass on the Dell. Without the two flags the install is about 1.1 GB; the image adds
about 120 MB and the stock runtime about 230 MB. To read a stock
job's result once one exists: `uv run alpha research diagnostic native-result --data-dir … --job-id …
--profile-source … --profile-runtime … --profile-mode resume`, or the Native job result screen.
Technical detail: [worker README](../../workers/rdagent/README.md).
