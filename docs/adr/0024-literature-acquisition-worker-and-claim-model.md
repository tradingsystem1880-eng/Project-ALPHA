# ADR-0024: Lawful literature acquisition worker and the claim-level evidence model

**Status:** Accepted (implemented 2026-08-09/10; accepted 2026-08-10)
**Date:** 2026-08-07
**Deciders:** Project ALPHA owner and AI build agents

## Context

The research-first redesign requires papers and external evidence to be structured research
objects linked to hypotheses, not links pasted into notes. Gate 2 of the Research Scientist
program specified this source plane; today only its fail-closed validation primitives exist
(`research_acquisition.py` deliberately performs no network I/O), source records/packs are
metadata-only CLI records, and there is no claim-level structure. External documents are
untrusted input: hostile PDFs and prompt-injection bodies are the expected threat model, and the
contract's source policy already labels all external text `UNTRUSTED_SOURCE`.

## Decision

- **Claim-level evidence.** Add append-only `research_source_claims` linking a source to the
  hypothesis version it bears on: `claim_text`, `direction ∈ {supports, contradicts,
  contextualizes, method}`, `strength ∈ {weak, moderate, strong}`, `method_summary`,
  `sample_summary`, `markets_json`, `limitations`, `status ∈ {draft, screened}`, author +
  `author_kind`. Codex drafts claims; **only owner screening elevates draft → screened**; a
  published paper is never auto-trusted. Add typed `doi`, `year`, `authors_json` columns to
  `research_source_records` by additive migration; other descriptors stay in `metadata_json`.
- **Acquisition worker.** Build the Gate-2 network worker as an isolated component under
  `workers/` (ADR-0016 isolation pattern: own lockfile, not a root workspace member, no
  credential or shell context). It uses approved metadata services (OpenAlex, Crossref,
  Unpaywall, arXiv; Google Scholar stays manual-browser-only) and fetches open-access or
  owner-provided documents only, driving every URL, redirect, and response through the existing
  `AcquisitionPolicy` / `validate_source_url` / `validate_source_response` primitives (HTTPS,
  IDNA host allowlist, global addresses only, MIME/size/magic checks). Every stored object is
  content-addressed under `data_dir/research/objects/` with a `SourceReceipt`
  (`trust_label="UNTRUSTED_SOURCE"`); document text never carries instruction authority.
  Retraction/version state is recorded on the source record.
- **MCP.** Add `search_research_sources` (local records only), `get_research_source`, and
  `draft_source_claim` — read and draft-write; screening and pack freezing stay owner CLI.
- **Phase gate.** The hostile-document suite (malformed PDFs, archive bombs, oversized bodies,
  instruction-bearing text) plus the 2026-08-06 spec §12 Gate-2 exit conditions (dedup,
  DOI/version/retraction, access policy, tamper detection) gate the phase.

## Implementation anchors

- Spec: `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md` §7
- Phase plan: `docs/superpowers/plans/2026-08-07-research-first-R4-source-plane.md`
- Existing primitives: `apps/alpha-cli/src/alpha_cli/research_acquisition.py`
- Existing records: `research_source_records` / `research_source_packs` in
  `apps/alpha-cli/src/alpha_cli/control_store.py`
- Isolation precedent: ADR-0016; dependency gating:
  `docs/governance/2026-07-19-dependency-license-matrix.md`

## Consequences

- "What existing evidence exists for or against this idea?" becomes answerable from structured,
  screened, hypothesis-linked claims with method and limitations stated.
- The application gains exactly one new network surface, isolated and fail-closed, whose blast
  radius is bounded by construction.
- Literature work becomes part of the recorded research lineage and the scorecard's literature
  dimension instead of living in owner notes.
