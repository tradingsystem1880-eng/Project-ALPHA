# Bound status metadata before parsing

**Delivery state:** Completed — proven end to end by `tests/smoke/test_crypto_backfill_smoke.py` (2026-11-14, `m8/prove-crypto-backfill`); done when that pull request merges.

Requirement: canonical v9 W05/W02, market-data amendment delivery slice C and its
bounded status/recovery contract (pages 42–43; Library
libfile_181ac6079dcc8191b222b76c1f10bf17, version 9). This is a quality successor to
55a96a745b1b9efcae20aae13154c6734ae960bd, not a new provider or qualification claim.
Base remains 3f7b23185c29b2542605bd41b9485016c2ef3e79. Original candidates/exports
are preserved separately and unchanged.

## Demonstrated defect

The predecessor's manifest/retirement readers used unbounded read_text before JSON
validation, outside the status artifact counter. A temporary synthetic CLI reproduction
read a 2,098,455-byte manifest twice (4,196,910 bytes total), returned complete, and had
no metadata counter. No provider call or inspection mutation occurred. Its report disclosed
that exclusion, but arbitrarily large JSON bodies still posed a resource-exhaustion risk.
The separate reproduction receipt preserves these measured facts.

Retained configuration already has an 8,192-byte read ceiling, but a decoder RecursionError
could escape status's lazy loader catch. A content-addressed malformed artifact_kind list
also reached set membership and escaped as TypeError rather than a structured blocked result.
Both are independently exercised by synthetic CLI regression cases.

```json
{
  "schema_version": 1,
  "title": "Bound status metadata before parsing",
  "context": "Close the demonstrated unbounded manifest/retirement read path in backfill-status while preserving legacy verifier signatures/default behavior and all source/admission boundaries.",
  "assumptions": [
    {"statement": "Metadata byte accounting is inspection resource control, separate from artifact hashes, HTTP quotas and billing.", "verified_by": "Separate MetadataVerificationBudget with status-only construction; all storage keywords default None"},
    {"statement": "Stable descriptor/path generation checks detect the tested truncation/replacement, not global transactional immutability.", "verified_by": "Synthetic regular-file read/replace/short-read tests and existing ledger-hash recheck"}
  ],
  "alternatives_considered": ["Keep metadata excluded: rejected after actual oversized CLI reproduction.", "Change all production storage defaults: rejected; optional bound is supplied only by inspection.", "Add a separate manifest catalog or parser platform: rejected; extend existing verification/store seams."],
  "pre_mortem": ["Root verification is capped but recursive raw parents or retirement reads bypass it.", "Every window resets the metadata counter.", "A replaced/partial file parses as a healthy checkpoint.", "A new bytes decoder silently accepts encodings the existing UTF-8 reader rejects."],
  "slices": [
    {"title": "Read stable bounded metadata and preserve legacy dispatch", "verify": "New metadata unit tests plus existing storage/verifier regressions, types and lint", "expected": "Aggregate reservation before body open; exact-size reads; generation checks; UTF-8 and depth checks before decoding; abort/cleanup on failure", "rollback": "Remove optional metadata keyword users before helpers; retained schemas and evidence never change", "status": "done"},
    {"title": "Compose metadata bounds through actual status CLI", "verify": "Synthetic CLI oversized/malformed/truncated/replaced metadata and no-effect tests, independent exact-tree source review", "expected": "One shared counter through every normalized/raw/retirement verification; truthful blocked/deferred states and config decoder handling", "rollback": "Disable new optional status bound path before reverting; preserve existing artifacts and original candidates", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/work/2026-11-08-backfill-metadata-bounds/02-plan.md"],
  "out_of_scope": ["Provider/retained-store/credential operations", "ControlStore or inactive accounting activation", "New provider budgets/policy", "Wall-time/RSS guarantees", "Production migration or sender fencing", "Private/full gates", "Other owners/shared generated outputs", "Installations/transfers/publication"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/verification.py", "packages/alpha-data/src/alpha_data/crypto/storage.py", "apps/alpha-cli/src/alpha_cli/_crypto_backfill_evidence.py", "apps/alpha-cli/src/alpha_cli/_crypto_backfill_inspection.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_metadata_budget.py", "tests/integration/test_crypto_backfill_metadata_cli.py"]
}
```

## Behavior and compatibility

Status constructs one MetadataVerificationBudget across all normalized/raw manifests,
retirement receipts and repeated reads in completion verification. The optional CLI
--max-verify-metadata-bytes defaults to 32 MiB aggregate input, the same magnitude as
existing normalized-read convention. This is a NEW inspection engineering default,
not a pre-existing metadata policy, provider quota or spending allowance. Nesting is
limited to 64 containers before json.loads; braces/escaped quotes inside strings do not
count. The receipt reports both limits, reserved/read bytes and abort state. An aborted
metadata or artifact verification prevents later windows being silently marked verified.

Regular-file metadata is sized and reserved before body open. O_NOFOLLOW/O_NONBLOCK,
regular-descriptor checks, capped os.read requests, exact expected length and before/after
inode/size/mtime/ctime/path identity checks reject observed replacement, truncation, growth,
short reads, symlinks and FIFOs. The descriptor closes on failure/cancellation. Reservations
are retained on failure; there is no refund or persisted ledger. Reads count repeatedly.
UTF-8 decoding matches the old text-reader contract: UTF-16/32 and UTF-8 BOM are not silently
admitted by json.loads(bytes). No raw exception/body text enters the inspection receipt.

Metadata keywords on existing store/completion APIs default None. Old callers retain
original dispatch and limits, including no new keyword sent to legacy helpers when absent.
No persisted manifest/receipt/frame schema changes. The artifact_kind guard converts
malformed non-string kinds to typed DataError; it admits no formerly invalid data.
Configuration keeps its existing 8,192-byte cap; status sanitizes a lazy decoder
RecursionError as STORAGE_UNAVAILABLE. No config/admission implementation is changed.

The byte counter covers manifest and retirement input bodies only. Root configuration is
separately bounded; identity/capacity queries, filesystem read-ahead, decoded-object overhead,
canonical serialization, total process RSS and wall time are outside it. O_NONBLOCK is not
a deadline for regular-file I/O. An immutable generation across multiple separate files or
across the entire query is not proved; existing source-hash recheck remains observational.
A test-injected concurrent metadata replacement is attributed to the fixture writer;
inspection itself leaves the ledger, artifacts and remaining retained files unchanged.

Metadata status remains unavailable/unverifiable/deferred, never healthy by exhaustion.
Quality, coverage, freshness, source availability, rights, historical quota and execution
permission remain separate. The recovery preview still forces existing --dry-run. No
accounting, provider route, initialization, repair, admission or new service is activated.

## Evidence and review

Official Python 3.12 JSON documentation recommends limiting untrusted input size because
of CPU/memory consumption: https://docs.python.org/3.12/library/json.html . os.read promises
at most the requested byte count: https://docs.python.org/3.12/library/os.html#os.read .
Those support input-byte bounds, not a total RSS or wall-time guarantee. Source-only
navigator review identified the complete call chain and legacy dispatch requirements.

No existing Claude tool/session or executable was available in this executor. No install,
authentication, security change or workaround was attempted. Independent review uses an
available Codex subagent and is recorded as such, not Claude or native approval. Exact-tree
public focused checks/review receipts are separate from provider or scientific qualification.
Shared README/manual/build/Atlas changes remain deferred under owner coordination; this
candidate-local plan records the new status flag/default and its explicit claim ceiling.
QuantPad stays excluded. No transfer or publication in this slice.

Independent Codex review identified one artifact-budget-only recursion branch that
forwarded metadata_budget=None to legacy overrides. The old call shape is restored
when metadata budgeting is absent. An exact legacy-signature override regression
failed before the correction and passed afterward; original finding and final review
are retained separately. No other required findings were identified.
