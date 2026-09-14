# ADR-0036: Add DefiLlama chain TVL as a supplemental crypto research family

**Status:** Accepted
**Date:** 2026-09-14
**Deciders:** Project ALPHA owner and AI build agents

## Context

The neurotrader888 port (`docs/superpowers/plans/2026-09-12-neurotrader888-port.md`, stream D)
carries one indicator whose input is not a market price: the TVL indicator regresses a chain's
log total value locked (TVL) on log price over a trailing window and reports the residual in ATR
units. Its data comes from DefiLlama, a keyless public API that no existing family covers.

ADR-0032 governs crypto data by dataset family with one provider authority per family, explicit
availability time on every observation, and no authority gained by analogy. Adding TVL therefore
needs its own record: the family, its authority, its market type and units, what it may and may
not evidence, and how the DefiLlama terms are honoured in receipts.

DefiLlama's `https://api.llama.fi/v2/historicalChainTvl/{chain}` endpoint returns a JSON array of
`{"date": <unix seconds>, "tvl": <usd float>}` rows, one per UTC day. It is documented as free for
non-commercial use with attribution. The endpoint could not be reached from the build sandbox
(egress-blocked), so the parser is written against a recorded fixture and the live shape is
confirmed by the owner's first `alpha provider check defillama` receipt.

## Decision

Register one new family, `defi_tvl`, with `defillama` as its sole provider authority:

| Field | Value |
|---|---|
| family | `defi_tvl` (`alpha_data.crypto.contracts.CryptoFamily`, `FAMILY_AUTHORITIES["defi_tvl"] == "defillama"`) |
| market type | `network` — the instrument is a chain name (`ethereum`, `arbitrum`, ...), never a pair |
| quote / units | `USD` (`--quote USD`); `--base` carries the chain's native asset symbol for the identity only |
| frequency | `1d` only; DefiLlama publishes one end-of-day point per chain |
| observation time | `observed_at` = the row's UTC day start |
| availability time | `available_at` = the next UTC day boundary (a day's TVL is only complete after that day closes) |
| research eligibility | supplemental (`_SUPPLEMENTAL_FAMILIES`); never a provider-native price family, so `validation`/`execution_price` requests are rejected with `provider_native_price_required` |
| feature | `defi_tvl_residual` (`alpha_data.crypto.features`): trailing log-log OLS of TVL on close over a positive-lag window, residual divided by the ATR of the same market bars; `available_at` is the maximum of both inputs' availability |
| provider registration | `alpha_cli.providers` entry `defillama` (`credential_names=()`, `budget_tier="free_public"`, `research_authority=True`, `paper_execution=False`); `alpha provider check defillama` records a `ProviderCheckReceiptV1` from one bounded request |
| acquisition | `alpha crypto-data acquire defillama defi_tvl <chain> --base <asset> --quote USD --frequency 1d`; a closed endpoint table, host-prefix check, byte cap, epoch-seconds decoding with the 2010–2100 window |

The feature is computed inside `alpha_data.crypto.features` with a numpy trailing OLS and ATR
rather than by importing `alpha_patterns.vsa.rolling_ols_residual`: the import-linter contract
`alpha_data depends only on core` forbids the cross-import, and moving the feature into `alpha_cli`
would strand `available_at` propagation outside the data layer. The two implementations are pinned
equal by a unit test.

Receipts follow ADR-0032: provider, endpoint, request, response hash, fetch time, parser version,
access tier `free_public`, the attribution note `"Data: DefiLlama (https://defillama.com), free for
non-commercial use with attribution"`, and the retention note `"raw bytes retained locally for the
owner's private research only; never redistributed or hosted"`. A terms change or removal request
disables acquisition first and tombstones dependent snapshots through the existing inventory path.

## Consequences

- ALPHA gains a governed non-price family with honest availability lag; TVL can inform research
  studies but cannot serve as validation or execution evidence, and no gauntlet gate consumes it.
- The provider is keyless and public; there is no credential, quota token, or paper/broker path.
- Live behaviour is receipt-driven: until the owner records a successful `alpha provider check
  defillama`, the family's live readiness is an honest UNVERIFIED environment state, not a pass.
- `CryptoFamilyValue`, `CryptoProviderValue`, and `CryptoFeatureNameValue` in the web contract gain
  one member each; the generated OpenAPI/TypeScript is regenerated in the same change.
- MCP stays pinned at 62 tools; acquisition remains CLI-only.
