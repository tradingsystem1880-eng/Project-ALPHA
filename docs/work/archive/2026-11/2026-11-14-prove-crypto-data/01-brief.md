# Prove "Download crypto market data" end to end

## What the owner wants

From the owner's direction of 2026-11-14, passed on by the orchestrating session: "All 31
unproven features. Prove, built, implement, improve all of them. 1 by 1." For this capability
(`crypto-data` in `docs/roadmap/capabilities.toml`, state Partial, "tested in-process only; no
end-to-end smoke check yet"): run it from start to finish through the installed `alpha` program,
offline against a recorded provider and for real on free data, fix what that run finds, and add
the end-to-end smoke check that lets its state honestly become Working.

## What done looks like

- A smoke check runs the installed `alpha` in a throwaway home and downloads a Binance spot
  market list, one monthly archive of daily bars and one short live-service tail, through an
  offline recorded provider: real TLS, real host checks, no network, no product code switched.
- The same check reads the bars back as of a date and sees nothing that closed after it, finds
  them in coverage and quality, and sees the installed `alpha-web` serve the same coverage.
- A month the provider does not have fails loud with a message that names the HTTP status, and
  stores nothing.
- The real run on the Dell is written down with exact commands and results.

## How they will see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_data_smoke.py
uv run alpha crypto-data catalog
```

## Out of scope

Bybit, CoinGecko, DefiLlama, GeckoTerminal and Coin Metrics downloads (not run end to end here);
the backfill, snapshot and retained-coverage capabilities (their own tasks); changing the web
app's command environment; any stored real data.
