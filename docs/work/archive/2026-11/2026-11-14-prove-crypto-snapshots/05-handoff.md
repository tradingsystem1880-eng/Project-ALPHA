## What changed for you

- **"Freeze crypto data into exact snapshots and check them" is proven end to end and counts as
  Working.** A new automatic check downloads three months of two coins with the real `alpha`
  program (from a recorded copy of Binance on this computer), freezes them into one snapshot,
  checks it for research, refuses overlapping months, survives a repeat download, and refuses the
  snapshot once one stored file is changed by a single byte. The Workstation's API gives the same
  verdict.
- **`alpha crypto-data asset-master-verify reviewed-native-v1` works.** It used to say "version is
  invalid" for the two built-in asset masters that `asset-masters` lists as verified.
- On a copy of your data folder, one snapshot of the whole BTC and ETH daily history (222 months)
  froze in 4 seconds and verified in 4 seconds.

## How to see it

```sh
uv run alpha crypto-data asset-master-verify reviewed-native-v1 --json
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_snapshots_smoke.py
```

## What I am unsure about

- Freezing a long history still means listing every monthly id by hand; filed as backlog
  `crypto-snapshot-by-range` (pick by coin and dates, refuse gaps).
- `snapshot-query` (DefiLlama only) and custom asset masters are not run end to end.
