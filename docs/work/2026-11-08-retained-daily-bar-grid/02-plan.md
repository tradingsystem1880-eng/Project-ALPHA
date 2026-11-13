# Inspect retained native daily bars against an explicit grid

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical v9 W05 and the market-data amendment's page42 coverage/gap interface
require truthful retained coverage evidence. The existing quality command reverifies
bytes and displays an immutable stored report. The qualifier warns about adjacent
cadence gaps but cannot identify missing leading/trailing slots relative to a requested
range. A synthetic retained Jan2–3 artifact is mechanically qualified while a caller's
Jan1–5 exclusive grid has two missing slots. This slice exposes that difference.

Predecessor tree: 3c102e2b65b0e2dab88d4bfa65619d5a87e3f277; cumulative base:
3f7b23185c29b2542605bd41b9485016c2ef3e79. Preserve those candidates and exports.

```json
{
  "schema_version": 1,
  "title": "Inspect retained native daily bars against an explicit grid",
  "context": "Extend the existing quality CLI with opt-in bounded retained native Binance spot daily bar diagnostics, without changing admission, stored quality or acquisition.",
  "assumptions": [
    {"statement": "Expected grid is explicitly caller-declared; no provider, halt, calendar or publication policy is inferred.", "verified_by": "Mandatory start/exclusive end/as_of/native cadence arguments; fixed identity refusal and diagnostic authority flags"},
    {"statement": "Input byte/row bounds do not prove decoder RSS, elapsed time, source completeness or historical availability.", "verified_by": "Separate reported hashing/metadata/payload limits and explicit exclusions; no PIT eligibility or provider-completeness claim"}
  ],
  "alternatives_considered": ["Requalify artifacts: rejected; inspection must preserve stored evidence.", "Infer a global exchange calendar or funding cadence: rejected; no such policy is selected.", "Add another catalog/query service: rejected; reuse existing quality command and immutable store verifier."],
  "pre_mortem": ["Min/max hides leading/trailing gaps.", "Sorting or deduplication hides invalid source order or conflicting native rows.", "A limited decoded prefix is reported as a complete artifact audit.", "Byte integrity is confused with source availability or research admission."],
  "slices": [
    {"title": "Audit an explicit daily grid preserving source defects", "verify": "Pure synthetic grid, duplicates, invalid values/times and future poison with leaky control", "expected": "Exact missing counts and capped compact ranges; native fields compared without sort/dedup; declared-grid success distinct from provider completeness", "rollback": "Remove optional CLI mode then pure helper; never alter old persisted evidence", "status": "done"},
    {"title": "Compose bounded read-only audit through the quality CLI", "verify": "Synthetic retained artifacts, legacy output parity, corrupt/missing lineage and resource caps; scoped regressions/types/lint/imports and independent source review", "expected": "No fetch, DB initialization or writes; unavailable on failed verification or caps; immutable stored quality shown separately", "rollback": "Remove opt-in branch and optional verifier budgets; legacy schemas/default callers remain unchanged", "status": "done"}
  ],
  "tier_impact": ["determinism", "bias"],
  "docs_to_update": ["docs/work/2026-11-08-retained-daily-bar-grid/02-plan.md"],
  "out_of_scope": ["Provider calls and acquisition", "Rights/readiness/accounting activation", "Source publication or vintage eligibility", "Non-daily/other venue calendars", "Repair/fill/deduplication", "Snapshot admission", "ControlStore or other owners' paths", "Private/full gates, installations, transfers or publication"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/quality.py", "packages/alpha-data/src/alpha_data/crypto/storage.py", "apps/alpha-cli/src/alpha_cli/_crypto_bar_coverage.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_bar_coverage.py", "tests/integration/test_crypto_bar_coverage_cli.py"]
}
```

## Operator journey

Use an existing normalized manifest, with its retained raw parents:

```
alpha crypto-data quality MANIFEST_ID --coverage-start 2024-01-01T00:00:00Z --coverage-end 2024-01-05T00:00:00Z --as-of 2024-01-05T00:00:00Z --expected-cadence-seconds 86400 --max-verify-artifact-bytes 1000000 --json
```

Only Binance spot market_bars, native OHLCV, 1d, interval_start_utc is supported.
Cadence must match that native identity. Caller start anchors the grid; end is exclusive
and all requested periods must have closed by as_of. This cutoff is not a vintage query.
Retrieval later than as_of is disclosed; source publication/PIT eligibility remains false.
Rows outside the requested interval do not enter requested-grid integrity checks;
unplaceable timestamps block success. The audit checks original order, all eleven native
columns, duplicates/conflicts, OHLC/base-and-quote-volume/finite values, nonnegative integral
trade counts, close-time bounds and off-grid rows. Taker-volume fields are checked for
finite values and exact conflicts; this does not add unapproved relationships or source
semantics. Native timestamp units ms/us are supported; ns is refused before conversion
can truncate precision. Integer conflict comparison preserves exact large counts.
Missing slots are absent observations on the declared grid, not proof of missing trades,
provider errors or complete historical coverage. No fill, repair or reacquisition follows.

Exit0 means only that the verified retained artifact satisfies the explicit grid's checks.
Exit1 covers inspected findings or unavailable evidence. The receipt distinguishes those
states, gives capped missing ranges with exact totals, and preserves the stored quality
state/method/row count. No flags retains the existing quality output and behavior.
Any new audit flag requires the complete five-argument group; limits cannot silently fall
back to legacy inspection.

One shared artifact hashing budget and metadata budget flow through normalized/raw
verification and retirement checks. The final normalized payload read has its own bound
(max_input_bytes+1); it is not charged as another hash read. Defaults reuse existing32MiB
normalized/metadata conventions; decoded rows cap50000, missing ranges1000. These are new
inspection engineering ceilings, not provider quota or operational policy. Parquet returned
row count and encoded input bytes are bounded; decompression/decoder peak memory, physical
I/O and wall time are not. Count mismatch or overflow cannot become prefix success.
Raw lineage verification checks exact hash/size/identity, not raw reparsing or qualification.
Generation checks do not constitute a multi-file immutable filesystem transaction.

No persisted schemas, hashes, receipts, provider routes, scientific defaults or production
accounting are changed. Optional storage budget arguments defaultNone and preserve old
call dispatch. The pure checker reuses the existing mechanical qualifier without changing it.

## Delivery boundaries

Shared README/manual/build/Atlas updates are intentionally deferred to integration by the
parent's ownership constraint. This candidate-local document records the new opt-in CLI
journey and limitations; existing README's broad readiness statements gain no new authority.
No native README/review attestation or full release qualification is claimed. Scoped public
checks and independent review are recorded in the executor-local delivery receipts.

Claude was unavailable through existing tools/executable; no installation, authentication
or workaround was attempted. Independent review uses an available Codex reviewer and is
labelled accordingly. No protected source or private outcomes are read.
