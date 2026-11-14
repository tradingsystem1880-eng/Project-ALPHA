# Free real market data on the Dell

## What the owner wants

Chosen on 2026-11-14 from offered options: "The Dell should download FREE real market data now
(Yahoo, Stooq, crypto exchanges); paid or keyed providers still wait for the Mac; results stay
labelled not yet confirmed"
([owner decisions](../../../../reference/project/owner-decisions-2.md#2026-11-14-free-real-data-on-the-dell-now)).

In one sentence: real, free market data stored on the Dell through ALPHA's own governed data
commands, usable by the research loop, and labelled not yet confirmed.

## What done looks like

- A data folder outside any git tree, configured with the project's own setup command and the
  owner's 10 GB free-space reserve; downloads under 8 GB.
- Real daily bars for a starter universe of US stocks and ETFs and for the main crypto pairs,
  brought in only through `alpha data` or `alpha crypto-data` commands, never by writing into
  the store by hand.
- Proof: an as-of read returns real rows, a frozen snapshot is made and verified, and one existing
  study command runs on a real snapshot.
- Each source's terms and rate limits checked on its own site first; a source that refuses
  automated access is not used.
- Honest labels using the project's existing ones.

## How they will see it

`export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`, then `uv run alpha data chart-datasets`
and `uv run alpha data candles BTCUSDT --manifest-id <id> --end 2022-06-30 --json`; the full list
is in `04-verify.md`.

## Out of scope

Keyed or paid providers (Tiingo, CoinGecko Demo), live trading, research approvals, any change to
hash-bound research or validation code, and data files in git.
