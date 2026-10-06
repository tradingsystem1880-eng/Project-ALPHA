# DefiLlama Integration and Crypto Data Hygiene

## Context

The current crypto archive has broad provider plumbing but uneven usable coverage. Its metadata inventory reports 33,536 total manifests and 11,775 normalized records; the last observed CoinGecko, Coin Metrics, and GeckoTerminal artifacts are from August 2026. Several provider families have warning or quarantined artifacts. The full artifact verifier did not complete during the initial audit. The user requested a DefiLlama integration, removal of obsolete APIs, and cleanup of unusable old data.

## Goal

Add bounded, provider-native DefiLlama protocol TVL, stablecoin supply, and yield pool/history acquisition that is discoverable through the existing CLI/API/UI and can be qualified and frozen into immutable crypto snapshots. Audit provider usage and archive defects. Keep source lineage and snapshot reproducibility intact; only remove artifacts when verification proves they are corrupt, they are not referenced by any retained derived artifact/snapshot, and the deletion is recorded in an auditable cleanup receipt.

## Invariants and impact

- Preserve provider, venue/network, instrument, unit, frequency, timestamp, and quote identity. Never merge provider histories or infer ticker identity.
- Discovery metadata is not artifact verification. Verify selected inputs and raw lineage before feature or snapshot use.
- Do not mutate or delete snapshot members, their raw parents, derived outputs, or qualified historical data. Retain quarantined source bytes unless they meet the explicit corruption and unreferenced checks above.
- DefiLlama is a new external adapter only; no engine imports, automatic fallback, or execution authority. HTTP stays bounded to allowlisted hosts/paths, with no credentials in URLs or receipts.
- Historical TVL/stablecoin/yield observations remain point-in-time with provider timestamps; a current yield-pool listing is a snapshot, not backfilled history.
- No changes to the canonical daily backtest store or its point-in-time reader.

## Slices

1. **Provider wire contracts and parsers** — add an allowlisted DefiLlama client and strict parsers for protocol TVL, stablecoin supply, current yield-pool catalog, and pool history. Add parser/URL negative tests for malformed payloads, invalid IDs, unexpected hosts, empty data, duplicate observations, and numeric/timestamp errors. Verify: focused provider tests and Ruff.
2. **Typed families and qualification** — register the provider families, frequencies, limits, units, and mechanical quality rules; expose them in capability/catalog responses and typed API contracts. Verify: contract, capability, and quality tests.
3. **Acquisition integration** — add CLI request planning and response-size bounds and provider dispatch, then ensure the existing acquisition API relays the exact typed request. Verify: CLI acquisition tests with injected transport and representative API tests; no live persistence in tests.
4. **UI support and research handoff** — add DefiLlama to the provider selector, family sections, and parameter fields; leave the pool-history UUID blank until selected from catalog data, with copy distinguishing current catalog snapshots from history; ensure acquired qualified records can be selected and frozen for research with exact lineage. Verify: focused UI model/component tests and generated API freshness.
5. **Data/provider hygiene** — map every provider integration to reachable CLI/API/UI use; remove only proven dead routes/adapters. Audit archive and references before any immutable-data purge. Do not treat age or warning/quarantine labels alone as proof of corruption; the current storage API supports deletion only for the explicitly disposable cache. Verify: provider route/use audit, archive inventory if mounted, and full storage verification if it completes.
6. **Documentation and gates** — update applicable operating documentation/build state with actual provider limits, cleanup semantics, and verification evidence. Run focused tests, frontend component gate as applicable, and canonical full gate; report every unverified item honestly.

## DAG and bias impact

Changes are confined to `alpha_data.crypto` provider/contracts/quality/capabilities, CLI orchestration, web typed relay, and Workstation data-management UI. There is no new dependency from data into strategies or engines. The data is supplemental research input, not a signal claim. Point-in-time availability uses acquisition timestamps; derived feature availability cannot precede any source input.

## Acceptance and observed implementation state

- Four DefiLlama data families parse and acquire bounded records; malformed inputs fail closed.
- Capabilities identify exact family/provider and no execution authority.
- Qualified DefiLlama datasets are visible and can be frozen; warning/quarantined datasets cannot be bound as qualified inputs.
- No immutable artifact has been deleted. Existing provider adapters remain reachable in current route/use mapping; no dead integration was established by the audit.
- A live bounded acquisition succeeded and recursive manifest/raw-lineage verification passed for all four families: Aave protocol TVL (2,328 rows), stablecoin id `1` supply (3,230), current yield-pool catalog (17,061), and one Aave/Ethereum pool's history (902). Each is qualified; immutable archive artifacts were retained.
- Disposable cache cleanup removed 2,190 bytes; immutable artifacts removed: zero.
- Backend and frontend gates passed; Atlas and eval component gates passed after regenerating Atlas output. A full-gate attempt stopped at Atlas freshness before regeneration, so the full aggregate command has not yet passed on the final generated tree. Full archive integrity inventory remains unverified.


## 2026-10-02 review correction and retirement contract

Stablecoin circulating balances are native USD-pegged token units, not historical USD valuations. Version 2 uses native units and no quote asset. Availability is acquisition time, never observation time. Reject naive timestamps and canonicalize pool UUIDs. The local pool picker verifies catalog bytes and raw lineage before selection.

Retirement preserves canonical manifests, qualification reports and immutable payloads. Append hash-bound receipts for unreferenced quarantined inputs and the known v1 stablecoin units error; exclude them from active discovery and new explicit-ID snapshot/derived admission. Historical verification remains available. Malformed receipts fail closed. Serialize local reference rechecks and retirement with snapshot/derived admission. Retain referenced flagged records and all warning records. This is discovery retirement, not byte corruption or reclaimed storage.

```json
{"feature":"defillama-and-crypto-data-hygiene","status":"delivered","slices":["provider-contracts","qualification","acquisition","verified-pool-picker","reference-audited-retirement","gates-and-review"],"authority":"supplemental-research-only","dag_impact":"external-data-adapter-no-engine-dependency","lookahead":"availability-at-acquisition","determinism":"immutable-lineage-and-hash-bound-retirement"}
```


Retirement applied: seven unreferenced quarantines and the first incorrect-unit stablecoin capture
are inactive for discovery/admission, with zero immutable deletions. The corrected live supply
capture is `ba8213d45cbe2bf74575ee519839a4432005eee5449c08c15d83a9529c6bfd65`.
Reference audit binds receipt `aa8cae59a5e73daecda4ba28ef50460eed5a8d4f46b9d8fa9ccebaa6c45972fb`;
52 referenced quarantines and all warnings remain. Independent review approved the bounded
retirement behavior after fixing traversal, inventory filtering and atomic-publication findings.

**Acceptance (2026-10-05):** the canonical full gate passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC, all six components, 969 s); see the 2026-10-05 record in `docs/BUILD-STATUS.md`. Full archive-wide byte integrity remains a separate, unclaimed inventory.
