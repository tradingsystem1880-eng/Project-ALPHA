---
generated_by: uv run python scripts/commands_reference.py
sources:
  - apps/alpha-cli/src/alpha_cli/main.py
  - apps/alpha-cli/src/alpha_cli/*_cmds.py
---

# Command reference

Every `alpha` command, generated from the CLI's own command tree (the catalogue behind
`alpha info commands --all --json` plus each command's help text). Do not edit by hand;
run `uv run python scripts/commands_reference.py`. Full options: `alpha <group> <command> --help`.

309 commands in 43 groups. Options marked (required) are
mandatory; `<ARG>` is a positional argument.

## alpha assistant

Advisory assistant; no evidence admission or execution authority.

- `alpha assistant check <SESSION_ID>` — (no description) Options: `--json`
- `alpha assistant create` — (no description) Options: `--context (required)`, `--json`
- `alpha assistant readiness` — (no description) Options: `--json`
- `alpha assistant show <SESSION_ID>` — (no description) Options: `--json`
- `alpha assistant turn <SESSION_ID>` — (no description) Options: `--request (required)`, `--json`

## alpha backtest

Run the v1 strategy through the backtest engine.

- `alpha backtest cross-sectional <SYMBOLS>` — Backtest a cross-sectional momentum book: long the universe's winners, s… Options: `--lookback`, +14 more
- `alpha backtest holdout <SYMBOL>` — Evaluate one frozen fixed-parameter candidate on its revealed final holdout once.
- `alpha backtest oos <SYMBOL>` — Evaluate one fixed rule over causal walk-forward OOS windows; no model is refit. Options: `--strategy`, `--lookback`, +19 more
- `alpha backtest portfolio <SYMBOLS>` — Backtest a diversified basket: run the strategy across SYMBOLS and combine the… Options: `--strategy`, +24 more
- `alpha backtest run <SYMBOL>` — Backtest SYMBOL with the fixed-parameter strategy; write the run artifacts. Options: `--strategy`, `--lookback`, +22 more

## alpha chart

Chart overlays (indicators, swings, trendlines, Fibonacci levels).

- `alpha chart overlays <SYMBOL>` — Indicator series and pattern annotations over the PIT candle window of SYMBOL. Options: `--indicator`, `--pattern`, +4 more

## alpha context

Point-in-time macro, SEC filings, Binance derivatives, CFTC and FINRA context.

- `alpha context import-bybit` — Import verified Bybit funding and hourly open interest from a restored store. Options: `--from (required)`, `--json`
- `alpha context list` — List stored FRED series and free CFTC/FINRA tables with provenance (no network). Options: `--json`
- `alpha context pull` — Pull FRED vintages using FRED_API_KEY; default to the macro starter set. Options: `--series`, `--json`
- `alpha context pull-binance` — Pull checksum-verified funding months or metrics days (at most 400 days). Options: `--symbol (required)`, +4 more
- `alpha context pull-cftc-cot` — Pull weekly CFTC positioning (legacy, futures only); no key. Options: `--market (required)`, `--since`, `--json`
- `alpha context pull-edgar` — Pull filings and insider transactions with the declared ALPHA_SEC_USER_AGENT. Options: `--ticker`, `--cik`, `--forms`, +2 more
- `alpha context pull-finra-short-volume` — Pull FINRA daily short sale volume; no key. Options: `--symbol (required)`, `--start (required)`, +2 more
- `alpha context pull-osap-portfolios` — Pull one release of published long-short factor returns; no key. Options: `--release (required)`, +3 more
- `alpha context show <SERIES_ID>` — Show stored observations with the selected vintage view named in the output. Options: `--as-of`, `--start`, +3 more
- `alpha context show-binance` — Show stored funding or metrics as known, with optional inclusive UTC date bounds. Options: `--symbol (required)`, +5 more
- `alpha context show-bybit` — Show imported Bybit context known at the UTC cutoff. Options: `--symbol (required)`, `--kind (required)`, `--as-of`, `--json`
- `alpha context show-cftc-cot` — Show stored CFTC positioning known at the cutoff (a row appears only once published). Options: `--market (required)`, +2 more
- `alpha context show-derived` — Show a derived COT or FINRA series on an asset's daily bars (value, known_from, age). Options: `--series (required)`, +4 more
- `alpha context show-edgar` — Show locally stored EDGAR events as known at the cutoff. Options: `--view (required)`, `--ticker`, `--cik`, `--as-of`, `--json`
- `alpha context show-finra-short-volume` — Show stored FINRA short volume known at the cutoff; FINRA-reported trades o… Options: `--symbol (required)`, +2 more
- `alpha context show-osap-portfolios` — Show stored factor returns known at the cutoff, naming the vintage used. Options: `--as-of`, `--release`, +2 more
- `alpha context window` — Summarise the macro window; endpoints use values knowable at each boundary. Options: `--start (required)`, +4 more

## alpha crypto-data

Provider-native crypto acquisition, qualification, snapshots, and storage.

- `alpha crypto-data acquire <PROVIDER> <FAMILY> <INSTRUMENT>` — Acquire one bounded public provider page; this grants… Options: `--base (required)`, +15 more
- `alpha crypto-data asset <SYMBOL>` — Inspect one reviewed native-asset identity and provider-symbol lineage. Options: `--as-of (required)`, `--json`
- `alpha crypto-data asset-contract <NETWORK> <CONTRACT_ADDRESS>` — Resolve one contract by exact network and address;…
- `alpha crypto-data asset-master-create` — Freeze exact cross-provider contract identities; ticker joins remain prohib…
- `alpha crypto-data asset-master-verify <VERSION>` — Rederive a frozen asset master's content identity before snapshot… Options: `--json`
- `alpha crypto-data asset-masters` — List verified asset masters without exposing internal paths or requiring opaque i… Options: `--json`
- `alpha crypto-data backfill <PROVIDER> <FAMILY>` — Run many bounded 'acquire' pages over symbols x windows, resumably…
- `alpha crypto-data backfill-status <PROVIDER> <FAMILY>` — Inspect retained progress/evidence without writes or provid…
- `alpha crypto-data cache-clean` — Delete only the explicitly disposable external cache; immutable data is untouched. Options: `--confirm`, `--json`
- `alpha crypto-data capabilities` — Project discovered support and recorded qualification without hashing data artifac… Options: `--json`
- `alpha crypto-data catalog` — List the exact provider authority for every supported dataset family. Options: `--json`
- `alpha crypto-data compare` — Persist non-substituting cross-venue close-price divergence diagnostics. Options: `--primary-manifest-id (required)`, +4 more
- `alpha crypto-data coverage` — Show exact normalized family coverage and qualification without provider probes. Options: `--json`, `--metadata-only`
- `alpha crypto-data estimate <FAMILY>` — Estimate a bounded acquisition before any network or storage write. Options: `--instruments`, `--days`, +2 more
- `alpha crypto-data feature-create <FEATURE_NAME>` — Materialize one immutable provenance-bound research feature. Options: `--input`, `--available-at`, +1 more
- `alpha crypto-data feature-show <MANIFEST_ID>` — Reverify one immutable derived feature and its exact input lineage. Options: `--json`
- `alpha crypto-data features` — List immutable derived crypto features after full lineage re-verification. Options: `--json`
- `alpha crypto-data liquidity-freeze <PROFILE_ID>` — Freeze one complete prior-day top-liquidity scope without cross-u…
- `alpha crypto-data market-catalog` — Search the latest qualified Binance spot listing catalog without network access. Options: `--query`, `--limit`, `--json`
- `alpha crypto-data profile-batches` — List bounded coverage batch checkpoints without exposing provider bytes. Options: `--json`
- `alpha crypto-data profile-create` — Freeze the default coverage tasks from exact qualified Bybit catalogs. Options: `--as-of`, `--json`
- `alpha crypto-data profile-resume <BATCH_ID>` — Resume exactly one failed or interrupted coverage batch. Options: `--confirm`, `--json`
- `alpha crypto-data profile-run <PROFILE_ID>` — Run and checkpoint one bounded cadence page from an immutable profile. Options: `--cadence (required)`, +4 more
- `alpha crypto-data profile-select-one-minute <PROFILE_ID>` — Bind at most 50 exact one-minute markets to a fresh rese…
- `alpha crypto-data profile-show <PROFILE_ID>` — Inspect a bounded page of one immutable coverage profile. Options: `--offset`, `--limit`, +6 more
- `alpha crypto-data profiles` — List immutable coverage profiles without exposing their full task membership. Options: `--json`
- `alpha crypto-data quality <MANIFEST_ID>` — Reverify and display one normalized artifact's mechanical quality report. Options: `--json`, +9 more
- `alpha crypto-data snapshot-create` — Freeze qualified membership in canonical order; the id is independent of option…
- `alpha crypto-data snapshot-query <SNAPSHOT_ID>` — Read one bounded DefiLlama TVL page from an exact frozen snapshot… Options: `--limit`, `--offset`, +3 more
- `alpha crypto-data snapshot-verify <SNAPSHOT_ID>` — Reverify every external byte and current qualification before res… Options: `--required-family`, +2 more
- `alpha crypto-data snapshot-verify-crowding <SNAPSHOT_ID>` — Verify exact Bybit BTCUSDT crowding-research compatibili… Options: `--json`
- `alpha crypto-data snapshot-verify-hedged-basis <SNAPSHOT_ID>` — Verify the exact two-venue candidate bundle without… Options: `--json`
- `alpha crypto-data storage` — Verify the configured bulk identity and inventory without probing providers. Options: `--json`, `--metadata-only`
- `alpha crypto-data storage-inventory` — Inventory immutable artifacts and removable cache without exposing private pa… Options: `--json`
- `alpha crypto-data storage-verify` — Re-hash every manifest artifact and rederive every frozen snapshot membership. Options: `--json`
- `alpha crypto-data yield-pools` — Search a bounded selection from the latest verified stored yield-pool catalog. Options: `--query`, `--limit`, `--json`

## alpha data

Data ingestion, snapshots, and integrity.

- `alpha data audit <PROVIDER> <RECEIPT_ID>` — Read one immutable candidate/quarantine quality report. Options: `--json`, `--timeframe`
- `alpha data candles <SYMBOL>` — Point-in-time OHLCV candles for SYMBOL (split-adjusted; ''--end'' is an as-of cutoff). Options: `--start`, `--end`, +7 more
- `alpha data chart-datasets` — Discover qualified external archive chart datasets without hashing all artifacts. Options: `--json`
- `alpha data first-bar <SYMBOL>` — Report when SYMBOL was first listed on a CCXT exchange (read-only; needs network). Options: `--source`, +2 more
- `alpha data health <ASSET>` — Check daily bars for adjustment, timestamp, gap and survivorship faults. Options: `--universe`, `--stored`, `--json`
- `alpha data market-overview` — Read-only market overview of stored bars. Options: `--store`, `--window`, `--limit`, `--json`
- `alpha data pull <SYMBOL>` — Pull raw bars + corporate actions for SYMBOL and store them. Options: `--start (required)`, `--end (required)`, +8 more
- `alpha data repair <PROVIDER> <RECEIPT_ID>` — Promote one exact quarantined receipt after explicit owner review. Options: `--approve-differences`, +1 more
- `alpha data rollback-promotion <SYMBOL>` — Recover a canonical symbol after a process interruption during promotion. Options: `--acknowledge`, `--timeframe`
- `alpha data snapshot <SNAPSHOT_ID> <SYMBOLS>` — Freeze the current store for SYMBOLS into an immutable, hashed snapsh… Options: `--source`, +2 more
- `alpha data snapshots` — List every immutable snapshot's manifest summary in deterministic id order. Options: `--json`, `--with-content`
- `alpha data source-status <SYMBOL>` — Show canonical provenance and pending candidate/quarantine receipts for SYMBOL. Options: `--json`, `--timeframe`
- `alpha data symbols` — List every symbol with stored bars (the workstation's symbol picker reads this). Options: `--json`, `--with-actions`, `--timeframe`
- `alpha data ticker <SYMBOL>` — Report SYMBOL's current last-trade price on a CCXT venue (read-only; needs network). Options: `--source`, `--exchange`, +1 more
- `alpha data universe import <NAME> <CSV_PATH>` — Import symbol,effective_from,effective_to,delisting_return,reason ro… Options: `--json`
- `alpha data universe show <NAME>` — List the members of universe NAME as of a date, including names that later left. Options: `--as-of (required)`, `--json`
- `alpha data verify <SNAPSHOT_ID>` — Re-hash a snapshot and confirm it matches its manifest.

## alpha diagnose

- `alpha diagnose <RUN_ID>` — Read the automatic diagnostic pass and audit stored with a rule test. Options: `--json`

## alpha evidence

Append-only cited findings and negative-result memory.

- `alpha evidence add <CLAIM>` — Create a draft evidence record; agent-created findings cannot skip review. Options: `--assets (required)`, +20 more
- `alpha evidence list` — List current or point-in-time evidence projections. Options: `--asset`, `--project-id`, `--status`, `--as-of`, `--limit`, +2 more
- `alpha evidence revise <EVIDENCE_ID>` — Append a reviewed evidence revision without mutating its history. Options: `--status (required)`, +10 more
- `alpha evidence show <EVIDENCE_ID>` — Show current evidence plus immutable revision history. Options: `--json`

## alpha figures

Render publication-quality figures for a stored run.

- `alpha figures clean <RUN_ID>` — Delete cached figures. Options: `--all`, `--json`
- `alpha figures export <RUN_ID>` — Write one figure outside the cache, for a paper or a deck. Options: `--figure (required)`, `--out (required)`, +2 more
- `alpha figures list` — Show the figure catalogue, optionally with per-run availability. Options: `--run`, `--json`
- `alpha figures path <RUN_ID>` — Print a figure's cache key and path without rendering it. Options: `--figure (required)`, `--format`, `--dark`, `--json`
- `alpha figures render <RUN_ID>` — Render figures for a run into the derived cache. Options: `--figure`, `--format`, `--force`, `--dark`, `--json`
- `alpha figures theme` — Emit the canonical figure theme document. Options: `--json`
- `alpha figures theme-css` — Write (or verify) the SPA's generated theme stylesheet. Options: `--out (required)`, `--check`

## alpha follow

Follow a tested idea forward on paper.

- `alpha follow book` — Every active follow as a share of ONE paper account, and the sum per asset. Options: `--json`
- `alpha follow list` — One row per follow, with its state. Options: `--json`
- `alpha follow show <FOLLOW_ID>` — The frozen record, the entries by kind and the chain head. Options: `--all`, `--last`, `--json`
- `alpha follow start` — Follow a tested rule or setup forward on paper. Options: `--test`, `--find`, `--trade`, `--asset`, `--factor`, `--card`, +2 more
- `alpha follow stop <FOLLOW_ID>` — Stop a follow. Options: `--reason`, `--json`
- `alpha follow today` — What is active today: one row per active follow, grouped. Options: `--json`
- `alpha follow update <FOLLOW_ID>` — Book the sessions that closed since the last entry of a followed rule test. Options: `--all`, `--json`
- `alpha follow verify <FOLLOW_ID>` — Recompute the hash chain. Options: `--entry`, `--json`

## alpha forecast

Kronos foundation-model forecasting (probabilistic outcome cones).

- `alpha forecast eval <SYMBOL>` — Score SYMBOL's forecaster at rolling origins vs realized outcomes + baselines. Options: `--horizon`, `--stride`, +16 more
- `alpha forecast run <SYMBOL>` — Sample future OHLCV paths for SYMBOL and write the outcome-cone artifacts. Options: `--horizon`, `--samples`, +12 more

## alpha idea

Write an idea card before you test an idea.

- `alpha idea file <CARD_ID>` — One page for one idea: the card, the map, every reading, the counts, the open points. Options: `--json`
- `alpha idea list` — List every card with its idea and whether a test is linked to it. Options: `--json`
- `alpha idea new` — Save a card. Options: `--claim`, `--mechanism`, `--other-side`, `--disproved-by`, `--baseline`, `--signal-forms`, `--held-for`, +5 more
- `alpha idea show <CARD_ID>` — Print one card, and name the fields that are not stated. Options: `--json`

## alpha info

Resolved settings + machine-readable catalogs.

- `alpha info commands` — Introspect the CLI command tree (flags + defaults) for the workstation's new-run form. Options: `--json`, `--all`
- `alpha info procedures` — Describe registered analysis and research protocols; grants no execution authority. Options: `--json`
- `alpha info providers` — List provider capabilities, limitations, and redacted local configuration state. Options: `--json`
- `alpha info strategies` — List registered strategies and their tunable ''--param'' axes. Options: `--json`
- `alpha info system` — Report local readiness only; no provider endpoint is contacted. Options: `--json`

## alpha labels

Triple-barrier labels and overlap weights (López de Prado), from the AFML worker.

- `alpha labels barrier` — Label what happened after each event: target, stop or time limit first. Options: `--asset (required)`, `--target`, `--stop`, +7 more
- `alpha labels importance <RESULT_ID>` — Report which factors the labels lean on (MDI, purged MDA and SFI). Options: `--factors (required)`, +5 more
- `alpha labels weights <RESULT_ID>` — Weight labels by how much they overlap (uniqueness), with time decay. Options: `--train-end`, `--last-weight`, +3 more

## alpha ledger

Read all recorded trials through one unchanged-ledger view.

- `alpha ledger families` — Show family counts and the conservative all-trials total. Options: `--rdagent-ledger`, `--json`
- `alpha ledger journey` — Write seven-step journeys, annotated pictures and their plotted data. Options: `--run-dir (required)`, `--factor`, `--out`, `--theme`
- `alpha ledger list` — List matching trials newest first, retaining source provenance. Options: `--kind`, `--family`, `--asset`, `--outcome`, +4 more
- `alpha ledger proposal` — Show the ideas RD-Agent proposes and waits on before it builds anything. Options: `--run-dir (required)`, `--details`, +1 more
- `alpha ledger query <QUESTION>` — Run a named question with bound parameters; arbitrary SQL is unavailable. Options: `--asset`, `--family`, +4 more
- `alpha ledger reply` — Answer RD-Agent's proposal. Options: `--run-dir (required)`, `--as (required)`, `--accept`, `--drop`, `--revise`, `--idea`, `--note`
- `alpha ledger show <TRIAL_ID>` — Show a record, its raw row and a fresh evidence hash check. Options: `--rdagent-ledger`, `--json`
- `alpha ledger summary` — Summarise mapped trials, unknown rows and missing sources. Options: `--rdagent-ledger`, `--json`

## alpha library

Browse published ideas and turn one into an idea card.

- `alpha library card <RECORD_ID>` — Make an idea card from a record. Options: `--json`
- `alpha library import-catalogue <SOURCE>` — Turn a published signal table into facts-only 'imported' records. Options: `--from (required)`, +3 more
- `alpha library list` — List the records. Options: `--market`, `--tier`, `--json`
- `alpha library show <RECORD_ID>` — Print one record and the idea cards already made from it. Options: `--json`

## alpha lookalike

- `alpha lookalike` — Has price action like the latest N bars happened before? Options: `--asset (required)`, `--last`, `--timeframe`, `--top`, +3 more

## alpha ml

Prepare and validate isolated cross-sectional ML worker exchanges.

- `alpha ml capabilities` — Inspect installed isolated model capabilities without training or installation. Options: `--worker-project`, `--json`
- `alpha ml compare <EXCHANGES>` — Compare lineage-bound predictions on identical frozen research inputs. Options: `--output`, `--json`
- `alpha ml evaluate <EXCHANGE>` — Compute portable score diagnostics; this is not an ALPHA verdict. Options: `--json`
- `alpha ml export-input <PROJECT_ID> <EXPERIMENT_ID> <OUTPUT>` — Generate a validated Alpha158 starter bundle from one… Options: `--as-of`, `--json`
- `alpha ml import <EXCHANGE>` — Validate a completed worker result without publishing an ALPHA run. Options: `--json`
- `alpha ml prepare <SPEC> <PANEL> <EXCHANGE>` — Validate and atomically publish a worker request bundle. Options: `--worker-lock`, `--model`, +2 more
- `alpha ml prepare-replay <EXCHANGE> <OUTPUT>` — Publish the causal top-quintile signal handoff for canonical ALPHA re… Options: `--json`
- `alpha ml refit-plan <ORIGINAL> <CHANGED>` — Verify frozen engineering inputs; no fits, admission or acceptance. Options: `--protocol (required)`, +3 more
- `alpha ml refit-status <RECORD> <ORIGINAL> <CHANGED>` — Reverify a plan against current bytes; no dispatch or continu…
- `alpha ml replay <EXCHANGE>` — Replay validated OOS predictions through ALPHA and publish an immutable v3 run. Options: `--starting-cash`, +3 more
- `alpha ml train <EXCHANGE>` — Run the separately locked worker and validate its portable result. Options: `--mode`, `--worker-project`, `--no-sync`, +2 more

## alpha monte-carlo

Required scenario/path-risk Monte Carlo evidence from a completed validation run.

- `alpha monte-carlo classical` — Publish IID, causal regime-Markov, and Student-t OOS account-return paths. Options: `--from-run (required)`, +6 more
- `alpha monte-carlo kronos` — Generate synthetic OHLCV tails and fully replay the unchanged canonical strategy. Options: `--from-run (required)`, +12 more

## alpha next

- `alpha next` — Say where the project stands and what you can do now. Options: `--json`

## alpha nightly

Run the golden paths on real stored data and read the record.

- `alpha nightly run` — Run the golden paths end to end and write one dated record. Options: `--config`, `--only`, `--json`
- `alpha nightly status` — Say what the last run showed, the clean streak, and whether it is ready. Options: `--config`, `--json`

## alpha optim

Parameter sweeps judged for overfitting (Deflated Sharpe + PBO + SPA).

- `alpha optim grid <SYMBOL>` — Sweep SYMBOL over the ''--grid'' axes and report the overfitting-aware best config. Options: `--grid`, `--strategy`, +27 more
- `alpha optim mcpt <SYMBOL>` — In-sample Monte Carlo permutation test of the ''--grid'' sweep (overfit test, not OOS). Options: `--grid`, +24 more

## alpha options

Stored option chains: derived volatility series (readings only).

- `alpha options derived <UNDERLYING>` — Show iv30, IV rank and percentile, 25-delta skew, term slope and IV minus real… Options: `--series`, `--rows`, +4 more

## alpha owner-auth

Enroll or recover the local Touch ID owner credential.

- `alpha owner-auth enroll` — Issue a short-lived localhost registration URL; browser enrollment cannot self-start. Options: `--reason (required)`, +2 more
- `alpha owner-auth recover` — Begin a trusted credential-replacement ceremony without weakening browser authority. Options: `--reason (required)`, `--json`

## alpha paper

Nautilus paper trading: local crypto sandbox and fail-closed IBKR Paper.

- `alpha paper ibkr-preflight <INSTRUMENT_ID>` — Construct native IB clients offline in read-only paper mode; never con… Options: `--asset-class`, +3 more
- `alpha paper ibkr-run <SYMBOL>` — Run one long-only stock/ETF decision cycle through native IBKR Paper execution.
- `alpha paper ibkr-what-if-execute <PLAN_HASH>` — Execute one SPY preview; never creates an order or earns paper credi…
- `alpha paper ibkr-what-if-plan` — Freeze the exact offline SPY what-if contract; never connects or submits an order.
- `alpha paper preflight <SYMBOL>` — Construct the Binance-data/sandbox-execution wiring offline without connecting. Options: `--strategy`, +2 more
- `alpha paper readiness` — Generate the evidence-only paper acceptance report; elapsed time never passes it. Options: `--json`
- `alpha paper reconcile <SESSION_ID>` — Report the machine-derived reconciliation state; this command cannot approve i… Options: `--json`
- `alpha paper run <SYMBOL>` — Run ''BASE/USDT'' on Binance public data with local sandbox fills only. Options: `--snapshot (required)`, `--provider`, +9 more
- `alpha paper scheduler-repair <SYMBOL> <SESSION>` — Clear one known crash marker; immutable outcomes and canonical pr… Options: `--config (required)`, +1 more
- `alpha paper scheduler-status` — Inspect due/completed/interrupted daily work without contacting providers. Options: `--config (required)`
- `alpha paper scheduler-tick` — Run one short wake-safe daily scheduler tick (intended for launchd every five minutes). Options: `--config (required)`
- `alpha paper sessions` — List durable operational paper sessions, newest first. Options: `--json`
- `alpha paper show <SESSION_ID>` — Show one durable paper session (never signals its recorded PID). Options: `--json`
- `alpha paper stop <SESSION_ID>` — Request safe cooperative stop: cancel ALPHA orders, never flatten positions.

## alpha partner

Self-checks of the AI research partner's honesty tools.

- `alpha partner selftest` — Check planted honest and dishonest answers against temporary stored runs. Options: `--json`

## alpha project

Strategy projects, immutable versions, experiments, and audit links.

- `alpha project agent-brief <PROJECT_ID>` — Prepare a bounded, evidence-cited scope packet for Codex or another agent. Options: `--evidence-limit`, +2 more
- `alpha project attempt <PROJECT_ID> <EXPERIMENT_ID>` — Append an immutable attempted, failed, pruned, or completed co… Options: `--stage (required)`, +6 more
- `alpha project create <NAME>` — Create a governed strategy project and immediately capture its research case. Options: `--hypothesis (required)`, +2 more
- `alpha project decide <PROJECT_ID> <EXPERIMENT_ID>` — Freeze one sandbox-only accept/reject/revise decision packet. Options: `--verdict (required)`, +4 more
- `alpha project experiment <PROJECT_ID>` — Create or reuse an immutable, content-addressed experiment specification.
- `alpha project experiment-show <PROJECT_ID> <EXPERIMENT_ID>` — Show one immutable experiment specification linked to… Options: `--json`
- `alpha project job-cancel <JOB_ID>` — Persist an idempotent cancellation request for the owning durable worker to obs… Options: `--actor (required)`, +2 more
- `alpha project job-cancel-requested <JOB_ID>` — Project whether the owning worker must honour an audited cancellation… Options: `--json`
- `alpha project job-capacity` — Show exact occupancy of the shared Qlib/Kronos heavyweight class. Options: `--json`
- `alpha project job-create <KIND>` — Create a durable queued development job. Options: `--request-json`, `--project-id`, `--experiment-id`, `--json`
- `alpha project job-event <JOB_ID> <EVENT_TYPE>` — Append a heartbeat, progress, or log event to a live job. Options: `--payload-json`, `--json`
- `alpha project job-list` — List durable development jobs. Options: `--limit`, `--offset`, `--json`
- `alpha project job-reconcile` — Mark only stale-heartbeat queued/running journals failed after confirmed interruption. Options: `--reason`, +2 more
- `alpha project job-show <JOB_ID>` — Show a durable job and a bounded window of its append-only event journal. Options: `--event-limit`, +3 more
- `alpha project job-status <JOB_ID> <STATUS>` — Advance a generic durable job lifecycle. Options: `--result-run-id`, `--terminal-error`, `--json`
- `alpha project link-run <PROJECT_ID> <EXPERIMENT_ID> <RUN_ID>` — Link one completed canonical run to a development st… Options: `--stage (required)`, +2 more
- `alpha project list` — List strategy projects. Options: `--limit`, `--offset`, `--json`
- `alpha project override-research-gate <PROJECT_ID>` — Record an append-only owner research-gate override (trusted-loc… Options: `--actor (required)`, +2 more
- `alpha project research-gate-overrides` — List override events on projects whose research gate is currently overridde… Options: `--limit`, `--offset`, +1 more
- `alpha project reveal-holdout <PROJECT_ID> <EXPERIMENT_ID>` — Permanently audit a one-shot final-holdout reveal. Options: `--actor (required)`, +2 more
- `alpha project review-monte-carlo <PROJECT_ID> <EXPERIMENT_ID>` — Append the owner-only continue/revise/reject decisi…
- `alpha project seal-holdout <PROJECT_ID> <EXPERIMENT_ID>` — Seal an immutable experiment before its final holdout can… Options: `--actor (required)`, +4 more
- `alpha project show <PROJECT_ID>` — Show bounded version, experiment, attempt, run-link, and holdout lineage. Options: `--lineage-limit`, `--json`
- `alpha project stage-state <LINK_ID> <STATE>` — Append a legal state transition to a stage/run link. Options: `--reason (required)`, `--json`
- `alpha project stage-transition <PROJECT_ID> <EXPERIMENT_ID> <STAGE> <STATE>` — Advance an experiment lifecycle stage… Options: `--reason (required)`, +1 more
- `alpha project version <PROJECT_ID>` — Create or reuse an immutable, content-addressed strategy version. Options: `--strategy (required)`, +5 more
- `alpha project version-show <PROJECT_ID> <VERSION_ID>` — Show one immutable strategy version linked to a project. Options: `--json`
- `alpha project workspace recover <PROJECT_ID>` — Quarantine invalid generated state and rebuild from authority. Options: `--json`
- `alpha project workspace show <PROJECT_ID>` — Read and verify the current workspace projection and staleness. Options: `--json`
- `alpha project workspace sync <PROJECT_ID>` — Idempotently publish one project workspace from authority. Options: `--json`
- `alpha project workspace sync-all` — Backfill every governed strategy project workspace. Options: `--json`

## alpha propfirm

Prop-firm Monte Carlo: pass/payout probabilities for a funded-trader evaluation.

- `alpha propfirm run <SYMBOL>` — Score SYMBOL (or --from-run RUN_ID) against a prop firm and write a verdict manifest. Options: `--strategy`, +28 more

## alpha provider

Explicit, receipted provider readiness checks.

- `alpha provider check <PROVIDER_ID>` — Run one bounded check. Options: `--json`

## alpha rdagent

Start RD-Agent with one command and watch the run.

- `alpha rdagent run` — Start the RD-Agent factor loop from rdagent.toml. Options: `--config`, `--dry-run`, `--run-id`
- `alpha rdagent status` — Say where a run is: working, waiting for you, finished or stopped, and what to type next. Options: `--run-dir`, `--config`, `--json`

## alpha report

- `alpha report <RUN_ID>` — Print the stored result for RUN_ID (any run type: gauntlet, backtest, portfolio, etc.). Options: `--json`, +4 more

## alpha research

Governed research cases, contracts, sources, and bounded runs.

- `alpha research approve <SCOPE> <PROJECT_ID> <CONTRACT_ID>` — Owner-approve one exact exploration or confirmation con… Options: `--actor (required)`, +2 more
- `alpha research brief <PROJECT_ID>` — Build the "Resume with Codex" delta brief and record it as a packet. Options: `--created-by`, `--json`
- `alpha research cancel <PROJECT_ID>` — Request active-job cancellation or return unowned work to idle. Options: `--reason (required)`, `--actor`, `--json`
- `alpha research capture <IDEA>` — Capture exact owner wording and immediately perform bounded deterministic triage. Options: `--name`, `--created-by`, +1 more
- `alpha research compare <SYMBOL>` — Backtest each strategy on SYMBOL and rank them by total return. Options: `--strategies`, `--json`
- `alpha research context build <PROJECT_ID>` — Assemble and record one bounded, content-addressed Codex context packet. Options: `--kind (required)`, +6 more
- `alpha research context list <PROJECT_ID>` — List this case's recorded packets, newest first. Options: `--limit`, `--offset`, `--json`
- `alpha research context show <PACKET_ID>` — Return one recorded packet byte-identically. Options: `--json`
- `alpha research data audit <PROJECT_ID> <REF_ID>` — Run a bounded descriptive audit and record it against the dataset… Options: `--json`
- `alpha research data list` — List registered research datasets with their latest audit. Options: `--symbol`, `--limit`, `--offset`, `--json`
- `alpha research data register <SYMBOL>` — Register a research dataset against its exact receipt/provenance bytes. Options: `--kind (required)`, +6 more
- `alpha research data register-crypto <SNAPSHOT_ID>` — Register an eligible CryptoSnapshotV1 after re-verifying every… Options: `--symbol (required)`, +2 more
- `alpha research decide <PROJECT_ID>` — Record the owner-only research outcome/disposition and close the case. Options: `--outcome (required)`, +4 more
- `alpha research decision-view <PROJECT_ID>` — Assemble the owner decision view: checklist, full scorecard, packet, an… Options: `--json`
- `alpha research diagnostic acquire-comparisons <CASE> <PLAN>` — Execute one frozen comparison acquisition batch in private case storage.
- `alpha research diagnostic acquisition-plan <CASE>` — Draft a bounded Tiingo comparison request for an inspected case… Options: `--symbol (required)`, +2 more
- `alpha research diagnostic check-review <PATH>` — Check a typed advisory review and its local JSON evidence hashes/selectors.
- `alpha research diagnostic execution-digest <RUN_ID>` — Verify existing baseline/validation execution, including fill… Options: `--as-of (required)`
- `alpha research diagnostic investigate <CASE>` — Investigate one verified recorded run with Codex; persists budget an… Options: `--run-id`, `--as-of`, +5 more
- `alpha research diagnostic investigation-tool <CASE> <ACTION>` — Fixed-case diagnostic seam used by the restricted MCP service.
- `alpha research diagnostic native-result` — Recover owner-observed synthetic receipt/result; never launch, resume or…
- `alpha research diagnostic run-plan <PATH>` — Run a frozen momentum baseline and validation; always read the terminal receipt.
- `alpha research diagnostic suggest <RUN_ID>` — Act as a research teammate: suggest useful next tests over verified ex… Options: `--as-of (required)`, +1 more
- `alpha research diagnostic weekly-classifier <SYMBOL>` — Measure next-week close direction versus majority and moment…
- `alpha research draft <PROJECT_ID>` — Create a complete exploration contract from owner answers and automatic fingerp…
- `alpha research draft-confirmation <PROJECT_ID>` — Freeze the one-shot D2 confirmation contract mechanically from adm… Options: `--created-by`, `--json`
- `alpha research draft-daily <PROJECT_ID>` — Freeze the bounded daily rule/control recipe; existing local approval is…
- `alpha research evidence-hub <PROJECT_ID>` — Project the eleven-section Evidence Hub with honest NOT_TESTED empty sta… Options: `--json`
- `alpha research export <PROJECT_ID>` — Generate a deterministic Markdown dossier from authority projections. Options: `--output-dir`, `--json`
- `alpha research import-pdf <PROJECT_ID>` — Import text from one owner-selected local PDF; no links are followed. Options: `--file (required)`, +2 more
- `alpha research investigations acquire <IDENTIFIER>` — (no description) Options: `--request (required)`
- `alpha research investigations create` — (no description) Options: `--request (required)`
- `alpha research investigations draft <IDENTIFIER>` — (no description) Options: `--request (required)`
- `alpha research investigations eligibility <RUN_ID>` — (no description)
- `alpha research investigations list` — (no description) Options: `--run-id (required)`
- `alpha research investigations run <IDENTIFIER>` — (no description) Options: `--request`
- `alpha research investigations show <IDENTIFIER>` — (no description)
- `alpha research list` — List bounded research-case backlog rows, newest research activity first. Options: `--limit`, `--offset`, `--json`
- `alpha research note add <PROJECT_ID>` — Append one commentary note — structurally outside the evidence model. Options: `--kind (required)`, +5 more
- `alpha research note list <PROJECT_ID>` — List this case's commentary notes, newest first (never evidence). Options: `--limit`, `--offset`, `--json`
- `alpha research pause <PROJECT_ID>` — Pause an active research worker at a durable checkpoint. Options: `--reason (required)`, `--checkpoint`, +2 more
- `alpha research proposal-options <PROJECT_ID>` — Show executable answer bundles, compatible packs/data, blockers, and… Options: `--json`
- `alpha research protocols list` — List the Git-owned protocol library; index↔file drift fails loud. Options: `--json`
- `alpha research protocols show <PROTOCOL_ID>` — Show one protocol entry plus its exact content. Options: `--json`
- `alpha research reject <SCOPE> <PROJECT_ID> <CONTRACT_ID>` — Owner-reject one exact contract without granting any res… Options: `--actor (required)`, +2 more
- `alpha research report <PROJECT_ID>` — Show the current progress report or deterministic terminal ResearchGatePacket. Options: `--json`
- `alpha research resume <PROJECT_ID>` — Resume a paused or failed case without changing its contract or budget. Options: `--reason`, +3 more
- `alpha research revise <PROJECT_ID>` — Create and reopen one pre-D2 revision child after an owner revise disposition.
- `alpha research run <STAGE> <PROJECT_ID>` — Run an allowed research stage: D0 pilot, governed D1 deep run, or one-sho… Options: `--json`
- `alpha research semantic-projection <PROJECT_ID>` — Read the verified, server-masked semantic projection for one D0 l… Options: `--json`
- `alpha research sources acquire <PROJECT_ID> <DISCOVERY_ID> <CANDIDATE_ID>` — Acquire one recorded direct-PDF candida… Options: `--json`
- `alpha research sources add <PROJECT_ID>` — Record permitted metadata or lawfully retained bytes by immutable receipt. Options: `--title (required)`, +9 more
- `alpha research sources claim add <PROJECT_ID>` — Draft one claim-level literature statement; a paper is never auto-t…
- `alpha research sources claim list <PROJECT_ID>` — List claims (latest revision per claim unless --history). Options: `--history`, `--limit`, +2 more
- `alpha research sources claim reject <PROJECT_ID> <CLAIM_ID>` — Append the owner's rejection of an unscreened claim;… Options: `--actor (required)`, +2 more
- `alpha research sources claim revise <PROJECT_ID> <CLAIM_ID>` — Append an owner revision direction; a later draft rem… Options: `--actor (required)`, +3 more
- `alpha research sources claim screen <PROJECT_ID> <CLAIM_ID>` — Owner screening appends the screened revision (truste… Options: `--actor (required)`, `--json`
- `alpha research sources discover <PROJECT_ID>` — Explicit owner-clickable discovery; results remain untrusted candida… Options: `--query (required)`, +4 more
- `alpha research sources fetch <URL>` — Owner-invoked driver for the isolated literature worker (the ONE network surfa… Options: `--objects-dir`, +2 more
- `alpha research sources freeze <PROJECT_ID>` — Freeze an order-independent, content-addressed source pack. Options: `--source-id (required)`, +2 more
- `alpha research sources original-pdf <SOURCE_ID>` — Verify an owner-provided PDF artifact, optionally returning its e…
- `alpha research sources screen <SOURCE_ID>` — Read source details or a bounded page slice; never screen claims or cha… Options: `--project-id`, +4 more
- `alpha research sources search <QUERY>` — Search local source records by title/locator/DOI terms; never the network. Options: `--limit`, `--offset`, `--json`
- `alpha research status <PROJECT_ID>` — Show the one current phase, execution state, next action, budget, and firewall… Options: `--json`
- `alpha research verify <PROJECT_ID>` — Regenerate and byte-verify a dossier without parsing Markdown as control state. Options: `--path (required)`, `--json`

## alpha results

List rule tests and quote their stored results.

- `alpha results check <PATH>` — Check a draft's tagged numbers, required labels and flags against stored facts. Options: `--json`, `--allow-untagged`
- `alpha results cite <RUN_ID> <METRIC>` — Quote exactly one stored fact; never recompute a metric. Options: `--tool-output`, `--json`
- `alpha results compare <RUN_IDS>` — Compare stored values, differences and ratios, with bases and run labels. Options: `--metric`, `--json`
- `alpha results correlate <RUN_IDS>` — How stored runs moved together: correlation of daily returns, common days, over… Options: `--json`
- `alpha results show <RUN_ID>` — Show sourced facts, observations, audit checks, tool outputs and chart names. Options: `--json`

## alpha risk

Risk & scenario analysis over stored runs.

- `alpha risk scenario` — Re-evaluate risk under vol-scaling and tail-shock scenarios for a stored run. Options: `--from-run (required)`, +4 more

## alpha rules

Owner rule strategies: save, list, show, validate, delete.

- `alpha rules delete <NAME>` — Remove a saved rule file; runs that used it keep their manifest copy of the spec. Options: `--json`
- `alpha rules explain <NAME> <SYMBOL>` — Explain saved conditions on canonical bars without saving or running a strate… Options: `--as-of`, `--json`
- `alpha rules list` — Every saved rule in name order. Options: `--json`
- `alpha rules save <NAME>` — Validate a rule spec and save it canonically as data_dir/rules/NAME.json (overwrites). Options: `--file`, `--spec`, `--json`
- `alpha rules show <NAME>` — One saved rule with its canonical spec and hash. Options: `--json`
- `alpha rules validate` — Parse a rule spec strictly without saving it; exit 2 with the defect if it is invalid. Options: `--file`, `--spec`, `--json`

## alpha scan

Rule scans over stored symbols and their deduplicated alerts.

- `alpha scan alerts` — The alert log (oldest first within the tail). Options: `--limit`, `--json`
- `alpha scan check <NAME>` — Run and append deduplicated alerts for signals that changed since the last check. Options: `--json`
- `alpha scan delete <NAME>` — Remove a saved scan and its check state; past alerts stay in the log. Options: `--json`
- `alpha scan hypotheses` — Screen frozen inputs; record each attempt. Options: `--as-of (required)`, `--lane`, `--symbols`, `--universe`, `--snapshot`, +7 more
- `alpha scan list` — Every saved scan with its last check time. Options: `--json`
- `alpha scan replay <SCAN_ID>` — Re-evaluate an exact frozen screen after code, lock and input integrity verification. Options: `--json`
- `alpha scan run <NAME>` — Evaluate the scan on point-in-time bars; nothing is written. Options: `--as-of`, `--json`
- `alpha scan save <NAME>` — Save (or overwrite) a scan: a rule set plus a universe. Options: `--rules (required)`, `--symbols`, `--json`
- `alpha scan show <NAME>` — (no description) Options: `--json`

## alpha setup

Find every match of a chart setup.

- `alpha setup find <SPEC>` — Record every match and draw contact sheets ending at the entry open. Options: `--asset`, `--context-bars`, `--max-sheets`, +3 more
- `alpha setup show <RUN_IDS>` — Read stored studies or trades: each evidence word and its place in the setup's family. Options: `--json`
- `alpha setup study <FIND_ID>` — Measure forward returns and honest controls; record one exploratory trial. Options: `--check-data`, +3 more
- `alpha setup trade <FIND_ID>` — Trade recorded occurrences with their exits and matched controls; one counted test. Options: `--check-data`, +3 more

## alpha strategy-candidate

Sandbox-only multi-leg candidate evaluation; no paper or order authority.

- `alpha strategy-candidate paper-preflight` — Report the permanent unsupported multi-venue paper boundary without conn… Options: `--json`
- `alpha strategy-candidate run <SNAPSHOT_ID>` — Evaluate a frozen candidate stream; never constructs either venue adap…

## alpha suite

Preview and run immutable, allowlisted Strategy Development workflows.

- `alpha suite actions` — List the fixed public action identifiers. Options: `--json`
- `alpha suite plan <PROJECT_ID> <EXPERIMENT_ID> <ACTION>` — Resolve immutable inputs, readiness, governance, commands,… Options: `--json`
- `alpha suite reserve <PROJECT_ID> <EXPERIMENT_ID> <ACTION>` — Persist the exact queued journal before a detached suit… Options: `--job-id (required)`, +1 more
- `alpha suite run <PROJECT_ID> <EXPERIMENT_ID> <ACTION>` — Execute exactly one ready allowlisted plan and persist its… Options: `--job-id`, +3 more
- `alpha suite status <JOB_ID>` — Read one durable job and its bounded journal. Options: `--event-limit`, `--event-offset`, `--event-tail`, `--json`

## alpha test

- `alpha test <SPEC>` — Test a long/flat trading rule on several assets and record every trial. Options: `--rule`, `--param`, `--asset`, `--name`, +11 more

## alpha tool

Discover and run investigation tools.

- `alpha tool declare <RUN_ID>` — Record which checks you chose before seeing their results. Options: `--set`, `--tools`, `--why`, `--json`
- `alpha tool describe <TOOL_ID>` — Read a tool's question, inputs, parameters, outputs and caveats. Options: `--json`
- `alpha tool find <WORDS>` — Find checks from plain words: what each answers, its cost and the command to run it. Options: `--json`
- `alpha tool history <TARGET>` — List successful, failed and unfinished attempts in ledger order. Options: `--json`
- `alpha tool list` — Find tools by target, question, family or kind. Options: `--for`, `--search`, `--family`, `--kind`, `--json`
- `alpha tool results <RUN_ID>` — List the stored check results of a run, each marked declared or exploratory. Options: `--json`
- `alpha tool run <TOOL_ID> <TARGET>` — Run one tool with repeatable key=value parameters. Options: `--param`, `--seed`, `--json`
- `alpha tool run-set <NAME> <TARGET>` — Run each member of a predeclared set and report every outcome. Options: `--json`
- `alpha tool situations` — List each situation with its checks, cheapest first. Options: `--json`, `--markdown`

## alpha unusual

- `alpha unusual` — How unlike every earlier stretch are the latest N bars? Options: `--asset (required)`, `--window`, `--timeframe`, `--json`

## alpha validate

- `alpha validate <SYMBOL>` — Validate SYMBOL end-to-end and write the run artifacts (manifest, parquet, tear sheet). Options: `--strategy`, +32 more
