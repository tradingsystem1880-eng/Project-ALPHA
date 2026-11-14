## What changed for you

- RD-Agent ran its whole research loop once, for real, on the Dell: an AI model (through the Codex
  route you use with ChatGPT) proposed an idea, RD-Agent had the model write the code, checked it,
  had Qlib train a model and backtest it, and had the AI judge the result. It used the real Binance
  daily bars for 15 coins already on the Dell (read only). 27 model calls, no money spent, about
  4.5 minutes. Nothing is evidence; everything is labelled exploratory and not yet confirmed.
- The idea: four simple daily signals (5-day reversal, 20-day volatility, recent versus usual
  trading volume, and the day's open-to-close move). All four were written and accepted first time.
- The catch: the backtest was hollow. RD-Agent's built-in model settings are tuned for 300 Chinese
  stocks. On 15 coins its model learned nothing and gave every coin the same score every day, so
  the backtest's profit numbers are noise (two identical runs even gave different numbers), and the
  AI's verdict ("improved, keep it") rests on that noise. A side check outside the loop shows one
  of the four signals (volatility) does line up with next-day returns across the coins, so there
  was something to find; the built-in model just could not use it. That side check is a lead, not
  a finding.
- No code in the repository changed. The run and its records are in
  `/home/hunta/alpha-clean-base/runs/2026-11-14-rdagent-first-real-loop/`.

## What stands between this and a routine real loop

1. **A backtest that can see the idea (your decision).** Pick one:
   a. a wider crypto universe (about 100 coins or more), so RD-Agent's built-in settings fit; this
      needs the data folder you choose in
      [storage settings](../../../../operations/storage-settings.md) and a bigger download;
   b. have ALPHA judge RD-Agent's factors with its own tools (Nautilus backtest plus the
      statistical checks), as the intended design says; this is engineering work ("W09" and
      beyond), no download;
   c. as a calibration only, run RD-Agent once on Qlib's public Chinese-stock data, the data its
      settings were made for (a download of a few hundred MB from Qlib's published dataset).
   Changing RD-Agent's own settings files is not an option: it stays pinned and unmodified.
2. **A repeatable install (engineering).** This run used things set up by hand in the run folder:
   extra Python packages not pinned by checksum, RD-Agent's Qlib image built from its own
   Dockerfile (not reproducible byte for byte; 10.9 GB), an MLflow switch that image needs, and a
   small stand-in for `conda`. These should become a hash-pinned lock, a pinned image and a
   launcher started by `alpha` under its job supervisor (budget, cancel, records).
3. **Crypto conventions (engineering, then your review).** Qlib annualises with 252 days, uses
   Chinese trading costs and trades at the next day's close; ALPHA fills at the next open. Either
   reconcile these or leave the backtest to Nautilus (option 1b).
4. Already listed: restart after a crash, and regular checking in CI
   ([roadmap](../../../../roadmap/rd-agent-in-alpha.md#what-stands-between-today-and-rd-agent-researching-real-ideas)).

## How to see it

On the Dell: `work/log` in the run folder is RD-Agent's own log (readable with RD-Agent's log
viewer); `gateway/model-gateway/calls.jsonl` lists every model call; `04-verify.md` here has the
numbers. To repeat the run: start the gateway as in the
[worker README](../../../../../workers/rdagent/README.md#model-gateway-2026-11-14), then
`bash scripts/run_loop.sh` in the run folder.

## Checks run

- The run's own records, and a direct look at the model's predictions (constant).
- `uv run python scripts/gate.py check` and `uv run python scripts/fs.py stale` (0): see the pull
  request.
