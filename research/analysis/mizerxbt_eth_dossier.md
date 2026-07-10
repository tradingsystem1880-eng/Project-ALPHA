# MizerXBT ETH Short — Research Dossier (2026-07-10)

Provenance labels: **[C]** confirmed by independent source · **[U]** relayed by the user
(unverifiable from this sandbox) · **[X]** checked and could NOT be verified.

## Access constraints (all verified 2026-07-10)
x.com, api.hyperliquid.xyz, hyperdash.com, legacy.hyperdash.com, hyperbot.network and several
news hosts are blocked by this session's egress policy (proxy CONNECT 403). Research below is
from web-search snippets and reachable coverage only.

## The trader
- **[C]** @MizerXBT ("Mizer") is a real, active X account trading ETH; search surfaced his post
  "+6 fig trade in less than 24h 🫡 $ETH is not done"
  (x.com/MizerXBT/status/1945379163168203126).
- **[U]** Exact thesis language: "Lower $ETH. Patience.", resistance $1,800–$1,848, signs of
  exhaustion, passive selling, LTF scalp with patience, holding $3.8M+ shorts, close only on
  invalidation.
- **[U]** Hyperliquid wallet 0x8A820d3B050BAFC0A1f3156706f28038aa292dce is his. The address is
  indexed by HyperDash/Hyperbot trader pages (so it is a tracked account), but both trackers and
  the Hyperliquid API are egress-blocked — position size, win rate and PnL history could not be
  read.
- **[X]** Widely-covered "90% win-rate whale" / "22-trade streak" ETH-short articles
  (bitcoinworld, cryptorank, MEXC) describe **pension-usdt.eth**, a different wallet. Do not
  conflate that record with MizerXBT's.

## Market stats consistent with the thesis (July 2026)
- **[C]** ETH rejected at the $1,800 wall 4–5 times in a month (FXLeaders 2026-07-07; coinpedia;
  coinpaper). A clean break targets $1,830–$1,850 — matching the $1,848 zone top.
- **[C]** Funding ~flat; taker flow sell-side into bounces; "the current setup favors patience
  over aggressive positioning" (tradingpedia). ETF flows only just snapped a 9-day outflow
  streak; whale-sized bids absent (cryptorank).
- **[C]** Range/chop regime: $1,700–$1,800 consolidation, $1,500–$1,800 wider range; 50-day EMA
  ≈ $1,803 sits on the zone floor; sentiment at extreme fear (cryptonews).
- **[C]** Volatility compression flagged ("calm before the storm", beincrypto headline) —
  consistent with an impending impulsive resolution in either direction.
- **[C]** Bull counter-case exists in print: "key resistance $1,796 could open path to $2,245"
  (MEXC news) and July bounce-from-yearly-lows coverage — the zone is being watched by breakout
  buyers too.
- **[C]** Analyst supports below: $1,670 and $1,500 (Ash Crypto via coinmarketcap/blockonomi
  coverage) — bracketing the user's TP1 $1,650 and TP3 $1,508.

## The user's live position (screenshot, 2026-07-10 20:39)
ETHUSDT perp short, isolated 16x. Entry $1,745.02, mark $1,797.38, notional $122,311.71
(≈68.05 ETH), uPnL −$3,562.83 = −47.56% of margin (margin ≈ $7,491), liq $1,844.86, exchange
TP/SL $1,642.55 / $1,840. Order book at capture: bid/ask depth 53%/47%; ask walls 26,786 ETH at
$1,810 and 8,290 at $1,840; day +2.56%.

**Structural red flag:** the stop ($1,840) sits $4.86 (0.26%) below the liquidation price
($1,844.86). A stop triggered by a wick into $1,840 must fill ~$5 of book before the position
liquidates; slippage through the $1,840 ask wall can convert a planned −86%-of-margin stop into
a −100% liquidation.
