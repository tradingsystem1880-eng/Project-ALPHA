# RD-Agent in ALPHA: what is real today and what is still missing

Written 2026-11-14 for the owner, after RD-Agent was installed and run on the Dell for the first
time. Every statement below comes from the repository or from that run; anything not checked is
marked "not verified".

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
  afterwards checks exactly what ran and recovers the result. Today it only runs on made-up inputs,
  and it could not run on the Dell (see "What is still missing", item 1).
- **Daily trading-rule study, "Packet 3"** (card 9). One fixed study you already approved: a
  20-day momentum rule against a "do nothing" control on Binance BTC/USDT daily bars, 2020–2022.
  RD-Agent's loop runs the steps; no AI model is involved. Today it has run only on a 7-bar
  made-up dataset; the real-data run has not started.
- **Native job result screen** (card 8). Workstation → View → Research → Native job result: type a
  job number, read its result. It answers today, but says "unavailable" until a stock job exists.

## What is real today

Run on the Dell on 2026-11-14:

- RD-Agent's own code, byte-identical to the pinned version (all 694 files checked): its loop
  engine (the part that runs the five steps in order, saves a checkpoint after each step and
  reloads it), and its core research records (hypothesis, experiment, trace, feedback, logging).
- ALPHA's controls around it: budget reservation before launch, a single owning process,
  cancellation, signed checkpoints, and refusal to resume twice.
- For the daily rule: ALPHA's real rule code, its real backtest engine and Nautilus 1.228, on the
  made-up bars.
- 50 of the 86 tests that had always been skipped now run and pass. The new smoke check (an
  end-to-end check through the installed programs) passes: RD-Agent's loop runs, then `alpha` and
  the web app both show the job.

## What is still made-up

- **No AI model.** The "propose" step returns a fixed hypothesis; no model is called anywhere.
- **No real tools or code writing.** In the stock loop the "coding" step writes nothing; model and
  tool calls are counted but fake.
- **No real data.** The rule study uses 7 invented daily bars; the stock loop uses fixed numbers.
- **Supplied answers.** Outcomes such as SUPPORTED or CONTRADICTED and every metric (for example
  a net return of −12.5%) are typed into the test, not computed from markets.
- **Test approvals.** The approvals in these runs are test records in a throwaway store, not yours.

## What stands between today and RD-Agent researching real ideas

1. **A runtime for RD-Agent's full stock loop.** Its loop needs at least six more upstream packages
   (Docker client, Rich, NumPy, OpenAI, tiktoken, LiteLLM) plus their dependencies; no file in the
   repository pins them to exact versions for this runtime, so they were not installed. *From you:* approval to add one pinned package list.
2. **An AI model connection.** Pinned RD-Agent reads its model from settings named `CHAT_MODEL`,
   `EMBEDDING_MODEL` and `BACKEND` (LiteLLM by default), with the provider address and key in
   `OPENAI_API_BASE`/`OPENAI_API_KEY` (or `CHAT_OPENAI_BASE_URL`/`CHAT_OPENAI_API_KEY`, Azure
   variants, and `LITELLM_`-prefixed copies); its own command line reads them from a `.env` file.
   ALPHA's workers deliberately clear these settings and block the network today, so connecting a
   model is also engineering work. *From you:* which provider, a spending limit, and the key,
   entered by you, never written into the repository.
3. **A permanent place to run long studies.** Studies must live on retained, non-temporary storage
   with a free-space reserve of at least 100 GB (or 15%, whichever is larger), recorded in a
   storage settings file. The Dell has about 48 GB free, so as configured it does not qualify.
   The daily study also needs one fixed Docker image (`python:3.12-slim`, pinned by its SHA-256
   checksum) checked by `workers/rdagent/qualify_daily_container.py`; it is not on the Dell, so the
   13 daily-study tests fail here. *From you:* which machine and disk, and permission to download
   that one image.
4. **Real market data admitted into the study.** The plans say the real run is "blocked on admitted
   retained storage": the Binance bars may only be downloaded into, and frozen from, storage that
   item 3 approves. Separately, the map says a data provider for your Mac has been blocked since
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
bash scripts/setup_rdagent.sh        # once; prints the export line below
export ALPHA_RDAGENT_SOURCE="$PWD/.alpha/state/runtime/rdagent-source"
uv run python scripts/run_owned_test.py -- uv run pytest -q -m smoke -n 0 tests/smoke/test_rdagent_smoke.py
```

The first check passes; the second (stock loop) is skipped until item 1 exists. To read a stock
job's result once one exists: `uv run alpha research diagnostic native-result --data-dir … --job-id …
--profile-source … --profile-runtime … --profile-mode resume`, or the Native job result screen.
Technical detail: [worker README](../../workers/rdagent/README.md).
