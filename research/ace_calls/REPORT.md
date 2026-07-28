# Ace: what the record actually shows

**Corpus:** 75 screenshots → 212 distinct statements, 15 Feb – 25 Jul 2026 (161 days).
**Scored:** 42 adjudicated calls, 27 with a completed 30-day horizon.
**Verdict:** his calls underperformed a same-regime coin flip by 28 points — and with
**n_eff = 2.9**, that gap is not statistically distinguishable from noise. Both halves of that
sentence are load-bearing.

---

## 1. The headline, with the number that guts it

| | value |
|---|---|
| calls resolved at 30d | 27 |
| hit rate (≥10% in the called direction) | **6/27 = 22.2%**  95% CI [10.6%, 40.8%] |
| contemporaneous control (same asset, same trend state, within 180d) | 47.1% over 3,016 draws |
| difference | **−28.1%**  95% CI [−39.6%, −7.0%] |
| **independent observations** | **n_eff = 2.9** |
| **difference at n_eff** | **95% CI [−41.0%, +32.2%] — spans zero** |

The 27 calls span 126 days and each looks forward 30. They overlap roughly nine-fold, so they are
not 27 draws from anything; they are about three. Every subgroup below tells the same story: a
nominal interval that excludes zero, and a deflated interval that does not.

| cut | n | n_eff | hit rate | control | diff | nominal CI | **CI at n_eff** |
|---|---|---|---|---|---|---|---|
| all calls | 27 | 2.9 | 22.2% | 47.1% | −28.1% | [−39.6%, −7.0%] | **[−41.0%, +32.2%]** |
| long only | 13 | 2.9 | 46.2% | 42.4% | +14.7% | [−17.5%, +41.9%] | **[−36.5%, +36.9%]** |
| short only | 14 | 3.0 | **0.0%** | 49.5% | −49.5% | [−51.6%, −27.9%] | **[−51.6%, +6.7%]** |
| position only | 11 | 2.1 | 18.2% | 48.5% | −28.5% | [−43.1%, +2.6%] | **[−51.1%, +17.3%]** |
| forecast only | 14 | 4.2 | 21.4% | 47.4% | −27.4% | [−41.9%, +3.7%] | **[−43.0%, +22.6%]** |
| no bare levels | 25 | 2.9 | 20.0% | 47.9% | −27.9% | [−40.0%, −6.2%] | **[−41.8%, +31.4%]** |
| BTC only | 26 | 2.9 | 19.2% | 47.2% | −32.2% | [−42.1%, −11.1%] | **[−41.1%, +32.1%]** |

**So: no, this does not establish that he is a bad trader.** It establishes that five months of
calls is not enough evidence to establish anything about anyone, in either direction. Anybody —
including him — who reads a track record this size as proof of skill or its absence is reading
noise. That cuts both ways and it is the single most important line in this document.

What the record *does* support is a description of **how he trades**, which needs far less
statistical power, and a handful of **arithmetic facts** that are true regardless of sample size.

### Horizon sensitivity (mandatory display, not a menu)

| horizon | resolved | hits | rate | control | diff |
|---|---|---|---|---|---|
| 7d | 33 | 1 | 3.0% | 9.5% | −6.4% |
| 14d | 33 | 3 | 9.1% | 23.0% | −13.9% |
| **30d (primary)** | 27 | 6 | 22.2% | 47.1% | −24.9% |
| 90d | 22 | 19 | 86.4% | 82.6% | +3.7% |

At 90 days he "hits" 86% of the time — and so does a coin, 83% of the time. Crypto reaches ±10%
within a quarter almost unconditionally. This is exactly why the horizon was fixed in advance:
picking 90d after the fact would have produced a flattering, meaningless number.

---

## 2. Four things that are true regardless of sample size

These are arithmetic, not inference. They do not need n_eff.

### 2.1 He never once gave a stop

**0 of 42 calls specified a risk level.** 15 named a target. Not one, in five months, said where the
idea was wrong. Every exit instruction in the corpus is discretionary and after the fact — "start
taking profit", "I'm out", "sell here like 20%". This is the most consequential structural fact
about the method and it needs no statistics at all.

### 2.2 At his own stated leverage, most of these calls do not survive to be judged

Mean adverse excursion across the 27 resolved calls: **−11.2%**. Share liquidated before the
horizon, at leverages he states himself in the corpus:

| leverage | 3× | 5× | 10× | 20× | 40× |
|---|---|---|---|---|---|
| share of calls liquidated | 0% | 7% | **56%** | 85% | **89%** |

He states 5× and 6× on the March BTC/LINK longs, 6.88–7.42× on the LINK panels, 3× on GMX, and
**40× on the BTC shorts**. Both 40× shorts liquidated **the next day**:

| short | entry | liquidation price (+2.5%) | breached |
|---|---|---|---|
| 9 Mar | 68,394 | 70,104 | 10 Mar |
| 14 Mar | 71,174 | 72,954 | 15 Mar |

Hit rate asks whether the direction was right. This asks whether the account lives long enough to
find out, and it is the more useful question for anyone thinking of following him.

### 2.3 The shorts went 0 for 14

Fourteen short calls between 9 March and 5 June. Not one reached −10% within 30 days. They were
made almost continuously into a rally that carried BTC from 68,394 to a peak of **82,829 (6 May)**.
The direction flipped to long on 14 April at 74,107 — near the top of that same rally — and stayed
long through the decline to 57,759 on 1 July.

The shape is short-into-strength, long-into-the-top. With n_eff = 3 this is *one* mistimed regime
call repeated, not fourteen independent errors, and it should be read that way.

### 2.4 His own words confirm the outcome

On 3 June: *"I holded this position since feb to be in loss today June 3rd."* He entered BTC at a
stated 64.3k on 2 March. BTC closed **64,118** on 3 June — **−0.3%**. The admission is
arithmetically exact.

In between, BTC traded to 82,829. A 5× long from 64.3k was up ~140% at that peak and back to
flat by June.

---

## 3. The one verifiable position, and it worked

Six exchange panels across 2–17 March show **one continuous LINK/USD long** — identical entry
$8.7933 and identical $1,000,814.99 size throughout. Not six trades; one, tracked over fifteen days.
Every arithmetic relation between entry, mark, leverage, collateral and liquidation price is
self-consistent to the cent, so the panels are almost certainly genuine.

| date | leverage | mark | liquidation | unrealised |
|---|---|---|---|---|
| 2 Mar | 6.88× | 8.7001 | 7.5635 | −$17,382 |
| 3 Mar | 6.91× | 9.2140 | 7.5695 | +$40,282 |
| 13 Mar | 5.78× | 9.3236 | 7.3219 | +$55,009 |
| 14 Mar | 5.79× | 9.5227 | 7.3229 | +$79,141 |
| **16 Mar** | 6.55× | 9.9651 | 7.4990 | **+$127,452** |
| 17 Mar | 7.42× | 9.7929 | 7.6577 | +$111,405 |

LINK never came close to the liquidation price — its low through 23 May was **8.405**, well above
7.5695 — and it peaked at **10.728 on 10 May** (+22% spot, ≈+150% at 6.9×). Whether he was still in
it then is not in the corpus.

**But note what this is not.** It is the *only* position evidence in 75 screenshots. There is **no
BTC or XRP position panel anywhere**, despite BTC carrying 32 of the 42 calls. Every BTC and XRP
directional claim is unverified talk: no fills, no panels, no P&L. The one trade he documented is
the one that worked.

---

## 4. How he trades — the part the corpus does support

**Instruments.** Perpetual futures on BTC (76% of calls), with LINK, XRP, DOGE and GMX around it.
Leverage 3–40×, cross-margined, six-figure notional.

**Method, in his own vocabulary.** Horizontal levels above all — a "green line" (~69k) and a "blue
line" (~62.6–64k) that recur across five months and carry most of the decision weight. Then:
bearish/bullish "order blocks" (68.8k, 69k), supply/demand bands, bull flags, double tops, "3 taps"
on a level, weekly/monthly candle closes, FOMC and session timing (*"NEVER TRUST SUNDAY NIGHT
MOVES"*), altcoin dominance, and an inverse head-and-shoulders on XRP. It is discretionary
level-and-structure reading with no stated systematic component, no position-sizing rule, and no
risk framework.

**What he does not use.** No fundamental data. No on-chain. No funding, open interest, or flow.
No backtest, no historical base rate, and no expression of probability anywhere in 212 statements.

**Timing signature.** The one thing he is genuinely good at is *naming levels that get touched*.
1 March: pivot 69,011 (touched next day), target band 73,700–74,500 → BTC printed a 74,046 high on
**4 March, three days later**, inside the band. 22 July: *"58 to 67k, it's a 9k move"* → the actual
move was 57,759 → 66,924 = **9,166**. He is frequently right about *where*. He is much weaker about *when* and *which
direction next*, which is where the money is.

**Failure mode.** Escalating conviction into an adverse trend, expressed at rising leverage, with
no invalidation level. "No matter what we going to see 62k", "Give me 52-49k (ALL IN)", "IM LONG
MAKE SURE TO LONG UNTIL JUNE", "108k btc" — none of these came with a price that would have meant
he was wrong.

**Unfalsifiable framing.** On 15 April he posted *"btc to 83k-77k ?"*. On 18 June he described that
same call as *"already made a bit 83k-77k downside"* — recasting an ambiguous range as a downside
call after the fact. The range was never scoreable in either direction, which is precisely why it
could be claimed later. It is excluded from the record, and the pattern is worth naming.

**Self-contradiction is rarer than the noise level suggests.** Across 161 days I found exactly
**one** same-day directional contradiction (21 March: *"stay away from longs @everyone"* at 02:42,
*"Longs continues..."* at 10:55). Both sides are dropped from the record. One in five months is not
a serious charge.

### The two claims you asked about directly

> *"The whole crypto market is on the verge of a breakout"* (20 July) — scored against BTC at
> 65,225. Horizon incomplete (5/30 days); standing at **best +2.6%, now −1.5%**.

> *"XRP's price action is signaling a potential trend reversal (inverse head and shoulders), with
> multiple technical factors reinforcing the upside bias"* (21 July) — horizon incomplete (4/30);
> standing at **best +1.2%, now −4.0%**.

Neither is scoreable yet and neither will be until late August. Separately, the XRP pump study
found that the "multiple technical factors" idea does not hold up in general: stacking confluence
conditions did **not** raise the pump rate monotonically, and volatility compression — the core of
"on the verge of a breakout" — *anti*-predicted XRP pumps. His iH&S read, though, was independently
corroborated: the detector confirmed the same structure on 18 July, three days before he named it.

---

## 5. Where the record stands right now (not scored)

Thirteen calls have not completed their horizon. Reported so nothing is hidden, **explicitly not
counted** — judging a call early judges it on a window the caller did not choose.

| date | asset | dir | elapsed | best | worst | now |
|---|---|---|---|---|---|---|
| 2 Mar | LINK | long | 19/30 | +12.5% | −6.2% | +1.8% |
| **27 Jun** | **BTC** | **long** | 28/30 | **+11.5%** | −3.7% | +7.1% |
| 2 Jul | BTC | long | 23/30 | +8.7% | −0.5% | +4.4% |
| 2 Jul | XRP | long | 23/30 | +8.9% | −3.2% | +1.0% |
| 7 Jul | BTC | long | 18/30 | +5.7% | −2.9% | +1.5% |
| 8 Jul | BTC | long | 17/30 | +7.5% | −0.9% | +3.2% |
| 20 Jul | BTC | long | 5/30 | +2.6% | −2.4% | −1.5% |
| 21 Jul | XRP | long | 4/30 | +1.2% | −5.2% | −4.0% |

The 27 June call — *"Bottom is forming, 3 taps on 60k's… time to join in"* at BTC 60,000 — is the
best call in the corpus. The actual low was 57,759 four days later (3.7% below), and BTC has run
+11.5% off it. **It is not in the scored record**, and its exclusion is not a judgement about him:
its horizon simply has not closed. That it is his best call and is missing from the headline is
worth stating plainly, because the omission runs against him.

Four calls (LINK 6 May, LINK 27 Jun, DOGE 27 Jun, DOGE 30 Jun) fall past the end of their series;
two (GMX) have no price series at all. All six are kept in the denominator.

---

## 6. What is worth taking from him

1. **Level identification.** His horizontal levels get touched, and they get touched close to the
   prices he names. That skill is real and it is testable — it is the one component here worth
   extracting into a rule.
2. **The 3-taps / multiple-retest idea.** Both his 27 June bottom call and your own triple-tap
   trendline work point at the same structure. It is already formalised in `alpha_patterns`.
3. **Patience as a stated discipline** — "We don't need to catch every move", "not trading is also
   making money". He says it often; the record shows he does not follow it.

## What to take from him with tongs

1. **Leverage without stops.** 0/42 calls carried a risk level, 89% of them liquidate a 40× position
   before the horizon, and both 40× shorts died the next day. This is the mechanism by which a
   trader with genuine level-reading skill still blows up.
2. **Conviction language as a signal.** The most emphatic statements — "No matter what", "ALL IN",
   "MAKE SURE TO LONG UNTIL JUNE" — cluster in the worst-performing stretch of the record.
3. **Retrospective reframing.** "As planned", "market confirmed", "undefeated" appear after moves in
   both directions, and the 83k-77k episode shows an ambiguous range being resolved after the fact.
4. **Any claim of profitability.** There is exactly one documented position in 75 screenshots. His
   own 3 June message says a position held since February was in loss. Nothing in this corpus
   establishes that he is profitable, and nothing in it establishes that he is not.

---

## 7. Method, limits, and what would change the answer

**Scoring.** A call hits if price reaches +10% in the called direction within 30 days, measured
from **the close of the bar the message was posted on** — the follower's fill, not his. When he
says he is long from 64.3k while BTC trades 68.8k, a reader cannot have his price; scoring from it
would hand him 4,500 points no follower could take.

**Pre-registration.** `DEFAULT_HIT`, `DEFAULT_HORIZON_DAYS`, `HORIZON_SWEEP`, `CONTROLS_PER_CALL`,
`TREND_WINDOW_DAYS` and the seed were fixed in `score.py` before any screenshot was read. The
adjudication rules (hedged is not a call; retrospective is never a call; one call per date/asset/
direction; same-day contradictions are unscoreable) were fixed with them. The seven robustness cuts
in §1 were declared before the record was scored, not chosen after.

**The adjudication is a judgement and is exposed as one.** `adjudicate.py` maps corpus index →
call, and every row of `calls.csv` carries the index, the source screenshot and the verbatim text.
Disagree with a call and you can find it in seconds and re-run without it. Applying the rules
consistently cost the record some of its most memorable material — the "99k" call is explicitly
conditional (*"Incase we don't get rejection… could be upwards"*) and is therefore excluded, as is
every other hedged claim. Consistency beats anecdote.

**Three corrections I made to my own method, each of which changed the answer:**

1. The original control drew same-trend-state bars from six years of history while every call sits
   in five months of 2026. That measures the difference between two volatility regimes and bills it
   to the caller. Contemporaneous (±180d) controls are now primary; the six-year comparison gives
   −32.6% instead of −28.1%, and is reported as the looser number it is.
2. Requiring a contemporaneous control initially marked six resolvable calls "unresolved". A
   missing control does not make an outcome unknown — and same-state neighbours run short exactly
   at regime changes, so the loss was selective. Outcomes are now always resolved; the control is
   separately allowed to be absent.
3. The fabrication guard in `consolidate.py` checked the *old* OCR pass's field names, so it
   iterated two empty dicts and passed all 75 visual extractions without inspecting a single
   number. Pointed at the right fields, it drops one price that appears nowhere on its chart's
   axis. The consolidator also defaulted to the 16-image OCR subset, silently rebuilding the corpus
   at a quarter size with entirely plausible-looking counts.

**Limits, stated plainly.**

- **n_eff = 2.9.** Nothing here is statistically significant and nothing here should be read as if
  it were. Roughly 20–30 *non-overlapping* calls — two to three years of this posting cadence —
  would make the comparison mean something.
- **No multiple-comparison correction is applied** because no parameter was swept. One primary
  specification, one mandatory horizon display, seven pre-declared cuts. Had I searched for a
  horizon or threshold that made the numbers speak, this section would need a correction and the
  finding would not survive one.
- **Selection.** These are the screenshots that were sent to me. If they over-represent his
  memorable calls in either direction, the record inherits that bias and I cannot detect it.
- **Data.** BTC/XRP/ETH/SOL from a SHA-pinned Binance mirror to 25 Jul 2026; LINK's mirror stops
  21 Mar so it falls back to CoinMetrics closes (no intraday extremes — those rows understate
  excursions and are marked). DOGE is close-only to 23 May. GMX and SNDK have no series. Market-data
  APIs are egress-blocked, so there is no funding, open interest, or order flow anywhere in this.
- **One fabricated number** was found by adversarial re-read of the images (`IMG_7853`, a price
  present nowhere on that chart's axis, wrapped in a provenance claim asserting a tag pair that
  does not exist). It is stripped. 1 in 465 checked numbers; the rest of the transcription layer
  held up.

**Reproduce:**

```
.venv/bin/python -m research.ace_calls.consolidate   # 75 visual extractions -> corpus.json
.venv/bin/python -m research.ace_calls.adjudicate    # corpus.json -> calls.csv (42 calls)
.venv/bin/python -m research.ace_calls.score         # calls.csv -> the tables above
```

---

## The one-paragraph answer

He is a discretionary level-and-structure trader on high-leverage perps who is genuinely good at
naming prices that get touched and poor at naming direction and timing, and who has never once
published a stop. Over 27 scoreable calls he hit 22% against a same-regime control of 47%, his
shorts went 0-for-14, and 56% of his calls would have liquidated a 10× position before the horizon
closed — but with only 2.9 independent observations, that deficit is **not** statistically
distinguishable from bad luck, and any confident verdict in either direction is unsupported by the
evidence. The single documented position in 75 screenshots was a winner. His own message of 3 June
says a position held since February was in loss, and BTC's close that day matches his stated entry
to within 0.3%. The honest summary is that this corpus is enough to characterise **how** he trades
and nowhere near enough to establish **whether** he is profitable.
