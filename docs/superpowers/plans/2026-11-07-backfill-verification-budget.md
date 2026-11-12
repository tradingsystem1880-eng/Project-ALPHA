# Bound explicit resume artifact verification

Delivery state: isolated successor to approved resume tree
`a20c88091c9951ea98b5202e6b1dfc999e8a79d0`. Focused verification/review receipts are separate.
No release, runtime/provider admission or durable quota qualification is claimed.

```json
{
  "schema_version": 1,
  "title": "Bound explicit resume artifact verification",
  "context": "W05/W02 independent fallback: explicit local artifact-read caps, without inventing durable acquisition quota policy. Predecessor content 9214111f89ba9f6fb79d5c66ff3b2b77e6ff99ad33774bac6044a529a8f8c5c2 remains preserved.",
  "assumptions": [
    {"statement": "RequestBudget is invocation-local HTTP accounting; a v1 window ledger is not durable quota authority.", "verified_by": "Existing _wire.py, _crypto_backfill.py and inactive F5 evidence"},
    {"statement": "A caller-supplied local read cap fits existing bounded normalized-read semantics without changing their existing meaning.", "verified_by": "CryptoBulkStore.read_verified_normalized(max_bytes); the new cap is explicit and opt-in"}
  ],
  "alternatives_considered": ["Persist HTTP allowance in the window ledger: rejected without adopted campaign/quota/reset semantics.", "Use W09 or pending ControlStore accounting: rejected; wrong authority and excluded owner.", "Silently cap all old verification calls: rejected; compatibility and no approved default."],
  "pre_mortem": ["Each raw hash resets its cap.", "A buffered read or EOF probe exceeds the cap.", "A failed read refunds allowance.", "A local read counter is mislabeled durable provider quota."],
  "slices": [
    {"title": "Reserve and bound artifact hashing", "verify": "Public synthetic verification-budget unit cases", "expected": "Atomic per-object reservations, exact-fit bounded reads, mutation/error/cancel rejection", "rollback": "Remove optional budget; leave immutable artifacts and old readers intact", "status": "done"},
    {"title": "Share one budget through actual resume CLI", "verify": "Public synthetic CLI cap/exhaustion/dry-run cases and scoped review/lint/types", "expected": "Count recursive and repeated reads; stop before new effects on exhaustion", "rollback": "Disable opt-in creation before reverting; persisted receipt/ledger schemas unchanged", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-07-backfill-verification-budget.md"],
  "out_of_scope": ["Durable quota accounting", "Cross-process acquisition ownership", "New default spending limits", "Provider calls", "Owner data", "Installations", "Protected/broad gates", "Shared docs/Atlas", "Publication"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/verification.py", "packages/alpha-data/src/alpha_data/crypto/storage.py", "apps/alpha-cli/src/alpha_cli/_crypto_backfill_evidence.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_verification_budget.py", "tests/integration/test_crypto_verification_budget_cli.py"]
}
```

`crypto-data backfill --max-verify-artifact-bytes N` creates one local hashing budget.
The existing recursive manifest verifier and the resume receipt checks share it. Every artifact
hash counts, including repeated raw reads. Complete declared sizes reserve before artifact open;
unbuffered reads consume only that reservation. Exact fit needs no extra EOF probe. Descriptor
type/size/identity and hash must agree; failure/cancellation aborts reuse without refund. Concurrent
threads sharing that same object cannot over-reserve; this is not process/host fencing.

The additive summary fields are `verification_artifact_byte_limit`,
`verification_artifact_bytes_reserved` and `verification_artifact_bytes_read`. Without the option
they are null, not falsely zero. Dry-run with a cap reports zero reads/reservations and performs
no storage probes or progress writes. Old uncapped callers and `read_verified_normalized(max_bytes)`
retain their semantics. Ledger/artifact schemas and snapshot admission are unchanged.

The cap covers application-returned artifact bytes during hashing. Manifest/retirement/progress
JSON, kernel read-ahead, physical I/O, wall time and new acquisition/HTTP traffic are excluded.
No persistent quota usage, billing, provider period or restart/reset authority follows.

Durable acquisition implementation remains blocked on the owning contract: stable campaign/cap
identity and migration; whether usage is per-ledger, provider/account/shared IP and period; retry
and rollover scope; durable-before-send ordering and fenced ownership; and affirmative recovery
evidence before any release. The current ledger path can change and does not bind a quota owner.
The inactive F5 fragment does not designate a real store/host/scope. Required ControlStore ownership
is concurrently excluded. Unknown historical consumption cannot be initialized as zero.

Proposed later README/manual/build documentation is recorded here; shared files and Atlas are
deliberately untouched. This successor requires separate exact-tree review and final delivery gates;
the predecessor's 108-test receipt and approval do not qualify it.
