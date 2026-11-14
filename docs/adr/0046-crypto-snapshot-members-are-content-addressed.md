# ADR-0046: A crypto snapshot member is its content; equal recaptures count as one

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** AI build agents, under the owner's standing direction that every data fault fails loud

## Context

A governed crypto snapshot ([ADR-0032](0032-governed-crypto-data-house.md)) freezes, for each
member, the dataset identity, the normalized artifact's content-addressed key and its SHA-256. It
does not freeze which normalized manifest published those bytes. Downloading the same provider
file again (on the Dell on 2026-11-14: a test pull of Binance BTCUSDT January 2024, then the
backfill) publishes a second normalized manifest for the same bytes; the two differ only in their
own id and their raw inputs' fetch time.

Before this decision creation and verification used different rules. `snapshot-create` resolved
only the manifest the caller named and accepted it; `snapshot-verify` (and `storage-verify`, which
re-verifies every snapshot) required exactly one retained manifest per member and refused the
second as "ambiguous". A snapshot that could be created could never be verified again, and one
honest repeat download made the whole-store check fail for ever, with no legitimate way out:
snapshots are immutable and cannot be deleted.

Options considered:

| Option | Effect | Verdict |
|---|---|---|
| Keep "exactly one manifest", apply it at creation too | No false acceptance, but a repeat download still breaks every existing snapshot of that month | Rejected: an honest repeat download corrupts the store |
| Refuse or skip the second download at fetch time | Hides a real re-observation (proof the provider's file is unchanged) and leaves stores that already hold duplicates stuck | Rejected |
| Mark stuck snapshots superseded | Needs a new owner-visible record type; does not stop the next repeat download from breaking another snapshot | Not needed once the rule is fixed |
| **Treat equal recaptures as one capture; refuse any that differ** | Matches the content-addressed member; anything that differs still fails loud | **Chosen** |

## Decision

- **One rule, one place.** `apps/alpha-cli/src/alpha_cli/_crypto_snapshot_members.py` resolves a
  member for both `snapshot-create` and every verification path (`snapshot-verify`,
  `storage-verify`, research registration). Creation therefore refuses exactly what verification
  refuses.
- **Equal recaptures are one capture.** Several active normalized manifests that carry a member's
  exact dataset, artifact key and artifact hash count as one capture only when they are identical
  in everything except per-fetch provenance: the normalized manifest's own id and raw-input ids,
  and, in each raw input, its manifest id, storage key, receipt id and fetch time. Quality report
  (including correction lineage and method version), acquisition scope, provider, byte counts,
  request, response hash, upstream checksum, parser and schema versions must all be equal.
  Anything else is "ambiguous" and fails loud, at creation and at every later verification.
  The representative manifest is the one with the smallest id, so the choice is deterministic.
- **Repeat downloads stay allowed and recorded.** The second download keeps its own raw receipt
  and normalized manifest (it proves the provider's file was unchanged at a later time); nothing is
  refused, skipped or merged at download time.
- **Membership is canonical.** `snapshot-create` freezes members in one canonical order (dataset
  identity, then observed start, then artifact hash), so the snapshot id does not depend on the
  order of `--manifest-id` options. Naming one capture twice is refused. Members of one dataset
  must each have an observed range, and the ranges must not overlap; this is checked at creation
  and at verification. `CryptoSnapshotV1` is unchanged: snapshots stored in any order still verify.

Where ADR-0032 says research consumes "one exact qualified `CryptoSnapshotV1`", this record
defines what exact means for a member: its content, with all retained captures of that content in
agreement.

## Consequences

- The Dell's stuck snapshot `c8ab0d2a…6226` verifies under the corrected rule, without editing any
  receipt, manifest or snapshot; `storage-verify` passes on the real data folder (recorded in
  `docs/work/archive/2026-11/2026-11-14-crypto-snapshot-duplicates/04-verify.md`).
- A later capture of the same bytes whose provenance differs (for example a correction lineage
  that appeared because the provider changed the file in between) makes every snapshot holding
  those bytes fail verification. That is intended: the provider's history is no longer one story.
- A snapshot that holds several months of one pair is now well defined. Readers that require one
  member (the daily price query in `crypto_price_snapshot_query.py`, bound to daily-rule owner
  approvals) are unchanged.
- `crypto_bulk_store.py`, `control_store.py` and the other daily-rule guard files are unchanged, so
  no owner approval is invalidated.

Tests: `tests/unit/test_crypto_snapshot_members.py`,
`tests/integration/test_crypto_snapshot_duplicates_cli.py`.
