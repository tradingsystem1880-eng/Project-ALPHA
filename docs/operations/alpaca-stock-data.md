# Alpaca stock data: owner steps

ALPHA can download daily US stock and ETF prices from Alpaca's free market-data plan with
`alpha data pull --source alpaca`. It needs an Alpaca key that only you create and only you hold.
This page is the whole procedure. Why Alpaca, and its limits:
[ADR-0047](../adr/0047-alpaca-interim-stock-source.md) and the
[data layer](../reference/project/components/data-layer.md#real-data-on-the-dell).

Everything downloaded this way is **not yet confirmed**: Alpaca is an interim source, not the
authoritative one (Tiingo, [ADR-0017](../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)).
Alpaca's terms allow it for your own personal, non-commercial use only: never publish, share or
commit the downloaded data.

## 1. Create the free account (once, in your browser)

1. Go to `https://alpaca.markets` and sign up. A paper-trading account is enough; you do not need
   to fund anything or open a live brokerage account.
2. Keep the free **Basic** market-data plan (the default). Do not buy "Algo Trader Plus".

## 2. Make a key (once)

1. In the Alpaca dashboard, on the paper-trading home page, find **API Keys** on the right and
   choose **Generate New Keys**.
2. Alpaca shows a **Key ID** and a **Secret Key**. The secret is shown only once; keep the page
   open for step 3. If you lose it, generate a new pair (the old one stops working).
3. Never paste either value into a chat, an issue, a commit or any file inside the repository.
   If you reset your paper account later, Alpaca's FAQ says to generate new keys.

## 3. Store the key on the Dell, outside the repository (once)

In a terminal on the Dell, run these lines. They ask for the two values without showing the secret
and without saving them in your shell history, and write a file only you can read:

```sh
mkdir -p ~/.config/alpha && chmod 700 ~/.config/alpha
( umask 077
  read -r -p "Alpaca Key ID: " id
  read -r -s -p "Alpaca Secret Key: " secret; echo
  printf 'export APCA_API_KEY_ID=%q\nexport APCA_API_SECRET_KEY=%q\n' "$id" "$secret" \
    > ~/.config/alpha/alpaca.env )
```

ALPHA reads only the two environment variables `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` (the
names Alpaca's own documentation uses). It never writes, prints or stores them; the AI agents
working in this repository are not allowed to read that file.

## 4. Each time you download

(Steps 1 to 3 were done on 2026-11-14; the starter download below was run that day into
`data-alpaca`, snapshot `alpaca-starter-2026-11-14`. QQQ was refused, see the table.)

```sh
cd /home/hunta/alpha-clean-base/Project-ALPHA
source ~/.config/alpha/alpaca.env
uv run alpha provider check alpaca        # expect: "alpaca: verified (...)"
```

If the check says `authentication_failed`, the key is wrong: repeat steps 2 and 3. If it says
`entitlement_denied`, Alpaca refused the consolidated (SIP) history on your plan: stop and tell
the assistant; ALPHA never falls back to the smaller IEX feed by itself.

Then the starter universe, full available history (Alpaca's history starts in 2016), one symbol
at a time:

```sh
export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data-alpaca
END=$(TZ=America/New_York date -d yesterday +%F)
for s in SPY QQQ IWM DIA TLT IEF GLD; do
  uv run alpha data pull "$s" --source alpaca --asset-class etf --start 2016-01-04 --end "$END"
done
for s in AAPL MSFT AMZN GOOGL NVDA META JPM XOM JNJ; do
  uv run alpha data pull "$s" --source alpaca --start 2016-01-04 --end "$END"
done
uv run alpha data snapshot alpaca-starter-$(date +%F) SPY QQQ IWM DIA TLT IEF GLD AAPL MSFT AMZN \
  GOOGL NVDA META JPM XOM JNJ --source alpaca
uv run alpha data verify alpaca-starter-$(date +%F)
```

Why a separate folder (`data-alpaca`): the main data folder already holds the same 16 symbols from
Yahoo, and ALPHA never mixes two sources in one price series, so an Alpaca download onto a
Yahoo-held symbol is refused. The crypto data stays in `/home/hunta/alpha-clean-base/data`.

Each successful line ends with `not yet confirmed (interim source, ...)`. A line that fails names
the reason; the usual ones:

| Message | Meaning | What to do |
|---|---|---|
| `needs APCA_API_KEY_ID and APCA_API_SECRET_KEY` | the two variables are not set in this terminal | `source ~/.config/alpha/alpaca.env` |
| `quarantined ... calendar_gap:<date>` | Alpaca has no bar for a trading day (a halt, or before the first day it has) | start after that date, or leave the symbol out |
| `stock_dividend` or `spin_off ... cannot adjust` | the company had an action ALPHA cannot adjust prices for | leave that symbol out |
| `split cross-check failed` | Alpaca's split list and its prices disagree | leave the symbol out and tell the assistant |
| `dividends on <date> disagree on record or pay date` | Alpaca lists one dividend twice with different dates (QQQ, 2022-09-19) | leave the symbol out, or start after that date |
| `HTTP 429 persisted` | the free plan's 200 calls a minute was exceeded | wait a minute and rerun that symbol |

A rerun of the same command is safe: it keeps a new receipt, compares every stored row, and
leaves unchanged rows as they are; a changed row is recorded as a correction.
