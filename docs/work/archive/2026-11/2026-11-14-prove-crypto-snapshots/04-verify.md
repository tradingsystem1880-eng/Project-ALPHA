# Verification: "Freeze crypto data into exact snapshots and check them" end to end

Run on the Dell on 2026-11-14 (UTC), branch `m8/prove-crypto-snapshots` (based on the unmerged
`m8/prove-crypto-data`, which holds the recorded provider).

## Offline, through the installed program (the smoke check)

`tests/smoke/test_crypto_snapshots_smoke.py`, 2 passed (25 s), plus the crypto-data smoke checks
still passing after the recorded provider change below. Steps: three monthly archives and one
REST tail download `qualified`; `asset-master-verify reviewed-native-v1` is `verified`;
`snapshot-create` with the three ids in either order gives the same id, `frozen`, 3 members;
`snapshot-verify --required-family market_bars` is eligible with no blockers; a snapshot of the
February archive plus the overlapping February tail is refused (exit 2, "disjoint observed
ranges") and no snapshot file appears; a second identical download of January leaves the
snapshot eligible (ADR-0046); `storage-verify` is `verified` with 1 snapshot; after one byte of
the ETH January artifact is flipped, `snapshot-verify` and `storage-verify` both exit 2 and say
nothing is eligible or verified. Through the installed `alpha-web`,
`POST /api/crypto-data/snapshots/<id>/verify` answers eligible.

Two things the run found:

- `asset-master-verify reviewed-native-v1` answered "crypto asset-master version is invalid"
  although `asset-masters` lists both built-in versions as verified and `snapshot-create` uses
  v1 by default (confirmed on the real folder first). Fixed: built-in labels resolve exactly;
  a stored custom master is still source-verified. Test first: the in-process CLI test fails on
  the base branch.
- The first synthetic recording gave BTC and ETH byte-identical normalized files, and
  `snapshot-create` refused them as "the same capture more than once". Creation and
  verification both key members by artifact hash (`alpha_data.crypto.research` raises
  `duplicate_snapshot_artifact`), so they agree; changing that is a research-eligibility rule and
  was not touched. Real coins never share bytes; the recorded prices now differ by coin. The
  message names a "capture" where two datasets are meant: noted, not changed.
- `post_json` posts to `localhost`: `alpha-web` redirects `127.0.0.1` to `localhost` with a 307
  (WebAuthn origin), and urllib does not resend a POST body across it.

## For real

Read-only on the real folder (`ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`):

```text
alpha crypto-data storage-verify --json -> "state": "verified", 2854 manifests, 2 snapshots, 9.0 s
alpha crypto-data snapshot-verify a9202603... --purpose research --required-family market_bars --json -> eligible, no blockers
alpha crypto-data asset-master-verify reviewed-native-v1 --json -> exit 2 "version is invalid"   (before the fix)
```

On the copy of the folder (`/home/hunta/alpha-clean-base/tmp/prove-crypto/data`):

```text
alpha crypto-data snapshot-create <222 x --manifest-id> --json      (every BTC and ETH month 2017-08..2026-10)
-> snapshot d1cc356d..., "frozen", member_count 222, 3.7 s
alpha crypto-data snapshot-verify d1cc356d... --required-family market_bars --json -> eligible, no blockers, 4.3 s
```

The 222 ids had to be collected from `coverage --json` with a script, and the one month
downloaded twice resolved by hand: filed as backlog `crypto-snapshot-by-range`. After the
backfill proof added 111 more ETH captures to the copy, the snapshot still verified and
`storage-verify` was `verified` (3,080 manifests, 3 snapshots).

## Checks

- New unit and CLI tests for the built-in asset masters: the CLI one fails on the base branch.
- `uv run python scripts/gate.py check --all`: see the pull request.

## Review

Codex built slice 1 and the smoke check in one round; `handoff.py` stopped on a scope rule (it
also added `post_json` to `tests/smoke/_harness.py`, which the plan allowed in its text but not in
`files`). Claude reviewed the diff, ran the checks outside the sandbox and made the two fixes
above by hand.

## Plans closed

`2026-11-08-snapshot-capture-binding` moved to the archive as superseded: its "refuse every
repeat capture" rule was replaced by ADR-0046; its tamper refusals are proven by the smoke check.
`2026-11-08-asset-master-source-provenance` stays live: custom asset masters are not run end to
end here.

## Not proven here

`snapshot-query` (DefiLlama TVL pages; the recorded provider serves Binance only); custom asset
masters built from CoinGecko and GeckoTerminal catalogs.
