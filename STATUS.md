# ALPHA status

_Generated — do not edit; run: `uv run python scripts/status.py`_

## At a glance

- **Capabilities:** 19 working, 14 partly working, 1 demo only, 1 shelved, 2 not started.
- **Work in progress:** 41 in progress (limit 3).
  - 5 being worked on
  - 36 built but not yet checked end to end
  - Not counted: 3 blocked, 1 planned, not started.
  - Allowed for now: 41. This number only goes down, until it reaches 3.
- **Decisions waiting for you:** 22.

"Working" means a test runs it from start to finish on made-up (synthetic) data.
Runs on real market data are still to be confirmed on the Mac, except where noted.

## What works today

- **Workstation web app** — uv run alpha-web, then open http://localhost:8801
- **Price charts with indicators and patterns** — Workstation: View → Chart (a real run is recorded)
- **Download and freeze stock and ETF prices** — uv run alpha data pull SPY --source tiingo --start 2020-01-01 --end 2020-12-31
- **Download crypto market data (W05)** — uv run alpha crypto-data catalog (a real run is recorded)
- **Crypto history download that resumes safely (backfill, Phase B)** — uv run alpha crypto-data backfill bybit <family> --symbols BTCUSDT --quote USDT --start … --end … --ledger <name> --dry-run
- **"Are my downloaded daily bars complete?" check** — uv run alpha crypto-data quality <manifest-id> --coverage-start … --coverage-end … --as-of …
- **Freeze crypto data into exact snapshots and check them (W05)** — uv run alpha crypto-data snapshot-create …, then uv run alpha crypto-data snapshot-verify <snapshot-id>
- **Run a backtest** — uv run alpha backtest run SPY
- **Reports, figures and run comparison** — uv run alpha report <run-id>
- **Write trading rules and scan markets** — uv run alpha rules save <name> …, then uv run alpha scan run <name>
- **Strategy development workspace** — uv run alpha suite plan <project-id> <experiment-id> <action>
- **Statistical checks on a strategy (gauntlet, DSR, PBO, CPCV)** — uv run alpha validate SPY
- **Path-risk simulation (Monte Carlo)** — uv run alpha monte-carlo classical --from-run <run-id>
- **Risk numbers that state what they are based on (C04)** — uv run alpha risk scenario --from-run <run-id> --json --include-metric-basis
- **Prop-firm challenge check** — uv run alpha propfirm run SPY …, or --from-run <run-id>
- **Research cases from idea to decision (D0, D1, D2)** — uv run alpha research capture "<your idea>" --json, then uv run alpha research status <project-id>
- **Quick idea screening (Phase C)** — uv run alpha scan hypotheses --as-of <date>
- **Ask the AI assistant about a recorded run (Codex)** — Workstation: open a run, then "Investigate this run" (a real run is recorded)
- **Let an AI assistant use ALPHA's tools (MCP)** — uv run alpha-mcp (started by an MCP-capable AI client)

## Partly working

- **Download bookkeeping: receipts and quota** — not connected to any command; tests only.
- **Bybit funding-rate download** — not connected to any command; real downloads refused on purpose.
- **Price forecasts with the Kronos model** — proved only with a stand-in model. Needs: the Kronos model files (downloaded on first use; not on this computer).
- **Find papers and screen their claims (R4)** — paper download tested only with a stand-in worker. Needs: the literature worker setup (not installed on this computer).
- **Link paper claims to experiments and keep the original PDFs** — no test takes one paper all the way to an experiment.
- **Check data providers and background jobs** — job list tested only with a stand-in command; provider checks need real providers.
- **Paper trading: practice trading with no real money (IBKR Paper)** — no end-to-end test; parts tested with stand-ins. Needs: an opt-in setting, live Binance public data, and an IBKR practice account and gateway for stocks.
- **Machine-learning experiments with Qlib** — proved only with a stand-in worker. Needs: the Qlib worker setup (not installed on this computer).
- **Corrected Alpha158 price features** — no ML run with version 2; final review pending. Needs: the Qlib worker setup (not installed on this computer).
- **Qlib model refit evidence (W11)** — blocked on missing statistics modules. Needs: the Qlib worker setup (not installed on this computer); reviewed statistics modules that do not exist yet.
- **AI stock research loop (RD-Agent, W02)** — made-up data only; restart after a crash not solved. Needs: the RD-Agent setup, which no machine has yet.
- **"Native job result" screen (W04, W18)** — empty until the AI stock research loop produces a job. Needs: the RD-Agent setup, for its browser test.
- **AI-run daily trading-rule study (Packet 3, W08)** — only the report is proven; the study itself needs RD-Agent. Needs: the RD-Agent setup, which no machine has yet; a permanent place to host the runs.
- **Running ALPHA on your Mac with real data providers** — one final review and a run on your Mac. Needs: your Mac; access to a real data provider (blocked since 31 August).

## Demo only

- **Qlib and Nautilus demonstration views** — made-up prices only; not a production path.

## Shelved

- **QuantPad data archive** — dropped from all data-source plans by your earlier decision (recorded in the README).

## Not started

- **Qlib models inside research cases (W09)** — only unused groundwork exists; waits on the daily rule study.
- **Autonomous AI research team** — only a plan; one advisory slice shipped.

## In progress now

- **Get real crypto history into ALPHA** — Resumable crypto history download is built; the real download of the top 50 Bybit contracts has not been done.
- **Clean up and protect the main branch** — Old programme from October; one hardening step left. The triage recommends closing it.
- **Repository tidy-up programme** — Old open-ended to-do list; several items shipped. The triage recommends closing it.
- **Make ALPHA run on your Mac** — Five of six steps done; one final independent review is left.
- **AI-run daily trading-rule study (Packet 3)** — Works on made-up data; the real-market run has not begun and needs RD-Agent and permanent hosting.

## Waiting for your decision

The full triage sheet, with what each item does and why: [docs/roadmap/triage-2026-11.md](docs/roadmap/triage-2026-11.md). Write your answer in its "Your decisions" table.

**Recommended: Keep (finish and check it)**

- Card 1: Crypto history download that resumes safely (backfill, Phase B)
- Card 3: "Are my downloaded daily bars complete?" check
- Card 4: Freeze crypto data into exact snapshots and check them (W05)
- Card 5: Risk numbers that state what they are based on (C04)
- Card 6: Link paper claims to experiments and keep the original PDFs
- Card 11: Corrected Alpha158 price features
- Card 12: Test and web plumbing fixes
- Card 13: Running ALPHA on your Mac with real data providers

**Recommended: Shelve (keep the code, put it aside)**

- Card 2: Download bookkeeping: receipts and quota
- Card 7: AI stock research loop (RD-Agent, W02) (your call)
- Card 8: "Native job result" screen (W04, W18)
- Card 9: AI-run daily trading-rule study (Packet 3, W08) (your call)
- Card 10: Qlib model refit evidence (W11)
- Card B: Bybit funding-rate download
- Card C: The RD-Agent runtime as a whole (covers cards 7, 8 and 9) (your call)
- Card F: Qlib and Nautilus demonstration views

**Recommended: Delete**

- Card 14: Old clean-up programmes (close the plans)
- Card A: Qlib models inside research cases (W09)
- Card D: QuantPad data archive
- Card E: Duplicate copy of the literature download code
- Card G: Delivery-task pilot (Claude/Codex hand-off tool)

**Recommended: Your call**

- Card 15: Autonomous AI research team

## Next up

Ideas not yet planned (no order recorded, so alphabetical):

- Catalyst, expectations and fundamentals research (W15) — large (L)
- ControlStore-owned durable acquisition journal — large (L)
- Data-directory naming migration — medium (M)
- Delivery-task system (durable task ownership and two-model handoff) — large (L)
- Full Qlib model zoo and fold-by-fold counterfactual retraining (W11/W12) — very large (XL)
- Gate coverage for workers/rdagent — small (S)
- Generalise D0 screening to every registered producer (Phase E) — medium (M)
- Governed storage restore and query for real-data native studies (W19) — large (L)
- Intraday (1h) equity timeframe — medium (M)
- Live trading phase (private, single owner) — very large (XL)
- Local vision model and hosted finance reasoning — medium (M)
- Multi-agent specialist swarm / PydanticAI migration — large (L)
- Options expression research (W16) — large (L)
- RD-Agent autonomous native research and restart continuation (W08/W13, T07) — very large (XL)
- Remove the remaining QuantPad code — small (S)

## Housekeeping

- Live plans: 45
- Archived plans: 111
- Backlog items: 15
- Staged refactors: 7

## Where things are

- [Roadmap: every plan, idea and refactor](docs/roadmap/README.md)
- [Capability map: the source of this page](docs/roadmap/capabilities.toml)
- [Triage sheet: decisions for you](docs/roadmap/triage-2026-11.md)
- [Glossary: what the codes mean](docs/reference/glossary.md)
- [How work gets done](docs/operations/development-loop.md)
- [Recently merged pull requests](https://github.com/tradingsystem1880-eng/Project-ALPHA/pulls?q=is%3Apr+is%3Amerged)
