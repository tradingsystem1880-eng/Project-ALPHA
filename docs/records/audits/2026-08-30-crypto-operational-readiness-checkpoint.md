# Crypto operational-readiness checkpoint — 2026-08-30

## Decision

**NOT READY FOR RELEASE.** C0-C3 are complete. The isolated deterministic lifecycle, standalone
no-order sandbox boundary, owner-machine crypto archive access, and full immutable rehash are now
exercised. The provider-backed BTC journey, visible Workstation walkthrough, and fresh owner Touch
ID ceremonies remain open. No paper, broker, order, or live-capital authority is enabled.

Evidence in this document was collected from branch `codex/generic-study-composition` starting at
`d80ddfead088ca3011432b1fa5ea92a8ded6bf13`. Generated owner data and immutable artifacts were not
deleted or rewritten.

The Expansion recovery evidence below was collected on `main` on 2026-08-31 after enabling iTerm's
macOS removable-volumes access. The bounded access probe was deleted immediately after its
create/write/hash check; no governed artifact was changed.

## C4 owner storage and provider evidence

| Check | Fresh result | Interpretation |
|---|---|---|
| `diskutil info /Volumes/Expansion` | mounted; case-sensitive Journaled HFS+; media and volume read-only both `No`; UUID `758CBD77-1003-3BA3-AD28-1D647F5E2A08` | The mounted volume identity matches `ALPHA_BULK_VOLUME_UUID`. |
| Capacity | 2.0 TB total; 1,949,306,789,888 bytes free (97.5%) | The 1.949 TB free capacity exceeds ALPHA's 100 GB minimum and 15% reserve. |
| Configured bulk root | `/Volumes/Expansion/Project-ALPHA/crypto-data` | The internal `.env` contains only the path and reviewed UUID, not provider credentials. |
| Process access | exact-root list plus create/write/SHA-256/delete probe all exited zero | iTerm removable-volumes access now reaches the configured directory; the temporary probe left no residue. |
| `alpha crypto-data storage --json` | `ready`; 372 manifests; 2,190 cache bytes | UUID, capacity, reserve, directory, and write-probe gates pass. |
| `alpha crypto-data storage-inventory --json` | 372 manifests: 262 raw, 97 normalized, 13 derived; 14 snapshots; zero staging; no private paths | The external inventory is readable without exposing absolute private paths. |
| `alpha crypto-data storage-verify --json` | `verified`; 372 manifests, 14 snapshots, 13 research-eligible snapshots, one asset master | Every external artifact was rehashed and frozen snapshot membership rederived successfully. |
| Governed projections | four immutable profiles; nine of nine batches completed; two asset masters verified; 12 feature artifacts verified | The repaired storage boundary supports the higher-level read-only projections; authority remains false. |
| Latest profile | `584cf038…b7bda8c`, 7,603 tasks | The earlier 7,602-task profile remains immutable; breadth completion is an operational backlog. |
| Scoped public network suite | 4 passed in 23.91 s on 2026-08-31 | Binance public quote, Bybit BTC derivatives/options, CCXT BTC history, and CoinGecko/GeckoTerminal/Coin Metrics reference schemas are live-compatible. |
| CoinGecko governed check | canonical Keychain launcher returned `rate_limited` at `2026-08-30T15:15:08.082896Z` | This is an explicit current provider blocker, not a skipped success. The earlier verified receipt remains historical evidence only. |

The external-storage release blocker is closed. Historical warning and quarantined acquisitions
remain immutable non-evidence and were not rewritten. The provider-backed BTC research case remains
open because this recovery run did not manufacture a research result from storage integrity alone.
ETH has no registered crowding empirical operator; ETH can be qualified as provider-native data,
but this release must not invent an ETH D1/D2 study path.

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

This does not complete C5. The archive is now accessible and verified, but no provider-backed BTC
research journey was run. The in-app browser discovery returned no connected browser backend, so
the required visible Research → semantic study → project workspace → Build → Results → Crypto Data
Center walkthrough was not performed. Fresh Touch ID actions also remain owner-performed.

## Remaining acceptance work

1. Run the provider-backed BTC case only to the evidence state mechanically supported by its
   results. Stop ETH at qualified data readiness unless a separate governed operator is approved.
2. Connect an in-app browser, perform the six-area visible walkthrough, and have the owner perform
   every fresh Touch ID ceremony personally.
3. Only after the blockers above close, run C6 review/gates, exact-SHA GitHub checks, merge, and
   post-merge smokes.
