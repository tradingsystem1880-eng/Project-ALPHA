# Phase 4h — The `alpha paper` CLI

> **For agentic workers:** orchestration only (the CLI composes engine + node). Lazy imports per
> `CLAUDE.md`. TDD.

**Goal:** a usable `alpha paper` command surface that runs a paper session through the sandbox and
inspects its artifacts, reusing the 4b–4g machinery.

## What landed

- **`alpha_paper/replay.py`** — `ReplayDataClient` (+ factory + config + `register_replay_events`): a
  shippable live data client that replays a recorded `Data` feed into the `TradingNode` (the
  production sibling of the test fixture). Drives a paper session over stored history — a dry-run of
  the live pipeline (a real-time websocket feed is the next increment).
- **`alpha_paper/session.py`** — `run_paper_session(spec, instrument, events, strategy, *, data_dir,
  loop, ...)`: builds the sandbox node, adds an `_EquityRecorder` actor (per-session
  mark-to-market equity, as in the backtest) + the caller's strategy, replays, and writes
  `session.json` (provenance + counts) + `audit.log.jsonl` (one record/order) +
  `equity_curve.parquet`. Returns a `PaperSessionResult`. Stays free of the validation/pandas edge —
  metrics are computed by the CLI.
- **`apps/alpha-cli/src/alpha_cli/paper_cmds.py`** — `alpha paper`:
  - `run SYMBOL [--asset-class equity|crypto] [strategy params] [--exchange --max-notional
    --feed-interval --snapshot]` — loads bars (the `_load_bars` seam), builds the t+1 feed
    (`to_execution_feed`, precision from the instrument), composes `TimeSeriesMomentum`, runs a
    session on a fresh event loop, echoes the summary.
  - `status` — lists sessions under `data_dir/paper`.
  - `report SESSION_ID` — prints headline metrics computed from the stored equity curve via
    `alpha_validation.metrics` (the CLI is the only layer allowed the validation edge).
  - Wired into `main.py` (`app.add_typer(paper_app, name="paper")`); node imports are lazy.

## Tests
`tests/integration/test_paper_cli.py`: `run` writes the session artifacts (session.json, audit
jsonl, equity_curve.parquet with one mark/session); `status` lists it; `report` prints metrics;
unknown session fails loud. Uses a small fixture store + a fast `--feed-interval`.

## Notes / limitations
- `run` is a **replay dry-run** over stored history through the live node — it proves the full paper
  pipeline end-to-end at $0 with no network. A real-time `ccxt.pro` websocket data client (live
  paper trading proper) is the next increment beyond this PR.
- A CLI `halt` kill-switch needs cross-process signalling (the node runs in-process during a bounded
  `run`); `halt_trading`/`resume_trading` (4g) cover the programmatic path. Deferred.

## Done = Phase 4h complete
`alpha paper run|status|report` work end-to-end on the offline fixture. Gate green (ruff · format ·
lint-imports 7-kept · mypy --strict 126 files · 209 tests).

**Next:** Phase 4i — CI coverage gate (`pytest-cov`), a Hypothesis property test, suppress the benign
event-loop teardown warnings, and update `CLAUDE.md` (module map + build status).
