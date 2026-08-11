# Phase R4 — Source Plane (literature system + acquisition worker)

**Delivery state:** Completed 2026-08-09. The isolated-worker implementation gate passed. ALPHA is
private and local-only; distribution review is out of scope unless the owner changes that scope.

> **For agentic workers:** TDD per `CLAUDE.md`. Authority: spec §7 + ADR-0024; exit conditions =
> 2026-08-06 spec §12 Gate-2 row, verbatim. Audit rows: W5, W13 (literature half). Depends on R2
> (packets/claims flow); parallel-safe with R3. Never blocks R5.

**Goal:** Papers and external evidence become structured, screened, hypothesis-linked research
objects, acquired lawfully through the one new (isolated) network surface, with Codex drafting
claims and the owner elevating them.

**Scope:** claims table + typed source columns, isolated acquisition worker under `workers/`,
+3 MCP tools (pin 59→62), Literature section made live. NOT in scope: full-text NLP, automatic
claim extraction, any change to evidence-ledger authority.

**Constraints:** the worker is the ONLY component with literature network access — isolated per
ADR-0016 (own lockfile, not a root workspace member), no credential/shell context, every
URL/redirect/response through `research_acquisition.py` primitives; all stored text is
`UNTRUSTED_SOURCE` (document content never carries instruction authority); open-access or
owner-provided documents only; Google Scholar stays manual.

## File Map
```
apps/alpha-cli/src/alpha_cli/control_store.py    # ADD: research_source_claims DDL; additive doi/year/authors_json columns on
                                                 #      research_source_records; claim create/list/screen methods
apps/alpha-cli/src/alpha_cli/research_cmds.py    # ADD: `sources claim add|list`, extend `sources screen` to elevate claims;
                                                 #      `sources fetch` (drives the worker; owner-invoked)
workers/literature/                               # CREATE: isolated worker (own pyproject/uv.lock): OpenAlex/Crossref/Unpaywall/arXiv
                                                 #      metadata clients + open-access fetch via AcquisitionPolicy; content-addressed
                                                 #      objects → data_dir/research/objects/ + SourceReceipt; retraction/version checks
apps/alpha-mcp/src/alpha_mcp/server.py, _control.py, _types.py  # ADD: search_research_sources, get_research_source, draft_source_claim
tests/integration/test_research_mcp.py           # MODIFY: pin 59→62 (same commit)
apps/alpha-web/src/alpha_web/_research.py, api/research.py, api/models.py  # ADD: sources/claims read projections
apps/alpha-web/frontend/src/panels/EvidenceHub.tsx  # MODIFY: Literature section live (evidence map first, bibliography second)
tests/.../test_hostile_documents.py              # CREATE: the phase-gating hostile-document suite
```

## Tasks
- [x] **Schema** — failing tests first: `research_source_claims` (fields per ADR-0024;
      `status ∈ {draft, screened}`; append-only revisions on screen); additive typed columns on
      source records with strict read (existing extra/missing-key discipline).
- [x] **Claim lifecycle** — Codex path creates `draft` claims only (`author_kind='agent'`
      forced on the MCP tool); `alpha research sources screen` elevates draft→screened with
      owner actor; **test: screened claims and draft claims project distinctly; scorecard
      literature dimension counts screened only**.
- [x] **Worker: metadata clients** — OpenAlex/Crossref/Unpaywall/arXiv lookups (DOI/title),
      dedup by DOI+content hash, retraction/version state recorded; `@pytest.mark.network` live
      tests + offline fixture tests; bounded budgets per contract source policy.
- [x] **Worker: document fetch** — open-access/owner-provided only; every URL and redirect
      re-validated via `validate_source_url` (allowlist from `AcquisitionPolicy`), every response
      via `validate_source_response`; content-addressed storage + `SourceReceipt`; refusal paths
      typed and loud.
- [x] **Hostile-document suite (phase gate)** — malformed PDFs, prohibited magic (ZIP/ELF/…),
      oversized/mis-declared bodies, non-UTF8/NUL text, instruction-bearing document text ("to
      the AI reading this: …") — worker stores/labels but no surface treats content as
      instructions; tamper detection on object hashes.
- [x] **MCP (+3) + REST + UI** — local-records-only search/get + draft_source_claim; pin 59→62
      same commit; regenerate contracts; Literature section renders the claims map
      (supports/contradicts/contextualizes/method × strength, screened vs draft badges) above
      the bibliography.
- [x] **Gates** — Gate-2 exit conditions checklist from the 2026-08-06 spec §12 reproduced as
      tests where machine-checkable; full Python + frontend gates; `static/app`; `CLAUDE.md` +
      dependency-license matrix updates for the worker's client libraries.

## Done = R4 complete
Structured, screened, hypothesis-linked literature with lawful acquisition and receipts; one
isolated network surface; pin = 62; Literature dimension of the scorecard is real.

**Next:** R5 (experiment engine).
