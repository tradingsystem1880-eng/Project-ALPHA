# Prove "Freeze crypto data into exact snapshots and check them" end to end

**Delivery state:** Completed — built, reviewed and verified on branch `m8/prove-crypto-snapshots`; done when its pull request merges.
**Build class:** standard — one smoke check and a small command fix; based on the unmerged recorded provider of `m8/prove-crypto-data`.

Filed straight into the archive, as `2026-11-14-crypto-snapshot-duplicates` was: the
work-in-progress ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- A new automatic check freezes downloaded crypto months into a snapshot with the real `alpha`
  program, checks it, and proves the snapshot is refused once any frozen file changes.
- `alpha crypto-data asset-master-verify reviewed-native-v1` used to say "version is invalid" for
  the two built-in asset masters that `asset-masters` lists as verified; it now verifies them.
- On a copy of your data folder, one snapshot of the whole BTC and ETH daily history (222 months)
  was created and verified in a few seconds.
- Nothing for you to decide here.

```json
{
  "schema_version": 1,
  "title": "Prove Freeze crypto data into exact snapshots and check them end to end",
  "context": "crypto-snapshots is Partial (in-process tests only). The recorded provider from m8/prove-crypto-data lets the installed alpha download several months offline, so snapshot-create, snapshot-verify and storage-verify can be proven end to end. Running the commands on the Dell found that asset-master-verify refuses the built-in versions reviewed-native-v1 and reviewed-native-v2 with 'crypto asset-master version is invalid' (_read_asset_master accepts only SHA-256 versions) while asset-masters lists them as verified and snapshot-create uses reviewed-native-v1 by default.",
  "assumptions": [
    {"statement": "Built-in asset masters are AssetMaster.with_reviewed_native_assets(label) for label in REVIEWED_NATIVE_LABELS and have no retained catalog sources; crypto_data_cmds already resolves them that way when verifying a snapshot (around line 664).", "verified_by": "crypto_data_cmds.py asset_masters and the snapshot verification path"},
    {"statement": "A snapshot member binds dataset, artifact key and artifact hash; verification re-hashes the stored artifact (ADR-0046).", "verified_by": "docs/adr/0046-crypto-snapshot-members-are-content-addressed.md"},
    {"statement": "crypto_data_cmds.py may not grow (code-size ratchet).", "verified_by": ".claude/code-size-baseline.json"}
  ],
  "alternatives_considered": [
    "Remove the built-in versions from asset-masters: rejected, snapshot-create defaults to reviewed-native-v1, so the listing is right and the verify command is wrong.",
    "Prove snapshot-query too: deferred, it reads DefiLlama TVL pages only and the recorded provider serves Binance hosts only."
  ],
  "pre_mortem": [
    "The tamper step damages something outside the throwaway home: it edits one artifact inside crypto_home only, located through the manifest's artifact_key.",
    "The builtin branch lets a custom master with a builtin-looking name skip source verification: names are matched exactly against REVIEWED_NATIVE_LABELS, which are not SHA-256 strings, so a stored custom master can never take that branch."
  ],
  "slices": [
    {"title": "asset-master-verify accepts the built-in versions it lists", "verify": "uv run pytest -q tests/unit/test_crypto_asset_master_sources.py tests/integration/test_asset_master_provenance.py", "expected": "all pass; the new builtin test fails on the base", "rollback": "revert the two source files and the test", "status": "pending"},
    {"title": "Snapshot smoke check through the recorded provider", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_snapshots_smoke.py", "expected": "2 passed", "rollback": "delete the smoke file", "status": "pending"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/roadmap/capabilities.toml", "STATUS.md", "docs/roadmap/README.md", "docs/roadmap/wip-limit.json"],
  "out_of_scope": ["apps/alpha-cli/src/alpha_cli/crypto_price_snapshot_query.py", "packages/alpha-data/src/alpha_data/crypto/providers/", "packages/alpha-research/src", "packages/alpha-validation/src", "stored data"],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_crypto_asset_master_sources.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "tests/unit/test_crypto_asset_master_sources.py",
    "tests/smoke/test_crypto_snapshots_smoke.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [command line crypto data](../../../../reference/invariants/cli-crypto-data.md) | Immutable documents; Bulk storage | always |
| [ADR-0046](../../../../adr/0046-crypto-snapshot-members-are-content-addressed.md) | Decision | always |
| [tests workspace](../../../../../tests/CONTEXT.md) | How to change it | always |
| [crypto-data smoke check](../../../../../tests/smoke/test_crypto_data_smoke.py) | — | slice 2: the pattern to follow |
| [recorded provider](../../../../../tests/smoke/_recorded_provider.py) | — | slice 2 |

## Slices

### 1. asset-master-verify accepts the built-in versions it lists

Add `builtin_asset_master(version: str) -> AssetMaster | None` to
`apps/alpha-cli/src/alpha_cli/_crypto_asset_master_sources.py`: returns
`AssetMaster.with_reviewed_native_assets(version)` when `version` is exactly one of
`REVIEWED_NATIVE_LABELS` (import it from where `crypto_data_cmds.py` does), else `None`. In
`crypto_data_cmds.py` `asset_master_verify`, the one line `master = _verified_asset_master(...)`
becomes one line `master = builtin_asset_master(version) or _verified_asset_master(_bulk_store(),
version)`; the import joins the existing import of that module. No other call site changes. The
file's line count must not grow. Output for a built-in: `source_manifest_ids` is `[]`, `state`
`verified`. Tests (new `tests/unit/test_crypto_asset_master_sources.py`, or the existing asset-master
test file if one covers this module): both labels return a master whose identities equal
`with_reviewed_native_assets(label)`; a 64-hex string and `reviewed-native-v9` return `None`; and
an in-process CLI test (`CliRunner`, temporary data folder in the style of
`tests/integration/test_asset_master_provenance.py`) that `asset-master-verify reviewed-native-v1
--json` exits 0 with state `verified`, which fails on the base.

### 2. Snapshot smoke check

`tests/smoke/test_crypto_snapshots_smoke.py`, following `tests/smoke/test_crypto_data_smoke.py`:

1. `test_snapshot_freezes_months_verifies_and_refuses_a_changed_file(crypto_home)`: record
   BTCUSDT 2024-01, BTCUSDT 2024-02 and ETHUSDT 2024-01 archives and a BTCUSDT REST tail for
   2024-02-10 to 2024-02-12; acquire the three archives (`--period`) and the tail with the
   installed `alpha`. Then, every call with `env=provider.env()`:
   - `crypto-data asset-master-verify reviewed-native-v1 --json`: `state` `verified`.
   - `crypto-data snapshot-create --manifest-id A --manifest-id B --manifest-id C --json` and the
     same with the ids in reverse order: both `frozen`, `member_count` 3, the same `snapshot_id`.
   - `crypto-data snapshot-verify <id> --required-family market_bars --json`: `eligible` true,
     `blockers` empty.
   - `crypto-data snapshot-create` with the BTCUSDT February archive and the February tail
     (overlapping days): refused (non-zero exit), no new snapshot file.
   - Acquire BTCUSDT 2024-01 again (a second identical capture): `snapshot-verify` still
     `eligible` true (ADR-0046).
   - `crypto-data storage-verify --json`: `state` `verified`, `snapshot_count` 1.
   - Change one byte of the ETHUSDT January normalized artifact inside `crypto_home` (find its
     path from that manifest's `artifact_key` under `<data>/bulk/`; make it writable first if
     needed). `snapshot-verify` must then not report `eligible` true: assert a non-zero exit or
     `eligible` false with a blocker, and record which in a comment; `storage-verify` must not
     report `verified`.
2. `test_workstation_verifies_the_snapshot(crypto_home)`: after downloading two archives and
   creating the snapshot as above, `web_server(crypto_home)` answers
   `POST /api/crypto-data/snapshots/<id>/verify` with JSON body
   `{"required_families": ["market_bars"], "purpose": "research"}` (check the request model in
   `apps/alpha-web/src/alpha_web/api/` for the exact field names) with `eligible` true. Add a small
   `post_json(url, body)` helper to `tests/smoke/_harness.py` if none exists (add that file to the
   change and say so).

If the installed program does not behave as listed, stop and report the exact output instead of
adjusting the expectation.

## Test plan

Slice 1 is test-first. Slice 2 runs outside any sandbox. The real-data proof is recorded by the
orchestrator in `04-verify.md`.

## Look-ahead, determinism and import impact

No read path changes. Snapshot identity is shown to be independent of option order. One new
import inside `alpha_cli`.
