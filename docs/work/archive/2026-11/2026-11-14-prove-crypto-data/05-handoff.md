## What changed for you

- **"Download crypto market data" is now proven end to end and counts as Working.** A new
  automatic check runs the real `alpha` program the way you would: it downloads a Binance market
  list, a month of daily bars and a few days from Binance's live service, reads the bars back as of
  a date, and sees the Workstation serve them. It talks to a recorded copy of Binance's answers on
  this computer instead of the internet (made-up prices, in Binance's exact format), so it runs
  anywhere, including on GitHub, without downloading anything.
- **Clearer error when Binance has no file:** "Binance archive request failed with HTTP 404"
  instead of a bare "request failed".
- Run for real on the Dell: the market list and coverage read fine on your data folder; a live
  download of November 2026 so far worked on a copy of it; an unfinished day is quarantined, never
  used.

## How to see it

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_data_smoke.py
```

## What I am unsure about

- Only Binance is proven end to end; the other crypto sources are not.
- A download started from the Workstation page ignores proxy and certificate settings (backlog
  item `web-downloads-network-settings`); changing that touches the web security boundary.
- The check needs 10 GB free on the machine running it (the store's reserve floor); GitHub's
  runners normally have more.
