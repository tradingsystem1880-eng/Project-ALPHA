# ALPHA status

_Generated — do not edit; run: `uv run python scripts/status.py`_

## At a glance

- **Capabilities:** 5 working, 26 partly working, 0 demo only, 5 shelved, 1 not started.
- **Work in progress:** 34 in progress (limit 3).
  - 3 being worked on
  - 31 built but not yet checked end to end
  - Not counted: 7 blocked.
  - Allowed for now: 34. This number only goes down, until it reaches 3.
- **Known defects:** 0.
- **Decisions waiting for you:** 0.

"Working" means the workflow was run from start to finish through the installed program
on made-up (synthetic) data.
Runs on real market data are still to be confirmed on the Mac, except where noted.

## What works today

- **Workstation web app** — uv run alpha-web, then open http://localhost:8801
- **Run a backtest** — uv run alpha backtest run SPY
- **Statistical checks on a strategy (gauntlet, DSR, PBO, CPCV)** — uv run alpha validate SPY
- **Machine-learning experiments with Qlib** — uv run alpha ml capabilities
- **Upstream Alpha158 price features** — set feature_recipe_version: 3 in an ML stage config, or version 3 in an alpha ml prepare spec

## Partly working

- **Download and freeze stock and ETF prices** — no offline way to get prices in; snapshot, verify and as-of read are proven end to end.
- **Reports, figures and run comparison** — the text and JSON (--json) reports are proven end to end; figures and run comparison are tested in-process only.
- **Price forecasts with the Kronos model** — proved only with a stand-in model. Needs: the Kronos model files (downloaded on first use; not on this computer).
- **Research cases from idea to decision (D0, D1, D2)** — proven up to the owner-approval boundary; a full case needs provider data and your approval.
- **Find papers and screen their claims (R4)** — paper download tested only with a stand-in worker. Needs: the literature worker setup (not installed on this computer).
- **Link paper claims to experiments and keep the original PDFs** — no test takes one paper all the way to an experiment.
- **Check data providers and background jobs** — job list tested only with a stand-in command; provider checks need real providers.
- **Paper trading: practice trading with no real money (IBKR Paper)** — no end-to-end test; parts tested with stand-ins. Needs: an opt-in setting, live Binance public data, and an IBKR practice account and gateway for stocks.
- **Corrected Alpha158 price features** — no ML run with version 2; superseded by version 3 (kept for stored results).
- **AI stock research loop (RD-Agent, W02)** — RD-Agent's general loop now runs here end to end with stand-in steps on made-up data, but the stock loop itself cannot run yet (no installable runtime; its smoke check skips), no alpha command starts a run, and restart after a crash is not solved. Needs: a pinned runtime for RD-Agent's full stock loop (ALPHA_STOCK_PYTHON; no lock in the repository); an AI model connection for RD-Agent. More: [docs/roadmap/rd-agent-in-alpha.md](docs/roadmap/rd-agent-in-alpha.md).
- **"Native job result" screen (W04, W18)** — the screen and its API answer here but say unavailable until a stock job exists; its smoke check and browser lane skip without the stock runtime. Needs: a finished stock RD-Agent job, which needs the stock runtime (ALPHA_STOCK_PYTHON). More: [docs/roadmap/rd-agent-in-alpha.md](docs/roadmap/rd-agent-in-alpha.md).
- **AI-run daily trading-rule study (Packet 3, W08)** — RD-Agent's loop runs the rule and its costed backtest in-process on made-up bars; the full daily study fails here without its Docker image and has no end-to-end smoke check. Needs: the qualified daily Docker image (not on this machine); a permanent place to host the runs (retained storage with a 100 GB reserve); real Binance daily bars admitted into that storage. More: [docs/roadmap/rd-agent-in-alpha.md](docs/roadmap/rd-agent-in-alpha.md).
- **Running ALPHA on your Mac with real data providers** — one final review and a run on your Mac. Needs: your Mac; access to a real data provider (blocked since 31 August).

Tested piece by piece inside the test suite, but not yet run from start to finish through the installed program:

- **Price charts with indicators and patterns** — tested in-process and in a browser against a test server (a real run is recorded).
- **Download crypto market data (W05)** — tested in-process only (a real run is recorded).
- **Crypto history download that resumes safely (backfill, Phase B)** — tested in-process only.
- **"Are my downloaded daily bars complete?" check** — tested in-process and in a browser against a test server.
- **Freeze crypto data into exact snapshots and check them (W05)** — tested in-process only.
- **Write trading rules and scan markets** — tested in-process and in a browser against a test server.
- **Strategy development workspace** — tested in-process only.
- **Path-risk simulation (Monte Carlo)** — tested in-process only.
- **Risk numbers that state what they are based on (C04)** — tested in-process and in a browser against a test server.
- **Prop-firm challenge check** — tested in-process only.
- **Quick idea screening (Phase C)** — tested in-process only.
- **Ask the AI assistant about a recorded run (Codex)** — tested in a browser against a test server only (a real run is recorded).
- **Let an AI assistant use ALPHA's tools (MCP)** — tested in-process only.

## Known defects

Found by running the installed program; each has a check that will fail once it is fixed.

- None known.

## Demo only

- None.

## Shelved

- **Download bookkeeping: receipts and quota** — shelved 2026-11-14: not wired into any command; kept for a future download-budget policy and durable acquisition journal.
- **Bybit funding-rate download** — shelved 2026-11-14: not wired into any command (real downloads refused on purpose); kept for funding-event research.
- **Qlib model refit evidence (W11)** — shelved 2026-11-14: not wired into any fit; kept for Qlib fold retraining once the reviewed statistics modules exist.
- **Qlib models inside research cases (W09)** — shelved 2026-11-14: unused groundwork, not wired in; kept for routing Qlib models through RD-Agent research cases after the daily rule study.
- **Qlib and Nautilus demonstration views** — shelved 2026-11-14: made-up prices only, not a production path; kept as a demonstration that Qlib and Nautilus connect (it re-ran on this computer on 2026-11-14).

## Not started

- **Autonomous AI research team** — a backlog item only (moved from a plan 2026-11-14); one advisory slice shipped.

## In progress now

- **Get real crypto history into ALPHA** — Resumable crypto history download is built; the real download of the top 50 Bybit contracts has not been done.
- **Make ALPHA run on your Mac with real data providers** — Five of six Mac steps done; one final review is left, and the real-provider steps (merged in 2026-11-14) wait on provider access.
- **AI-run daily trading-rule study (Packet 3)** — Works on made-up data; the real-market run has not begun and needs RD-Agent and permanent hosting.

## Waiting for your decision

The full triage sheet, with what each item does and why: [docs/roadmap/triage-2026-11.md](docs/roadmap/triage-2026-11.md). Write your answer in its "Your decisions" table.

- None.

## Next up

Ideas not yet planned (no order recorded, so alphabetical):

- Autonomous research agent programme — very large (XL)
- Catalyst, expectations and fundamentals research (W15) — large (L)
- ControlStore-owned durable acquisition journal — large (L)
- Data-directory naming migration — medium (M)
- Full Qlib model zoo and fold-by-fold counterfactual retraining (W11/W12) — very large (XL)
- Gate coverage for workers/rdagent — small (S)
- Generalise D0 screening to every registered producer (Phase E) — medium (M)
- Governed storage restore and query for real-data native studies (W19) — large (L)
- Intraday (1h) equity timeframe — medium (M)
- Live trading phase (private, single owner) — very large (XL)
- Local vision model and hosted finance reasoning — medium (M)
- Make the weekly mutation sweep pass on main — small (S)
- Multi-agent specialist swarm / PydanticAI migration — large (L)
- Offline price import from a local file — medium (M)
- Options expression research (W16) — large (L)
- RD-Agent autonomous native research and restart continuation (W08/W13, T07) — very large (XL)

## Housekeeping

- Live plans: 41
- Archived plans: 115
- Backlog items: 16
- Staged refactors: 7

## Where things are

- [Roadmap: every plan, idea and refactor](docs/roadmap/README.md)
- [Capability map: the source of this page](docs/roadmap/capabilities.toml)
- [Triage sheet: decisions for you](docs/roadmap/triage-2026-11.md)
- [Glossary: what the codes mean](docs/reference/glossary.md)
- [How work gets done](docs/operations/development-loop.md)
- [Recently merged pull requests](https://github.com/tradingsystem1880-eng/Project-ALPHA/pulls?q=is%3Apr+is%3Amerged)
