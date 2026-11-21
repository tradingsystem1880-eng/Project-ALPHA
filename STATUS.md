# ALPHA status

_Generated — do not edit; run: `uv run python scripts/status.py`_

## At a glance

- **Capabilities:** 34 working, 38 partly working, 0 demo only, 3 shelved, 1 not started.
- **Known defects:** 0.
- **Decisions waiting for you:** 5.

"Working" means the workflow was run from start to finish through the installed program
on made-up (synthetic) data.
Runs on real market data are still to be confirmed on the Mac, except where noted.

## What works today

- **Workstation web app** — uv run alpha-web, then open http://localhost:8801
- **Download crypto market data (W05)** — uv run alpha crypto-data catalog (a real run is recorded)
- **Crypto history download that resumes safely (backfill, Phase B)** — uv run alpha crypto-data backfill bybit <family> --symbols BTCUSDT --quote USDT --start … --end … --ledger <name> --dry-run
- **"Are my downloaded daily bars complete?" check** — uv run alpha crypto-data quality <manifest-id> --coverage-start … --coverage-end … --as-of …
- **Freeze crypto data into exact snapshots and check them (W05)** — uv run alpha crypto-data snapshot-create …, then uv run alpha crypto-data snapshot-verify <snapshot-id>
- **Run a backtest** — uv run alpha backtest run SPY
- **Statistical checks on a strategy (gauntlet, DSR, PBO, CPCV)** — uv run alpha validate SPY
- **Path-risk simulation (Monte Carlo)** — uv run alpha monte-carlo classical --from-run <run-id> (a real run is recorded)
- **Front door (alpha next)** — uv run alpha next
- **Idea card (alpha idea)** — uv run alpha idea new --from research/examples/idea-card.example.toml
- **Library of published ideas (alpha library)** — uv run alpha library list
- **Nightly real run (alpha nightly)** — uv run alpha nightly status More: [research/tools/nightly-run.md](research/tools/nightly-run.md).
- **Risk numbers that state what they are based on (C04)** — uv run alpha risk scenario --from-run <run-id> --json --include-metric-basis (a real run is recorded)
- **Quick idea screening (Phase C)** — uv run alpha scan hypotheses --as-of <date> (a real run is recorded)
- **Machine-learning experiments with Qlib** — uv run alpha ml capabilities
- **Upstream Alpha158 price features** — set feature_recipe_version: 3 in an ML stage config, or version 3 in an alpha ml prepare spec
- **Textbook labels and overlap weights (López de Prado)** — uv run alpha labels barrier --asset SPY@alpaca (result folder with facts and a picture) (a real run is recorded)
- **Which factors the labels lean on (purged MDI, MDA, SFI)** — uv run alpha labels importance <result-id> --factors <factors.parquet> (a real run is recorded)
- **Investigation tools for rule tests and fixed checks on RD-Agent replays** — alpha tool find "how bad could drawdown get" (a real run is recorded) More: [research/tools/resampling-checks.md](research/tools/resampling-checks.md). More: [research/tools/montecarlo-checks.md](research/tools/montecarlo-checks.md). More: [research/tools/run-level-checks.md](research/tools/run-level-checks.md). More: [research/tools/published-factors.md](research/tools/published-factors.md). More: [docs/reference/project/components/validation-and-evidence.md](docs/reference/project/components/validation-and-evidence.md). More: [docs/reference/invariants/cli-investigation-tools.md](docs/reference/invariants/cli-investigation-tools.md).
- **Has price action like this happened before? (STUMPY matrix profile)** — uv run alpha lookalike --asset SPY@alpaca --last 30 (a real run is recorded) More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md). More: [docs/reference/project/outside-projects.md](docs/reference/project/outside-projects.md).
- **What is unusual right now? (STUMPY left matrix profile)** — uv run alpha unusual --asset BTC/USDT --window 30 (a real run is recorded) More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md). More: [docs/reference/project/outside-projects.md](docs/reference/project/outside-projects.md).
- **Check an answer's numbers against the records** — alpha results check answer.md --json More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md).
- **One trial ledger across rule tests, tools and RD-Agent** — alpha ledger summary --json (a real run is recorded) More: [docs/reference/invariants/cli-trial-ledger.md](docs/reference/invariants/cli-trial-ledger.md).
- **Honesty self-test of the answer checker** — alpha partner selftest (a real run is recorded) More: [docs/reference/invariants/cli-results-check.md](docs/reference/invariants/cli-results-check.md).
- **Deflated Sharpe counted over the idea's family** — alpha results cite <run_id> family_trials (a real run is recorded) More: [docs/reference/project/components/validation-and-evidence.md](docs/reference/project/components/validation-and-evidence.md). More: [docs/reference/invariants/cli-trial-ledger.md](docs/reference/invariants/cli-trial-ledger.md).
- **Opposite-direction research control** — alpha diagnose <run_id> (a real run is recorded) More: [research/tools/inverted-signal-control.md](research/tools/inverted-signal-control.md). More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md).
- **Walk-forward efficiency with explicit limits** — alpha diagnose <run_id> (a real run is recorded) More: [research/tools/walk-forward.md](research/tools/walk-forward.md). More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md).
- **Find every match of a chart setup** — alpha setup find <spec.toml> --json (a real run is recorded) More: [docs/reference/invariants/cli-setups.md](docs/reference/invariants/cli-setups.md). More: [docs/reference/project/components/strategies-and-signals.md](docs/reference/project/components/strategies-and-signals.md).
- **Price-noise robustness controls** — alpha diagnose <run_id> (a real run is recorded) More: [research/tools/price-noise.md](research/tools/price-noise.md). More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md).
- **Implausible-result observation** — alpha diagnose <run_id> (a real run is recorded) More: [research/tools/diagnose-and-audit.md](research/tools/diagnose-and-audit.md). More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md).
- **Study outcomes after every separate setup occurrence** — alpha setup study <find_id> --json (a real run is recorded) More: [research/tools/setup-study.md](research/tools/setup-study.md). More: [docs/reference/invariants/cli-setups.md](docs/reference/invariants/cli-setups.md). More: [docs/reference/project/components/strategies-and-signals.md](docs/reference/project/components/strategies-and-signals.md).
- **Trade setup occurrences long or short with declared exits and results in R** — alpha setup trade <find_id> --json (a real run is recorded) More: [research/tools/setup-trade.md](research/tools/setup-trade.md). More: [docs/reference/invariants/cli-setups.md](docs/reference/invariants/cli-setups.md). More: [docs/reference/project/components/strategies-and-signals.md](docs/reference/project/components/strategies-and-signals.md).
- **Daily data health report** — alpha data health SPY@home (a real run is recorded) More: [research/tools/data-health.md](research/tools/data-health.md). More: [docs/reference/project/components/data-layer.md](docs/reference/project/components/data-layer.md).
- **Data health on rule tests and setup runs** — alpha test <spec.toml> --check-data More: [research/tools/data-health.md](research/tools/data-health.md).

## Partly working

- **Download and freeze stock and ETF prices** — no offline way to get prices in; snapshot, verify and as-of read are proven end to end.
- **Intraday bars, from one minute to one hour, end to end** — proven in-process and by hand on real data, with no smoke test yet; oos, portfolio and holdout backtests, research registration and the Workstation chart toolbar are still daily. More: [docs/reference/invariants/data-bar-timeframes.md](docs/reference/invariants/data-bar-timeframes.md).
- **Reports, figures and run comparison** — the text and JSON (--json) reports are proven end to end; figures and run comparison are tested in-process only.
- **Follow a tested idea on paper (alpha follow)** — Build F2: a followed rule test updates on stored bars (synthetic proof only). A setup or factor cannot be updated yet. Build F3 added `follow today` and the nightly steps N4 (update every follow, check journals) and N0 (opt-in bar refresh for followed assets); proven with fakes only. `scripts/status.py` does not show the follow count yet (protected). No real-data run yet.. More: [docs/reference/invariants/cli-follow.md](docs/reference/invariants/cli-follow.md).
- **Portfolio view across strategies (alpha results correlate, alpha follow book)** — Proven with in-process unit tests only; no smoke test through the installed program. Follow sizes are fixed paper sizes, not marked to market. No real-data run recorded.. More: [docs/reference/invariants/cli-results-check.md](docs/reference/invariants/cli-results-check.md). More: [docs/reference/invariants/cli-follow.md](docs/reference/invariants/cli-follow.md).
- **Today screen for followed ideas** — tested with a faked relay and in a browser; the detail shows the last 5 entries the command returns, not 10. No real-data run yet.. More: [docs/reference/invariants/web-frontend.md](docs/reference/invariants/web-frontend.md).
- **Price forecasts with the Kronos model** — proved only with a stand-in model. Needs: the Kronos model files (downloaded on first use; not on this computer).
- **Research cases from idea to decision (D0, D1, D2)** — proven up to the owner-approval boundary; a full case needs provider data and your approval.
- **Find papers and screen their claims (R4)** — paper download tested only with a stand-in worker. Needs: the literature worker setup (not installed on this computer).
- **Link paper claims to experiments and keep the original PDFs** — no test takes one paper all the way to an experiment.
- **Check data providers and background jobs** — job list tested only with a stand-in command; provider checks need real providers.
- **Paper trading: practice trading with no real money (IBKR Paper)** — no end-to-end test; parts tested with stand-ins. Needs: an opt-in setting, live Binance public data, and an IBKR practice account and gateway for stocks.
- **Corrected Alpha158 price features** — no ML run with version 2; superseded by version 3 (kept for stored results).
- **AI stock research loop (RD-Agent, W02)** — RD-Agent's own factor loop now runs model-connected on real Binance bars, judged by ALPHA instead of its built-in Qlib backtest (ADR-0049), from one launcher command with a hash-pinned runtime and the gateway's call cap: by 2026-11-16 about 80 factors judged across runs, no candidate; since ADR-0055 a screened factor passes only if its top third beat its bottom third (offline this rejects 16 of the 18 earlier replays; they still count as trials), the proposer sees every idea family, and each paid call has a 180 s limit; new frozen universes support explicit missing days, causal membership and 30-day write-offs with a disclosed 30% haircut, and an optional store directory; a first system check on the wide store (142 pairs) found three tickers whose identity changes across a gap (LUNA reused, DREP and COCOS redenominated), which the data layer must split before that store is used; `alpha rdagent run` and `alpha rdagent status` now start and watch it from one config file (no retry, no daemon), but it is not yet supervised as an ALPHA job, has no end-to-end smoke check with a scripted model, the fixture and stock loops ALPHA runs still use stand-in steps, and restart after a crash is not solved. Needs: supervision of the factor loop as an ALPHA job under the native job supervisor (backlog: rdagent-factor-loop-supervision); `alpha rdagent run` starts it today as a plain child process; an end-to-end smoke check of the factor loop through the installed programs with a scripted model route. More: [docs/roadmap/rd-agent-in-alpha.md](docs/roadmap/rd-agent-in-alpha.md).
- **RD-Agent recorded runs in the Workstation (RD-Agent)** — journey view awaits a browser check and owner review; the run records supply verdicts when available. More: [docs/reference/project/components/rd-agent.md](docs/reference/project/components/rd-agent.md).
- **RD-Agent's run viewer (RD-Agent)** — no end-to-end smoke check; not linked from the Workstation yet. More: [workers/rdagent/README.md](workers/rdagent/README.md).
- **"Native job result" screen (W04, W18)** — its smoke check now passes here: alpha and the web app read a made-up stock job's result; the browser lane fails here only because the web front end's test packages are not installed; no real job exists yet. Needs: a real (not made-up) stock RD-Agent job, which needs an AI model connection. More: [docs/roadmap/rd-agent-in-alpha.md](docs/roadmap/rd-agent-in-alpha.md).
- **AI-run daily trading-rule study (Packet 3, W08)** — with its Docker image now qualified here, the full daily study's tests pass on made-up bars; it has no end-to-end smoke check, the storage settings are not yet created, and no real data has been acquired. Needs: the Dell's storage settings, created by you (docs/operations/storage-settings.md; 10 GB reserve per ADR-0043); real Binance daily bars admitted into that storage. More: [docs/roadmap/rd-agent-in-alpha.md](docs/roadmap/rd-agent-in-alpha.md). More: [docs/operations/storage-settings.md](docs/operations/storage-settings.md).
- **Running ALPHA on your Mac with real data providers** — one final review and a run on your Mac. Needs: your Mac; access to a real data provider (blocked since 31 August).
- **Macro context data as first published** — installed-command smoke test written; execution and live FRED behavior await verification. More: [docs/reference/project/components/data-layer.md](docs/reference/project/components/data-layer.md).
- **Provider-neutral options data layer** — no provider adapter, health rows or context-store join; waits for the paid data package. More: [docs/reference/project/components/options-data.md](docs/reference/project/components/options-data.md).
- **Test a trading rule on several assets with one command** — installed-command synthetic run checked; smoke suite awaits execution outside the sandbox. More: [docs/reference/project/components/command-line.md](docs/reference/project/components/command-line.md).
- **Automatic diagnostic pass and audit on every rule test** — end-to-end smoke verification outside the builder sandbox. More: [docs/reference/invariants/cli-runs.md](docs/reference/invariants/cli-runs.md).
- **Company filings, earnings dates and insider trades as filed** — live SEC check (ticker map, submissions, time zone, Form 4 path) needs ALPHA_SEC_USER_AGENT. More: [docs/reference/project/components/data-layer.md](docs/reference/project/components/data-layer.md).
- **Futures positioning and short sale volume as known** — inputs only: no signal, factor or research read is wired yet; CFTC known_from for pre-2022-09 rows is a rule, not a stamp. More: [docs/reference/project/components/data-layer.md](docs/reference/project/components/data-layer.md).
- **Crypto funding rates and open interest as known** — no pull-to-screen path or research use yet; only one Binance symbol tried; no bias guard yet for the Bybit clocks. More: [docs/reference/project/components/data-layer.md](docs/reference/project/components/data-layer.md).
- **Published factor catalogue and returns (reference)** — reference only: no check compares a strategy with these factors yet, and the research reads are not wired. More: [docs/reference/invariants/data-context.md](docs/reference/invariants/data-context.md).

Tested piece by piece inside the test suite, but not yet run from start to finish through the installed program:

- **Price charts with indicators and patterns** — tested in-process and in a browser against a test server (a real run is recorded).
- **Market overview of stored bars** — tested in-process and in a browser against a test server.
- **Write trading rules and scan markets** — tested in-process and in a browser against a test server.
- **Strategy development workspace** — tested in-process only.
- **Prop-firm challenge check** — tested in-process only.
- **Ask the AI assistant about a recorded run (Codex)** — tested in a browser against a test server only (a real run is recorded).
- **Let an AI assistant use ALPHA's tools (MCP)** — tested in-process only.
- **Purged cross-validation for labels that last several days** — tested in-process only (a real run is recorded).
- **Fractional differencing with d chosen on training data only** — tested in-process only (a real run is recorded).
- **Second opinions on luck-adjusted scores, minimum track record and strategy risk** — tested in-process only (a real run is recorded).
- **Follow one judged idea through seven steps (RD-Agent)** — tested in-process only. More: [research/tools/rdagent-journey.md](research/tools/rdagent-journey.md). More: [docs/roadmap/backlog/research-loop-screen.md](docs/roadmap/backlog/research-loop-screen.md).

## Known defects

Found by running the installed program; each has a check that will fail once it is fixed.

- None known.

## Demo only

- None.

## Shelved

- **Qlib model refit evidence (W11)** — shelved 2026-11-14: not wired into any fit; kept for Qlib fold retraining once the reviewed statistics modules exist.
- **Qlib models inside research cases (W09)** — shelved 2026-11-14: unused groundwork, not wired in; kept for routing Qlib models through RD-Agent research cases after the daily rule study.
- **Qlib and Nautilus demonstration views** — shelved 2026-11-14: made-up prices only, not a production path; kept as a demonstration that Qlib and Nautilus connect (it re-ran on this computer on 2026-11-14).

## Not started

- **Autonomous AI research team** — a backlog item only (moved from a plan 2026-11-14); one advisory slice shipped.

## Waiting for your decision

The full triage sheet, with what each item does and why: [docs/roadmap/triage-2026-11.md](docs/roadmap/triage-2026-11.md). Write your answer in its "Your decisions" table.

**Recommended: Your call**

- Card N2: RD-Agent idea-family failure limit (three near-copies in one round close a family)
- Card N3: Move RD-Agent research toward stocks and the owner's own setups
- Card N4: Make the Qlib v3 feature recipe the default
- Card N5: When to resume Workstation screen work
- Card N6: Add the purpose and the three golden paths to CLAUDE.md

## Next up

Ideas not yet planned (no order recorded, so alphabetical):

- A route for new daily-bar research ideas — large (L)
- Autonomous research agent programme — very large (XL)
- Catalyst, expectations and fundamentals research (W15) — large (L)
- Check a coin's whole downloaded daily history in one step — medium (M)
- ControlStore-owned durable acquisition journal — large (L)
- Coverage maps for Qlib and RD-Agent — medium (M)
- Data provider limits not yet written down — small (S)
- Data questions from the November repository studies — medium (M)
- Data-directory naming migration — medium (M)
- Delivery tooling paper cuts found while building the swing-judge stack — small (S)
- Exact versions for outside projects in the main install's manifests — small (S)
- Exposure log: correct entries and match ideas by economic family — medium (M)
- File-system freshness gaps — small (S)
- Freeze a crypto snapshot by coin and date range — medium (M)
- From an RD-Agent candidate factor to a research case draft — medium (M)
- Full Qlib model zoo and fold-by-fold counterfactual retraining (W11/W12) — very large (XL)
- Gate coverage for workers/rdagent — small (S)
- Generalise D0 screening to every registered producer (Phase E) — medium (M)
- Governed storage restore and query for real-data native studies (W19) — large (L)
- Intraday (1h) equity timeframe — medium (M)
- Intraday bars in the multi-asset portfolio replay — medium (M)
- Intraday candles and run charts in the Workstation — medium (M)
- Live trading phase (private, single owner) — very large (XL)
- Local vision model and hosted finance reasoning — medium (M)
- Lookalikes and novelty: what comes after the first commands — medium (M)
- Make the weekly mutation sweep pass on main — small (S)
- Multi-agent specialist swarm / PydanticAI migration — large (L)
- Name where NautilusTrader may be imported — small (S)
- Offline price import from a local file — medium (M)
- One crypto store for backtests, with receipts — medium (M)
- One trial ledger, many code versions — medium (M)
- Options expression research (W16) — large (L)
- Overlap-corrected t statistic for the quick screen — small (S)
- Owner rule backtests: full allocation without rejected orders or daily churn — medium (M)
- Per-asset-class cost and annualisation defaults — small (S)
- Platform journey check: planted causes the AI partner must find — medium (M)
- RD-Agent autonomous native research and restart continuation (W08/W13, T07) — very large (XL)
- RD-Agent factor loop under the command line's job supervisor — medium (M)
- RD-Agent loop: a usable fake route, resume, and exact call accounting — medium (M)
- Re-check the vendored Kronos copy against the glue rules — small (S)
- Research loop screen — large (L)
- Research-method ideas recovered from earlier material — medium (M)
- Research-partner and screen ideas recovered from earlier material — medium (M)
- Research-practice ideas from the owner's private research — medium (M)
- Reviewer: checklists by folder and a required coverage list — small (S)
- Risk stress scenarios that can move the drawdown — small (S)
- Rule language: session, time of day, open and volume — medium (M)
- Rule-test report: wording and basis papercuts — small (S)
- Test-fixture ideas recovered from earlier material — medium (M)
- Textbook machine-learning methods in their own pinned worker — large (L)
- Vol-target sizing keeps sending orders a cash account cannot pay for — small (S)
- Web-started downloads ignore proxy and certificate settings — small (S)
- What the research partner borrows from QuantPad — medium (M)
- Workstation screen ideas from the owner's reference images — medium (M)

## Housekeeping

- Backlog items: 54
- Staged refactors: 5

## Where things are

- [Roadmap: every plan, idea and refactor](docs/roadmap/README.md)
- [Capability map: the source of this page](docs/roadmap/capabilities.toml)
- [Triage sheet: decisions for you](docs/roadmap/triage-2026-11.md)
- [Glossary: what the codes mean](docs/reference/glossary.md)
- [How work gets done](docs/operations/development-loop.md)
- [Recently merged pull requests](https://github.com/tradingsystem1880-eng/Project-ALPHA/pulls?q=is%3Apr+is%3Amerged)
