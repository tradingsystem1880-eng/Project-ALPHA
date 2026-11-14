# Verification: "Download crypto market data" end to end

Run on the Dell on 2026-11-14 (UTC), branch `m8/prove-crypto-data`.

## Offline, through the installed program (the smoke check)

`tests/smoke/test_crypto_data_smoke.py`, run with
`uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_data_smoke.py tests/smoke/test_web_smoke.py tests/smoke/test_data_smoke.py`:
4 passed, 1 skipped (the existing designed skip `test_data_pull_offline`), 55 s.

What it does: the installed `alpha` runs in a fresh home under `<repo>/tmp/smoke-crypto/` whose
data folder is configured by the same `scripts/storage_settings.py write` step `scripts/setup.sh`
runs. Every `alpha` call gets `HTTPS_PROXY` pointing at a loopback CONNECT proxy and
`SSL_CERT_FILE` at a throwaway certificate authority; the proxy answers synthetic Binance-format
bytes for the exact pinned URLs and never connects out. So the product code runs unchanged: real
TLS, the provider's own host, MIME, size and checksum checks. Steps and results: catalog lists
Binance market bars; the spot listing downloads `qualified`; `market-catalog --query BTC` finds
BTCUSDT; the January 2024 archive downloads `qualified` (31 rows, 1 to 31 January); a four-day REST
tail downloads `qualified`; `quality` shows no failures; `data candles ... --end 2024-01-12` returns
10 and 11 January only (12 January closes after the cutoff) with the recorded prices; an
unrecorded month exits 2 with `HTTP 404` and stores nothing; the proxy saw exactly the five
expected URLs and refused nothing. The installed `alpha-web` then serves the stored coverage and
the market list from the same home.

Before the build, a prototype proved the approach and found the bulk store refuses a data folder
under `/tmp` ("cloud bulk root cannot be a disposable temporary directory"); the smoke home is
therefore in the git-ignored `tmp/` of the checkout and removed afterwards. Not changed: that guard.

## For real, on free data

All with the main checkout's installed `alpha` (same code as `origin/main`).

Read-only, on the real folder (`ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`):

```text
alpha crypto-data storage --json        -> "state": "ready", 2854 manifests, free 50.6 GB, reserve 10 GB
alpha crypto-data catalog --json        -> 30+ families; market_bars: binance primary_acquisition
alpha crypto-data market-catalog --query BTC --limit 5 --json -> 42 matches (BTCUSDT, BTCUSD, BTCUSDC, ...), stale false
alpha crypto-data coverage --json       -> 1427 normalized items, 4.4 s
```

Writes, on a copy of the folder (`/home/hunta/alpha-clean-base/tmp/prove-crypto/data`, made with
`cp -a` and a fresh `storage_settings.py write` for the copy; the real folder was not written):

```text
alpha crypto-data acquire binance market_bars BTCUSDT --base BTC --quote USDT --category spot \
  --frequency 1d --start 2026-11-01T00:00:00Z --end 2026-11-13T00:00:00Z --json
-> "state": "qualified", 13 rows 2026-11-01..2026-11-13, one live request to api.binance.com, 2.0 s
alpha data candles BTCUSDT --manifest-id 6c3b77b0... --start 2026-11-10 --end 2026-11-13 --json
-> 10, 11 and 12 November (the 13th closes after the cutoff); source binance:market_bars, qualified
alpha crypto-data acquire ... --start 2026-11-13T00:00:00Z --end 2026-11-14T08:59:00Z --json   (run at 09:01 UTC)
-> "state": "quarantined", failures ["partial_period"]: the unfinished 14 November bar is never qualified
```

Rough edges seen, not changed: `--start 2026-11-01` (no time) is refused with "must include a
timezone" (a deliberate point-in-time rule; the backfill command takes plain dates); the chart
read labels a REST tail `history_kind: reconstructed_from_verified_archive` (a fixed label of the
read, not of the source).

The real folder was checksummed before (7,291 files, `tmp/prove-crypto/real-data-before.sha256`)
and compared after all four capabilities' runs (see the last task's verification).

## Checks

- New unit tests fail on `origin/main` (2 of 3 by assertion; the third pins the kept "rerun to
  resume" wording) and pass after the change; `tests/unit/test_crypto_binance.py` 56 passed.
- `uv run python scripts/gate.py check`: see the pull request.
- The handoff build's own gate runs failed only because the fresh worktree had no built web
  bundle (`static` missing for `alpha-web`, which also failed the existing web smoke); after
  `npm ci && npm run build` both pass. Not a code fault.

## Review

Codex-built; reviewed by Claude (orchestrator) line by line. Finding fixed by hand: the smoke home
fixture removed its shared parent folder with an "is it empty, then remove" race; now a suppressed
`rmdir`. Docstring of `tests/smoke/conftest.py` updated for the recorded provider.

## Not proven here

Bybit, CoinGecko, DefiLlama, GeckoTerminal and Coin Metrics downloads; a download started from the
Workstation page (it would not reach a proxy: backlog `web-downloads-network-settings`).
