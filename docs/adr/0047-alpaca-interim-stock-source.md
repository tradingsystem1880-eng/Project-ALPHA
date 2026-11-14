# ADR-0047: Alpaca's free plan is an interim, not-yet-confirmed stock source

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** The owner (use a free stock source until the Mac; Alpaca account to follow) and AI
build agents (how it is stored)

## Context

ADR-0017 makes Tiingo the authoritative daily stock and ETF source; Yahoo and Stooq are
comparison-only. On the Dell there is no Tiingo key, and the owner decided on 2026-11-14 to use a
free stock source until the Mac
([owner decisions](../reference/project/owner-decisions-2.md#2026-11-14-free-stock-prices-from-a-free-service-until-the-mac),
[and](../reference/project/owner-decisions-2.md#2026-11-14-any-free-stock-source-now-alpaca-account-to-follow)).
Alpaca's free Basic plan offers consolidated (SIP) daily history since 2016 once it is at least
15 minutes old, 200 calls a minute, for personal, non-commercial use (documentation and terms read
2026-11-14; quotes in the
[verification record](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-11/2026-11-14-alpaca-stock-data/04-verify.md)).

## Decision

- Add an `alpaca` daily-bar adapter on the existing receipt pipeline. It requests the SIP feed
  only (IEX is about 2.5% of volume, so its bars are not the market's) and never falls back to
  another feed.
- Store raw prices. Splits and cash dividends come from Alpaca's corporate-actions list as
  separate actions; with no announcement date in that list, knowledge falls back to the ex-date.
  A second, split-adjusted bar request is kept in the receipt and used only to cross-check every
  split; any disagreement, and any stock dividend, spin-off or unit split in the window, refuses
  the symbol.
- The receipt keeps every provider page byte for byte (a canonical envelope of the pages); keys
  come only from `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` and are never stored or printed.
- Alpaca is not authoritative: its data is labelled not yet confirmed, an Alpaca download never
  replaces Tiingo data, and it never merges into a series held from another source.
- Until the owner sets a key, Yahoo (`yfinance`) is used for personal research under the owner's
  decision above; Alpaca replaces it for new downloads once the key exists.

## Consequences

- Easier: real stock prices on the Dell now, and a keyed source that follows the adapter contract.
- Harder: history starts in 2016; a symbol with an action ALPHA cannot adjust is refused; a series
  cannot switch source in place (a separate data folder is used).
- Verified live on 2026-11-14 with the owner's key: the free plan serves SIP daily history; 15
  of 16 starter symbols came in, QQQ was refused on a duplicated dividend record, and a
  comparison with Yahoo is in the verification record.
- Confirmation of real data, and Tiingo as the authoritative source, still wait for the Mac.
