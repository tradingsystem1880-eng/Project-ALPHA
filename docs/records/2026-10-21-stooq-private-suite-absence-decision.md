# Stooq candidate: one-time absent-private-suite decision — 2026-10-21

This records a new owner decision for the Stooq interrupted-download fix and
navigation correction only. The earlier formal BLOCK was correct under the
instructions then in force; it remains historical evidence, not retroactive approval.

## Exact candidate and permitted metadata

Base: `b2556c0ede016f99dba687187b6e9f501bedd5cb`.
Original nine-file staged Git tree: `5419cdf8130508351f5e59ba09e1141dc4c4412e`.
Original full-index binary patch SHA256:
`ed0077a7c80aa69c8fdcea48db3f2bb83032f5ded74ea10d3f2b04460a5281ef`.

Preserve these nine files byte-for-byte from that tree:

| Path | SHA256 |
| --- | --- |
| `CLAUDE.md` | `c815c44a7bf8647bb840b635be3b8a6edb58d3299b1be96573b68cbcbc41849a` |
| `architecture/atlas/generated/graph.json` | `acea0cfb16eaa1efff937566f06f4d3623cd531170ac393ac13693af5f9f98b6` |
| `architecture/atlas/generated/inputs.json` | `0c29c7d54e4a80341e55a42ac4744dce92bb8f50494ce77419828c9703768c2e` |
| `architecture/atlas/generated/views/unknowns.json` | `12d24c7349c3419755fd01e9cfaa6a1aa22b8969ad6b88ac2d10d2f7be3f7e58` |
| `docs/BUILD-STATUS.md` | `6cf107de76b4d4b7735fb8885197f308782535c3d7fbdb8e2b95629ef2b89e22` |
| `docs/operations/owner-actions-checklist.md` | `f34e3990ddc1f97ee6ebf3f40e4f63d47013af6ea303f124f195add46ba086bc` |
| `packages/alpha-data/src/alpha_data/adapters/stooq_adapter.py` | `b37cdd52d198198cadcb4a61356d2c370e692ff544822ddf634dac8ea15870a2` |
| `tests/integration/test_data_cli.py` | `7a1a312337c9c8149b3d5fe20cdea4f6048d79c6f79fb73e54ec955de67bd5e8` |
| `tests/unit/test_stooq_adapter.py` | `cba1aefd4207606c096bf4559599c538626e6ec8d444a142143719d155e03d5d` |

The only additions authorized with those bytes are this decision record and the
corresponding appended Stooq exception in `.claude/agents/independent-reviewer.md`.
The final eleven-file staged tree and review bindings must be recorded in external
receipts after staging; this record cannot certify its own final hash. Any later
substantive change is outside this exception and needs its own governing review.
The separately named snapshot/rollback candidate is not included here.

## Owner authorization and accepted limitation

The parent supplied this consent exchange as explicit authorization:

Assistant `Sentinel_eaa60e271b848191941860ad47ae6277`:

> My recommendation is a one-time exception for these two fixes only:
> 1. Stooq interrupted-download errors and the navigation correction.
> 2. Snapshot consistency and safe retry after rollback.
>
> Do you approve updating Project-ALPHA’s review instructions and decision record so the missing private suite alone doesn’t block these two candidates? They must still pass fresh independent review and every other required check. Private coverage will remain explicitly unverified; no tests, thresholds, guards or CI checks will be weakened.
>
> The risk is that missing hidden tests could catch something the available tests missed. This would not authorize merging or apply to future changes.

Owner `Sentinel_ff8f92922cf881918a1aa8afbb47aef5`:

> yes i approve

This record implements only the first named candidate. Missing hidden tests may
catch defects missed by available tests; private coverage remains **UNVERIFIED**.

## Completion requirements and exclusions

- Only documented absence of the original private `tests/holdout/` suite becomes
  informational and nonblocking for this exact candidate. Establish absence using
  permitted path metadata, without reading private contents. Do not execute a
  known-absent or denied private command merely to manufacture an execution receipt.
- If the genuine suite is available and execution is permitted, run it normally.
  Actual failures, collection errors (including nonempty-suite collection errors),
  other unavailable required checks and every other blocking finding still BLOCK.
- A fresh independent reviewer must review both the software/navigation changes
  and these control-plane additions against the exact consent, independently run
  available covering tests, and provide a genuine verdict bound to the final staged
  tree and scoped diff. The author cannot self-approve or relabel the old BLOCK.
- Run every other available required gate unchanged on the frozen candidate,
  preserve failures before retries, and use the normal attestation path only after
  a genuine new APPROVE. A full-tier code stamp alone is not formal review approval.
- No seed promotion, fabricated tests, private-source access/edit/copy/transfer,
  gate/test/threshold/exclusion/timeout/CI/security/runtime change, override, or
  standing exception is granted. Existing application and owner authority remain.
- Preserve the original candidate, full manifest, prior BLOCK and recovery archive.
  Commit, push and publication remain held for parent review of the expanded final
  manifest. This decision grants no merge authority or later-change exemption.
