# Reopen frozen asset-master source evidence at retained-data consumers

**Delivery state:** Completed

```json
{
  "schema_version": 1,
  "title": "Reopen frozen asset-master source evidence at retained-data consumers",
  "context": "W05/T10 requires retained source integrity at reuse. The local readiness checklist at lines 249-253 and 1222 requires provider-to-snapshot reopen and rejection of missing/tampered sources; ADR-0032 binds asset masters to exact qualified source manifests. The supplied canonical v9 W05/W02 scope is controlling; its separately materialized full document was unavailable locally.",
  "assumptions": [
    {"statement": "Schema-1 asset masters freeze mappings and explicit ordered catalog source IDs, but have no historic builder-version binding.", "verified_by": "Existing AssetMaster serialization and create path; verify retained evidence without rebuilding frozen identities using today's builder"},
    {"statement": "A missing committed source can disappear from inventory without invalidating the master content hash.", "verified_by": "Two red public CLI tests accepted a deleted explicit source manifest before this correction"}
  ],
  "alternatives_considered": ["Rebuild identities with the current builder: rejected because historical builder semantics are not version-bound.", "Only verify inventory: rejected because deleted explicitly referenced manifests are absent from inventory.", "Introduce a new provenance registry/schema: unnecessary; use existing source IDs, storage verification and admission lock."],
  "pre_mortem": ["Verifying only normalized bytes misses lost raw lineage.", "A valid master under another version filename is accepted.", "A future catalog append implicitly rebinds frozen mappings.", "Checking hashes then reopening an unbounded path decodes different bytes."],
  "slices": [
    {"title": "Reopen committed catalogs at consumers", "verify": "Owned public catalog/master/contract/snapshot integration tests plus existing asset-master/profile tests", "expected": "Active qualified supported catalog roles and exact retained normalized/raw bytes required; explicit unavailable errors prevent new snapshot publication", "rollback": "Restore preserved fdfba819 source; no artifacts or schemas are migrated", "status": "done"},
    {"title": "Preserve frozen identity and legacy decoding", "verify": "Filename mismatch, legacy unbound, reviewed-native, future-canary, read-only and lock-composition cases; scoped types/lint/imports and independent source review", "expected": "No builder replay or implicit latest catalog; existing native identities and serialization preserved", "rollback": "Remove consumer guard and helper only; all prior artifact formats remain unchanged", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-08-asset-master-source-provenance.md"],
  "out_of_scope": ["PIT/publication, rights or admission authority", "Proving historical builder derivation", "Providers, live stores or acquisition", "Other owners' implementations, shared generated docs/assets", "Protected/full gates or publication"],
  "files": ["apps/alpha-cli/src/alpha_cli/_crypto_asset_master_sources.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/integration/test_asset_master_provenance.py"]
}
```

The existing CLI journey is retained catalog ingestion → frozen master creation → master
verification / exact contract lookup → snapshot creation → snapshot verification/query.
Custom-master uses reopen their explicitly committed catalog sources; missing, changed or
incompatible evidence refuses the operation. Existing historical master listing/storage
reading still decodes frozen records without asserting source eligibility. Builtin reviewed
native labels retain their separate existing route. A later catalog does not rebind a master.

Catalog decoding now uses the verified in-memory bytes from the existing normalized-reader
seam with its explicit 32 MiB ceiling, including the shared market-membership lookup. Larger
inputs refuse rather than decode. Master creation holds the existing admission lock across
source verification and publication. This coordinates participating retirement/publication;
it does not fence arbitrary external filesystem tampering or prove power-loss durability.

Source verification proves retained identity, supported source roles, qualified hash and raw
lineage integrity. It does not prove a historic builder produced these mappings, publication
availability, historical market completeness, rights or research approval. Synthetic temporary
capacity is a fixture only; production storage reserves are unchanged. No ControlStore or
provider action is needed by the tested read-only path.

README/manual/generated-output review: public CLI signatures and persisted/API schemas are
unchanged. Shared manual/build/Atlas edits are reserved for integration by task constraint;
this candidate-local behavior record is the proposed delivery documentation. No frontend or
OpenAPI regeneration is required by this internal retained-evidence guard. No full/private
release gate is claimed. Existing authorized Claude review is unavailable in this executor;
independent review uses the available Codex reviewer and is labelled accordingly.
