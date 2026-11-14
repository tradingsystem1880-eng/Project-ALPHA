# Refuse ambiguous retained captures at frozen snapshot verification

**Delivery state:** Superseded by ../2026-11-14-crypto-snapshot-duplicates/02-plan.md — ADR-0046 replaced its refuse-every-repeat rule (equal captures count as one, divergent ones refuse); its tamper refusals are proven end to end by `tests/smoke/test_crypto_snapshots_smoke.py` (2026-11-14).

**Historical delivery state (as first recorded):** Completed

```json
{
  "schema_version": 1,
  "title": "Refuse ambiguous retained captures at frozen snapshot verification",
  "context": "W05/T10 retained-data reuse must reject stale, missing, tampered or incompatible sources without guessed fallback (local canonical readiness checklist lines 249-253 and 1222). Existing snapshot-query requires one exact key/hash/dataset manifest; snapshot verification instead silently overwrote multiple captures by key/hash. Supplied canonical v9 W05/W02 remains controlling; its separately materialized complete document was unavailable locally.",
  "assumptions": [
    {"statement": "Schema-1 snapshot membership does not bind a source manifest ID.", "verified_by": "CryptoSnapshotMemberV1 and existing query explicit-manifest ambiguity refusal"},
    {"statement": "Distinct raw captures can yield identical normalized bytes with different immutable manifests and qualification evidence.", "verified_by": "Existing publish_normalized manifest identity includes input IDs, quality and optional acquisition scope; actual synthetic CLI red case succeeded despite duplicate retained captures"}
  ],
  "alternatives_considered": ["Choose latest, lexicographically last or qualified capture: rejected; no frozen authority to select one.", "Add manifest IDs to old snapshot schema: rejected; preserve hashes/readers and do not reinterpret legacy artifacts.", "Refuse all key/hash collisions including different datasets: rejected; existing query matches full dataset identity."],
  "pre_mortem": ["Only qualified candidates are counted, concealing contradictory evidence.", "Inventory ordering changes eligibility.", "Unrelated dataset metadata overwrites the exact match.", "Ambiguity is described as invalid bytes or authority instead of unavailable evidence."],
  "slices": [
    {"title": "Preserve all retained candidates and require exact unique binding", "verify": "Actual CLI producer/snapshot/verification red-green sequence and recapture variants", "expected": "Unique exact source verifies; multiple exact sources refuse before scope or quality evaluation regardless of order/state", "rollback": "Restore immutable9ec842e1 source; no stored artifact is changed", "status": "done"},
    {"title": "Verify source failure and compatibility boundaries", "verify": "Missing/raw/normalized tampering, snapshot alias, disjoint dataset cases; scoped regression/types/lint/imports and independent review", "expected": "Read-only failure or unchanged unique eligibility; frozen schemas/defaults preserved", "rollback": "Remove only new source selection guard/tests/doc; no data migration", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/work/2026-11-08-snapshot-capture-binding/02-plan.md"],
  "out_of_scope": ["New snapshot schema or manifest selection API", "PIT, historical completeness, rights or admission authority", "Providers/live stores/studies", "Other owners' source/shared generated docs", "Full/private gates, installations, transfers or publication"],
  "files": ["apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/integration/test_asset_master_provenance.py"]
}
```

The actual production CLI journey is synthetic retained ingestion → snapshot-create →
snapshot-verify. A unique capture remains eligible under existing mechanical checks. Adding
a distinct retained raw capture with identical normalized bytes now yields an explicit
ambiguous-member error. Existing native compatibility, registration and observation callers
that compose this verifier inherit the guard before downstream use. No study is executed.

The verifier matches artifact path, hash and full dataset identity before evaluating scope
or qualification. It does not select by timestamp, filename order, qualification state or
scope. Missing matches retain their existing missing/mismatched failure. Multiple exact
matches remain unavailable even when both are qualified or one is quarantined. Integrity
verification still occurs via the existing inventory path; this change does not make reads
atomic against arbitrary external tampering or eliminate unrelated inventory failures.

Schema-1 cannot recover the originally intended capture. Automatic verification of an
ambiguous historical snapshot therefore refuses; its immutable bytes remain decodable. A
future explicit-selection or schema-version design is separate and is not inferred here.
Creating another snapshot with the same membership does not resolve ambiguity. Inspection
must not delete evidence merely to make this verifier pass.

Tests create and alter only disposable fixtures. Correctly content-addressed incompatible
metadata is a negative fixture, not a claim it is admitted provider evidence. Read-only
checks compare retained content fingerprints and guard provider/ControlStore entry points;
they do not establish host-global immutability, release qualification or source authority.

README/manual/generated-output review: CLI signatures, persisted formats, API schemas and
frontend assets are unchanged. The new explicit failure replaces guessed retained capture
selection. Shared README/manual/build/Atlas changes remain integration-owned under task
constraints; this candidate-local plan is the proposed behavior documentation. No generated
delta is required. Full/private gates and live qualification remain NOT RUN. Independent
review uses available Codex; no existing authorized Claude route is available here.
