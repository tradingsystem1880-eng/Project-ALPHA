**Delivery state:** In progress (2026-09-10)

# Edge-first Phase B — feed the machine: resumable crypto backfill, a real derivatives dataset, a point-in-time equity universe, and the knowledge-time flag

```json
{
  "schema_version": 1,
  "title": "Edge-first Phase B: alpha crypto-data backfill (windowed, resumable, in-process), a multi-year top-50 perp derivatives dataset on the governed volume, a point-in-time equity universe table with a survivorship bias guard, knowledge_is_estimated surfaced, and a macro side series",
  "context": "Audit finding F1 (docs/audit/2026-09-10-edge-first-system-audit.md): the usable dataset is 21 survivor equities + 4 crypto pairs daily, while ~22k lines of crypto derivatives plumbing (funding, open interest, basis, options, on-chain) are tested against ~1 MB of sample slices. The navigator map established that `alpha crypto-data acquire` (apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py:2439) takes one instrument and one bounded page per call: Bybit funding pages 200 rows with no cursor (~66 days at 8h), price klines page 1000 rows (~41 days at 1h, ~2.7 years at 1d), open interest follows a cursor when --start is given, and Binance market_bars come as one monthly zip per --period. A bounded window that fills a page raises loudly (crypto_data_cmds.py:1225). One live funding call measured 3.0 s and returned state=qualified. No batch or --symbols flag exists; profile-run is a trailing-coverage loop, not a backfill. On the equity side there is no universe/membership/delisting type anywhere in alpha_core or alpha_data (only QuantPad and Binance membership), the Tiingo EOD endpoint carries no declaration dates so every stored corporate action has announce_date=null and knowledge_is_estimated=True is computed (alpha_core corporate.py:42) but surfaced nowhere. The external volume is mounted and Bybit + data.binance.vision are reachable from this machine.",
  "assumptions": [
    {
      "statement": "Looping the existing in-process acquisition function per window yields byte-identical manifests to running `alpha crypto-data acquire` once per window, so no provenance, receipt, or authority semantics change.",
      "verified_by": "run_backfill takes the acquire callable by injection and the CLI passes crypto_data_cmds._acquire_result unchanged; tests/unit/test_crypto_backfill.py asserts the exact kwargs forwarded per window."
    },
    {
      "statement": "Per-family window spans (funding/OI/ratio 60 days; 1h klines 40 days; 1d klines 900 days; 5m klines 3 days; Binance market_bars one calendar month) stay strictly under each provider page limit so the fill-one-page guard never fires.",
      "verified_by": "tests/unit/test_crypto_backfill.py window-count and span assertions; the live B2 run's ledger shows zero 'narrow the range' failures."
    },
    {
      "statement": "A JSON ledger under data_dir/crypto/backfill/<name>.json keyed by (symbol, window) is enough for resumability; the governed manifests remain the only evidence.",
      "verified_by": "test_rerun_skips_done_windows_and_retries_failed_ones"
    },
    {
      "statement": "A point-in-time universe is a core type + a sibling of write_actions in alpha_data.store + a universe_as_of read on the PIT reader; the as_of firewall (ADR-0005) applies and a future-poison guard with a leaky twin is required.",
      "verified_by": "tests/bias_guards/test_universe_survivorship.py (ack) following tests/bias_guards/test_future_poison_pattern.py"
    }
  ],
  "alternatives_considered": [
    "A shell script looping `alpha crypto-data acquire` (rejected: ~3 s per subprocess and no ledger; thousands of calls need resumability and an in-process loop halves the wall time).",
    "Extend `acquire` with --start/--end auto-windowing (rejected: acquire is documented as one bounded page and its identity/receipt semantics are tested as such; a separate command keeps that contract intact).",
    "Use profile-create/liquidity-freeze/profile-run for the backfill (rejected: it is a trailing 1-day/1-hour coverage loop that requires a qualified 1d bar for every active market before it will freeze a universe).",
    "Fetch a PIT equity universe from a paid vendor (rejected: $0 scope; a free S&P 500 change log plus explicit delisting flags gives a defensible ~600-name cross-section).",
    "Admit a 1h equity timeframe in this phase (rejected: touches the engine +23h close stamp, portfolio_replay, _runner (risk tier), PIT day-granular gating, and web models; crypto hourly research already lives in the crypto data house)."
  ],
  "pre_mortem": [
    "A window straddles a listing date and Bybit returns fewer rows or none -> the window is recorded failed with the provider error and the run continues; the summary lists it; rerun retries only failed windows.",
    "Bybit rate limits under sustained paging -> _wire retries only 429 for geckoterminal; the backfill sleeps a fixed 250 ms between windows and records HTTP errors as failed windows rather than aborting.",
    "The ledger and the manifests disagree after an interrupted write -> the ledger is written atomically (tmp + os.replace) after each window; a window marked done without a manifest id is impossible because the id comes from the acquire result.",
    "Symbol base/quote inference from BTCUSDT is wrong for exotic tickers (1000PEPEUSDT) -> base = symbol minus the exact --quote suffix; a symbol that does not end with the quote is rejected loudly.",
    "The survivorship guard passes vacuously because the fixture has no delisted names -> the fixture includes a name whose effective_to precedes the as_of and the leaky twin asserts the poisoned reader drops it.",
    "Backfill wall time exceeds a session -> it runs as a background process with the ledger; each window is independent so partial progress is durable.",
    "knowledge_is_estimated shows up in a manifest and changes run identity bytes -> it is surfaced only in `alpha data info`/quality JSON projections, never in run manifests."
  ],
  "slices": [
    {
      "title": "B1 alpha crypto-data backfill: pure window planner + atomic JSON ledger + injected-acquire runner in apps/alpha-cli/src/alpha_cli/_crypto_backfill.py; CLI command registered in crypto_data_cmds.py",
      "verify": "uv run pytest -q tests/unit/test_crypto_backfill.py tests/integration/test_crypto_data_cli.py && uv run python scripts/gate.py fast",
      "expected": "Planner cases pass (funding 60-day contiguous windows ending at --end, 1h klines 40 days, 1d 900 days, Binance monthly periods, unsupported family raises DataError); rerun skips done windows and retries failed; CLI dry-run lists windows",
      "rollback": "git revert the B1 commit",
      "status": "done",
      "files": ["apps/alpha-cli/src/alpha_cli/_crypto_backfill.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_backfill.py", ".claude/rules/alpha-cli.md"]
    },
    {
      "title": "B2 run the backfill on the governed volume: top-50 Bybit USDT linear perps by 24h turnover as of 2026-09-10 (selection rule recorded in the ledger name), funding + open_interest 1h + derivative_bars 1h + derivative_bars 1d + mark/index/premium 1h from 2022-01-01, and Binance um market_bars 1d monthly archives",
      "verify": "uv run alpha crypto-data coverage --json | python3 -c 'import json,sys; rows=json.load(sys.stdin)[\"items\"]; print(len(rows), sum(r[\"state\"]==\"qualified\" for r in rows))'",
      "expected": "Thousands of qualified normalized manifests; ledger failure count near zero (listing-date windows only); volume usage in the GB range",
      "rollback": "Manifests are immutable evidence; nothing to roll back. A wrong universe is simply not snapshotted.",
      "status": "in_progress",
      "files": ["data/crypto/backfill/*.json"]
    },
    {
      "title": "B3 point-in-time equity universe: UniverseMembership core type, ParquetStore.write_universe/read_universe, PointInTimeReader.universe_as_of, `alpha data universe import CSV` from a free S&P 500 change log with delisting flags, survivorship bias guard + leaky twin",
      "verify": "uv run pytest -q tests/unit/test_universe_store.py tests/bias_guards/test_universe_survivorship.py -m 'not network' && uv run python scripts/gate.py fast",
      "expected": "universe_as_of(date) returns names whose [effective_from, effective_to) covers the date, including later-removed names; the poisoned reader that drops removed names fails the guard",
      "rollback": "git revert the B3 commit",
      "status": "done",
      "files": ["packages/alpha-core/src/alpha_core/universe.py", "packages/alpha-core/src/alpha_core/__init__.py", "packages/alpha-data/src/alpha_data/store.py", "packages/alpha-data/src/alpha_data/pit.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_universe_store.py", "tests/bias_guards/test_universe_survivorship.py"]
    },
    {
      "title": "B4 surface knowledge_is_estimated: `alpha data info` / actions projections report per-symbol counts of estimated knowledge times so the single-clock state is visible",
      "verify": "uv run pytest -q tests/integration/test_data_cli.py -k knowledge && uv run python scripts/gate.py fast",
      "expected": "JSON carries actions_total and knowledge_estimated counts; run manifests unchanged (identity tests green)",
      "rollback": "git revert the B4 commit",
      "status": "done",
      "files": ["apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/integration/test_data_cli.py"]
    },
    {
      "title": "B5 macro side series: allow asset_class 'index' on the yfinance adapter and pull ^VIX, ^TNX, DX-Y.NYB, HYG, LQD, TLT into the store as ordinary daily bars (no corporate actions), documented as regime context not tradables",
      "verify": "uv run pytest -q tests/unit/test_yfinance_parser.py tests/integration/test_data_cli.py -m 'not network' && uv run python scripts/gate.py fast",
      "expected": "Index symbols pull and snapshot like ETFs; a bias guard is unaffected (same PIT path)",
      "rollback": "git revert the B5 commit",
      "status": "done",
      "files": ["packages/alpha-data/src/alpha_data/adapters/yfinance_adapter.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_yfinance_parser.py"]
    }
  ],
  "tier_impact": ["bias", "protected"],
  "docs_to_update": [".claude/rules/alpha-cli.md", ".claude/rules/alpha-data.md", "docs/BUILD-STATUS.md", "docs/audit/2026-09-10-edge-first-system-audit.md"],
  "out_of_scope": ["A research-lane flag that relaxes crypto research eligibility (deferred until Phase C needs a snapshot bound to a case; ADR-0032/0033 boundary)", "SEC XBRL fundamentals (own phase: filing-date PIT parser + store)", "1h equity timeframe (engine/runner/PIT/web blast radius; see alternatives)", "Any change to the 62-tool MCP pin, REST, or SPA (frozen in Phase A)"],
  "files": []
}
```

## Context

Everything after this phase (screening lane, gauntlet upgrades) is pointless on 22 symbols. The
crypto derivatives house already has parsers, quality checks, and features for every family the
backfill targets; what is missing is the data itself and a way to fetch it without thousands of
hand-typed commands. The equity side needs a universe that includes names that later left, or
every cross-sectional number is uninterpretable.

## Slices

- **B1** `_crypto_backfill.py`: `plan_windows(provider, family, frequency, start, end, now)`,
  `Ledger` (atomic JSON), `run_backfill(...)` with an injected `acquire` callable, `--dry-run`.
- **B2** operational run in the background; ledger names record the selection rule.
- **B3** universe table with the same two-clock discipline as corporate actions
  (`effective_from` inclusive, `effective_to` exclusive, `delisting_return` optional).
- **B4** the flag is a projection only.
- **B5** macro series are bars with no actions; the parser already reconstructs raw prices.

## Test plan

- B1: planner table tests; ledger round trip; rerun semantics; CLI dry-run via CliRunner with a
  monkeypatched acquire.
- B3: store round trip; `universe_as_of` boundaries (from inclusive, to exclusive); bias guard +
  leaky twin under `tests/bias_guards/` (ack).
- B4/B5: CLI JSON assertions; existing identity/determinism tests must stay green.

## DAG / look-ahead / determinism impact

- DAG: `_crypto_backfill.py` lives in `alpha_cli` and imports only `alpha_core` errors; the
  universe type lives in `alpha_core`, its store/reader in `alpha_data` (core-only). No new edges.
- Look-ahead: `universe_as_of` is gated by `effective_from <= as_of < effective_to`; a name's
  removal date is knowledge that only exists after the fact, so removed names stay visible before
  their removal. Guarded.
- Determinism: ledgers are operational state under `data/` (gitignored); manifests unchanged.

## B2 universe (selection rule, recorded 2026-09-10)

Bybit `instruments-info` (category=linear) filtered to `quoteCoin=USDT`, `contractType=LinearPerpetual`,
`status=Trading`, `launchTime <= 2023-01-01`, ranked by `turnover24h` from `market/tickers` on
2026-09-10; the top 50 (127 were eligible; the unfiltered turnover ranking was dominated by
tokenized stocks/commodities and 2025 listings with no history). Survivorship caveat: perps
delisted before 2026-09-10 are excluded; point-in-time membership must come from the
`market_membership`/`instrument_catalog` families before any cross-sectional claim.

```
BTCUSDT,ETHUSDT,SOLUSDT,ZECUSDT,XRPUSDT,IOSTUSDT,NEARUSDT,DOGEUSDT,ADAUSDT,BNBUSDT,LINKUSDT,UNIUSDT,APTUSDT,AAVEUSDT,LTCUSDT,DOTUSDT,DASHUSDT,AVAXUSDT,XMRUSDT,BCHUSDT,XLMUSDT,INJUSDT,OPUSDT,EGLDUSDT,WAVESUSDT,CRVUSDT,HBARUSDT,ATOMUSDT,FILUSDT,COTIUSDT,ICPUSDT,LRCUSDT,SHIB1000USDT,ZENUSDT,ETCUSDT,TRXUSDT,SANDUSDT,MINAUSDT,VETUSDT,LDOUSDT,XTZUSDT,ENSUSDT,GALAUSDT,ALGOUSDT,STXUSDT,PAXGUSDT,RVNUSDT,JASMYUSDT,ROSEUSDT,APEUSDT
```

## B1 live-run defects fixed before B2 (2026-09-10)

- `_acquire_result` called in-process leaves unspecified typer defaults as `typer.Option`
  sentinels (not `None`), which tripped the research-case scope check; `_backfill_acquire` passes
  every unused parameter as an explicit `None` (pinned by a test).
- The CLI path re-raises provider failures as `typer.BadParameter`; the wrapper converts them to
  `DataError` so one bad window is recorded and the run continues (pinned by a test).
- Some perps fund hourly, so a 60-day funding window overflows the 200-row page; the runner now
  halves a window on "fills one provider page" and retries both halves down to one day (pinned).
- B5 needed no adapter code: the yfinance path carries no dataset identity, so `^VIX`, `^TNX`,
  `DX-Y.NYB`, `HYG`, `LQD`, `TLT` pulled as ordinary daily bars (2015-01-01 -> 2026-09-10);
  the provider registry now declares `index` and the AssetClass literal admits it.
