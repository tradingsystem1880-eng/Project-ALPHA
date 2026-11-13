# ADR-0043: Storage reserve is an owner-set value; the default stays 100 GB / 15%

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** Project ALPHA owner (the decision) and AI build agents (the mechanism)

## Context

[ADR-0032](0032-governed-crypto-data-house.md) requires that, before ALPHA writes market data to
its storage, free space stays above a reserve: the larger of 15% of the disk and 100 GB. The rule
lives in `packages/alpha-data/src/alpha_data/crypto/storage.py:CryptoBulkStore.verify_ready` and
is applied to every store reopened from `<data dir>/crypto/storage-config.json`
(`apps/alpha-cli/src/alpha_cli/crypto_bulk_store.py:configured_crypto_bulk_store`).

The development machine (a Dell, 114 GB disk, about 48 GB free) can never meet a 100 GB reserve,
so no data could be stored there at all. On 2026-11-14 the owner decided:

> "Can we just use the disk space available on the Dell for now. I will worry about it when it
> gets low on free disk space."

## Decision

- The reserve becomes a value the owner sets per storage root, in the retained storage settings
  file, as an optional `free_space_reserve` object (schema `OwnerStorageReserveV1`): the reserve
  in bytes, an advisory "low space" threshold, who decided, the date, and where the decision is
  written down. The code only validates these fields; it never supplies them, so it cannot invent
  an approval (`crypto_bulk_store.py:OwnerStorageReserveV1`).
- **Default unchanged.** With no `free_space_reserve` the ADR-0032 rule (larger of 15% and
  100 GB) applies exactly as before. Existing settings files keep their bytes and their hash.
- **Hard floor.** No reserve or advisory value below 10 GB (`RESERVE_FLOOR_BYTES`
  = 10,000,000,000 bytes) is accepted; zero, negative, fractional and unattributed values are
  rejected as invalid configuration.
- **Refusal kept.** A storage write whose size would leave less than the reserve is still refused
  before any byte is written; the refusal now states the free space, the request, the reserve and
  who set it (`ConfiguredCryptoBulkStore.verify_ready`).
- **Advisory.** Below the advisory threshold `alpha crypto-data storage` prints a `LOW DISK SPACE`
  notice and `scripts/gate.py doctor` reports it; the advisory never refuses on its own.
- The Dell's setting is reserve 10 GB, advisory 20 GB, created by the owner with
  `scripts/storage_settings.py write` (see `docs/operations/storage-settings.md`).

## Consequences

- Studies on the Dell may run with far less headroom than ADR-0032 intended (10 GB instead of
  100 GB). Data acquisition that needs more than the remaining space minus 10 GB is refused
  before it writes; anything that grows past the reserve after its check can still fail. The
  owner revisits this when space gets low.
- Adding the reserve to an existing settings file changes that file's hash. A daily study frozen
  against the old bytes then refuses to start ("storage profile changed after freeze") until it is
  re-drafted; this is intended, not silent.
- `crypto_bulk_store.py` is part of the daily rule's implementation fingerprint, so daily contracts
  drafted before this change must be re-drafted; no approval is carried over automatically.
- Not changed here: the QuantPad archive's own reserve (`alpha_data/quantpad_archive.py`), and the
  daily study launch itself, which today checks storage identity but not free space.

Tests: `tests/unit/test_storage_reserve.py`.
