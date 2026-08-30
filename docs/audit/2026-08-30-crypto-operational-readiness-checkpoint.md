# Crypto operational-readiness checkpoint — 2026-08-30

## Decision

**NOT READY FOR RELEASE.** C0-C3 are complete. The isolated deterministic lifecycle and the
standalone no-order sandbox boundary are now exercised, but owner-machine crypto archive access,
full immutable rehash, the provider-backed BTC journey, the visible Workstation walkthrough, and
fresh owner Touch ID ceremonies remain open. No paper, broker, order, or live-capital authority is
enabled.

Evidence in this document was collected from branch `codex/generic-study-composition` starting at
`d80ddfead088ca3011432b1fa5ea92a8ded6bf13`. Generated owner data and immutable artifacts were not
deleted or rewritten.

## C4 owner storage and provider evidence

| Check | Fresh result | Interpretation |
|---|---|---|
| `diskutil info /Volumes/Expansion` | mounted; case-sensitive Journaled HFS+; media and volume read-only both `No`; UUID `758CBD77-1003-3BA3-AD28-1D647F5E2A08` | The mounted volume identity matches `ALPHA_BULK_VOLUME_UUID`. |
| Capacity | 2.0 TB total; 1,949,306,802,176 bytes free (97.5%) | Capacity and reserve are not the blocker. |
| Configured bulk root | `/Volumes/Expansion/Project-ALPHA/crypto-data` | The internal `.env` contains only the path and reviewed UUID, not provider credentials. |
| Process access | `ls`: `Operation not permitted`; shell read/write tests both `no` | The Codex process lacks macOS access to the configured directory. |
| `alpha crypto-data storage --json` | `blocked / bulk_volume_not_writable` | This is a release blocker, not a skipped success. |
| Internal control-plane inventory | 372 crypto manifests, 14 snapshots, one generated asset master, four immutable profiles, nine completed bounded batches | Counts are visible internally, but the referenced external bytes were not rehashed in this process. |
| Latest profile | `584cf038…b7bda8c`, 7,603 tasks | The earlier 7,602-task profile remains immutable; breadth completion is an operational backlog. |
| Scoped public network suite | 4 passed in 25.56 s | Binance public quote, Bybit BTC derivatives/options, CCXT BTC history, and CoinGecko/GeckoTerminal/Coin Metrics reference schemas were live-compatible. |
| CoinGecko governed check | canonical Keychain launcher returned `verified` at `2026-08-30T09:19:17.882241Z` | The launcher exposed no secret. An immediately prior keyless check recorded no capabilities and is not counted as success. |

Because the external bulk root cannot be read, `storage-inventory`, full `storage-verify`, exact
snapshot/feature/comparison revalidation, bounded batch resume, and the provider-backed BTC research
case cannot be accepted. ETH has no registered crowding empirical operator; ETH can be qualified as
provider-native data, but this release must not invent an ETH D1/D2 study path.

## C5 isolated lifecycle and sandbox evidence

The program acceptance now runs through public CLI surfaces in one temporary data directory:

1. raw idea, source pack, registered immutable dataset, D0, D1, and one-shot D2;
2. mechanical `SUPPORTED` classification and owner `advance_to_strategy` disposition;
3. promotion-linked registered `mean_reversion` development proxy, explicitly not a claim that the
   confirmed double-bottom detector is already an executable strategy;
4. matching research-contract-bound experiment and sealed final holdout;
5. suite-owned baseline, fixed-rule inner OOS, three validation null families, disclosed fake-model
   Kronos interface evidence, and classical plus Kronos path-risk Monte Carlo;
6. stored validation and Monte Carlo reports; and
7. a deterministic `StrategyProjectWorkspaceV1` whose validation/report indexes contain the linked
   immutable runs and whose authority remains `none`.

The acceptance found and closed two operational composition defects: `alpha project experiment`
could not relay the required promoted `research_contract_id`, and the two Monte Carlo commands did
not emit the canonical `-> run <id>:` token that the suite journal uses to link immutable results.

Fresh focused evidence:

- lifecycle plus related project/Monte Carlo regressions: 24 passed in 27.42 s;
- standalone hedged-basis candidate/suite boundary: 64 passed, 14 deselected in 2.10 s;
- live standalone preflight: `BLOCKED / UNSUPPORTED_MULTI_VENUE_PAPER`, with
  `credentials_requested`, `broker_connection_attempted`, `order_created`, `fill_created`, and
  `position_changed` all false.

This does not complete C5. The owner archive is inaccessible, so no provider-backed BTC research
journey was run. The in-app browser discovery returned no connected browser backend, so the required
visible Research → semantic study → project workspace → Build → Results → Crypto Data Center
walkthrough was not performed. Fresh Touch ID actions also remain owner-performed.

## Required recovery and rerun

1. In macOS Settings, grant the Codex application access to the Expansion volume (Files and Folders
   removable-volumes access, or the applicable Full Disk Access entry), then restart the Codex app
   if macOS requires it.
2. Confirm `ls /Volumes/Expansion/Project-ALPHA/crypto-data` no longer returns `Operation not
   permitted`.
3. Run, in order:

   ```bash
   uv run alpha crypto-data storage --json
   uv run alpha crypto-data storage-inventory --json
   uv run alpha crypto-data storage-verify --json
   uv run alpha crypto-data profiles --json
   uv run alpha crypto-data profile-batches --json
   uv run alpha crypto-data asset-masters --json
   scripts/alpha-with-keychain-provider coingecko check
   ```

4. Reverify the exact BTC/ETH core manifests, asset master, snapshots, derived features, and
   Binance-primary/Coinbase comparison; run or resume only bounded due profile pages.
5. Run the provider-backed BTC case only to the evidence state mechanically supported by its
   results. Stop ETH at qualified data readiness unless a separate governed operator is approved.
6. Connect an in-app browser, perform the six-area visible walkthrough, and have the owner perform
   every fresh Touch ID ceremony personally.
7. Only after the blockers above close, run C6 review/gates, exact-SHA GitHub checks, merge, and
   post-merge smokes.
