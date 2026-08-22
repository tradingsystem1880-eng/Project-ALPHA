# ADR-0035: Govern generic study composition as a projection layer

**Status:** Accepted
**Date:** 2026-08-21
**Deciders:** Project ALPHA owner and AI build agents

## Context

The attached `/Users/hunternovotny/Desktop/deep-research-report.md` proposes a broad
generic research framework and a portfolio of external quantitative libraries. Its
useful architectural principle is that Project ALPHA remains the authority and that
external capabilities are adapters or isolated workers. Its proposed autonomous MCP
D1 writes, additional ledgers, and new schemas cannot be adopted independently of the
existing research program.

Project ALPHA already has authoritative `alpha_research` primitives, `alpha_cli`
orchestration, immutable research contracts and artifacts, D0/D1/D2 boundaries,
attempt and decision histories, Touch ID owner actions, promotion dossiers, and a
deliberately pinned 62-tool MCP surface. A second research control plane would create
competing sources of truth and could weaken the existing fail-closed boundaries.

The repository is permanently private and local-only. That scope does not remove
third-party licence, provider terms, entitlement, or data-retention obligations.

## Decision

Create `alpha-study` only as a research-plane composition and projection package.
It may compose approved, read-oriented seams from `alpha_core`, `alpha_data`,
`alpha_patterns`, and `alpha_research`. It owns no research authority, persistence,
approval, D1/D2 transition, promotion, paper, broker, or order capability.

The package boundary is:

```text
alpha-study → approved core/data/patterns/research projections
alpha-cli   → may compose alpha-study and existing research authority
alpha-mcp   → existing public CLI/platform seams only; no direct alpha-study authority
alpha-web   → existing public CLI/platform projections only; no analytical authority
```

`alpha-patterns` remains core-only pure geometry. A third-party indicator adapter must
not be placed in `alpha_patterns` unless a separate DAG decision explicitly changes
that rule; the default location is an optional adapter boundary owned by the study
composition layer.

The proposed contracts map to existing authority as follows:

| Proposed contract | Existing authority | Rule |
|---|---|---|
| `EventTableV1` | Existing point-in-time research observations, artifacts, dataset snapshots, and operator outputs | Projection only; availability, venue, unit, vintage, and lineage semantics must be explicit before implementation. |
| `ExplorationMandateV1` | Existing owner-approved research contract, frozen `ResearchAnalysisPlanV1`, D1 topology, launch reservation, attempt, and phase histories | Derived refinement only; no second approval or budget ledger and owner-only D1 remains unchanged. |
| `OperatorRegistrationV1` | Git-owned operator implementation plus the existing contract fingerprint and code/dependency/environment identity | Closed source registry keyed to exact code hash; mutable detector definitions do not enter SQLite. |
| `DetectorValidationV1` | Existing D0 attempt/run, raw fixture measurements, and mechanical admission/reverification | Versioned D0 artifact referenced by the registration; it cannot accept producer-supplied pass flags or imply empirical truth. |
| `StudyWorkspaceManifestV1` | Existing control-store, run-manifest, chart, dataset, and promotion references | Generated non-authoritative projection; no raw-data copy or independent state. |
| `FindingV1` | Existing typed research evidence, Gate Packet, attempt ledger, and decision view | Findings remain stage- and evidence-bound; they cannot imply promotion or paper readiness. |
| `MechanismGraphV1` | Existing hypothesis, confounder, falsification, stability, screened-claim, context-packet, and note records | Generated explanatory projection; advisor statements remain non-authoritative proposals and graph bytes are never read back as authority. |

No proposed contract is implementation-ready until its exact serialization, canonical
hash, immutable source, revision binding, availability/vintage semantics, error behavior,
and read/write authority are documented. Domain-specific macro and cross-sectional
projections must not be forced into an under-specified universal event row.

## S5b semantic owner-event freeze

S5b adds one append-only `research_semantic_events` ledger to schema v5. It does not add a
mutable frozen flag, second attempt/approval ledger, or a semantic write to `alpha-study`.
The only new closed owner action is `record_semantic_event`, used for the exact sequence
`definition -> review -> freeze`. Each event requires its own fresh Touch ID assertion and is
committed atomically with exactly one owner-action receipt.

The migration is logically additive: every v4 row is preserved and only semantic-event
capability is added. SQLite cannot alter the existing closed
`owner_action_receipts.action_type` `CHECK` in place, so the v4-to-v5 transaction performs one
explicit physical table rebuild solely to add `record_semantic_event` to that check. The rebuild
must preserve the existing columns, constraints, rows, index, and append-only triggers exactly;
row count and canonical row content are compared before the old table is dropped. The receipt-row
digest is SHA-256 over canonical JSON of rows ordered by `receipt_id`, with each row represented as
an array in this exact column order: `receipt_id`, `challenge_id`, `credential_id`, `actor`,
`action_type`, `project_id`, `artifact_hash`, `expected_case_revision`, `consequence_summary`,
`reason`, `request_hash`, `assertion_hash`, `outcome_json`, `performed_at`. Count and digest must
match after copying and before dropping the old table. No second receipt table or authority is
permitted.

The new strict table is exactly:

```sql
CREATE TABLE research_semantic_events (
    event_id TEXT PRIMARY KEY,
    event_sha256 TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL CHECK (sequence >= 1),
    event_type TEXT NOT NULL CHECK (event_type IN ('definition', 'review', 'freeze')),
    case_contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    source_contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    case_revision TEXT NOT NULL,
    prior_semantic_head_sha256 TEXT NOT NULL,
    semantic_artifact_id TEXT NOT NULL,
    semantic_artifact_sha256 TEXT NOT NULL,
    verified_read_sha256 TEXT NOT NULL,
    projection_sha256 TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cutoff_confirmed_at TEXT NOT NULL,
    definition_id TEXT NOT NULL,
    review_id TEXT,
    review_decision TEXT CHECK (review_decision IN ('approve', 'reject')),
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    receipt_id TEXT NOT NULL UNIQUE REFERENCES owner_action_receipts(receipt_id),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (project_id, sequence),
    UNIQUE (project_id, semantic_artifact_id),
    FOREIGN KEY (project_id, case_contract_id)
        REFERENCES research_contracts(project_id, contract_id),
    FOREIGN KEY (project_id, source_contract_id)
        REFERENCES research_contracts(project_id, contract_id),
    FOREIGN KEY (project_id, definition_id)
        REFERENCES research_semantic_events(project_id, semantic_artifact_id),
    FOREIGN KEY (project_id, review_id)
        REFERENCES research_semantic_events(project_id, semantic_artifact_id),
    CHECK (event_id = 'se_' || event_sha256),
    CHECK (length(event_sha256) = 64),
    CHECK (length(case_revision) = 64),
    CHECK (length(prior_semantic_head_sha256) = 64),
    CHECK (length(semantic_artifact_sha256) = 64),
    CHECK (length(verified_read_sha256) = 64),
    CHECK (length(projection_sha256) = 64),
    CHECK (length(payload_sha256) = 64),
    CHECK (length(run_id) = 16),
    CHECK (
        (event_type = 'definition'
            AND substr(semantic_artifact_id, 1, 3) = 'sd_'
            AND definition_id = semantic_artifact_id
            AND review_id IS NULL AND review_decision IS NULL)
        OR
        (event_type = 'review'
            AND substr(semantic_artifact_id, 1, 3) = 'sr_'
            AND substr(definition_id, 1, 3) = 'sd_'
            AND review_id = semantic_artifact_id
            AND review_decision IS NOT NULL)
        OR
        (event_type = 'freeze'
            AND substr(semantic_artifact_id, 1, 3) = 'sf_'
            AND substr(definition_id, 1, 3) = 'sd_'
            AND substr(review_id, 1, 3) = 'sr_'
            AND review_decision IS NULL)
    ),
    CHECK (semantic_artifact_sha256 = substr(semantic_artifact_id, 4))
) STRICT;

CREATE INDEX idx_research_semantic_events_contract
    ON research_semantic_events(project_id, case_contract_id, sequence);
CREATE INDEX idx_research_semantic_events_source
    ON research_semantic_events(project_id, source_contract_id, sequence);
CREATE INDEX idx_research_semantic_events_artifact
    ON research_semantic_events(project_id, verified_read_sha256, sequence);
CREATE UNIQUE INDEX idx_research_semantic_events_one_review
    ON research_semantic_events(project_id, definition_id)
    WHERE event_type = 'review';
CREATE UNIQUE INDEX idx_research_semantic_events_one_freeze
    ON research_semantic_events(project_id, definition_id)
    WHERE event_type = 'freeze';
```

`research_semantic_events_no_update` and `research_semantic_events_no_delete` abort every
update or delete. Insert code and persisted-read verification require a contiguous project-local
sequence beginning at one. The `definition` event is allowed at genesis, after a rejected review,
or after a freeze; `review` must immediately follow and reference the latest unfrozen definition;
`freeze` must immediately follow and reference that definition's sole approving review. A rejected
review cannot freeze, and retry starts a new definition.

Canonical JSON uses sorted keys, compact separators, UTF-8, and `allow_nan=False`; every hash below
is lowercase SHA-256 over the UTF-8 canonical JSON bytes. The verified-source map is exactly
`project_id`, `case_contract_id`, `source_contract_id`, `case_revision`,
`verified_read_sha256`, `projection_sha256`, `run_id`, and `cutoff_confirmed_at`.
`verified_read_sha256` is the outer `VerifiedBlindSemanticReadV1.content_sha256`, and
`projection_sha256` is SHA-256 of canonical JSON for the exact inner
`BlindSemanticProjectionV1.to_dict()`. Before that full-object hash is accepted, the embedded
`content_sha256` is separately recomputed from its specified self-excluding map and verified.

The empty semantic head is the hash of exactly
`{"schema":"ResearchSemanticHeadV1","schema_version":1,"project_id":PROJECT_ID,"event_sha256":null}`;
after the first append the head is the latest `event_sha256`. The exact semantic-artifact maps are:

- Definition: `schema: ResearchSemanticDefinitionV1`, `schema_version: 1`,
  `event_type: definition`, the verified-source map, `prior_semantic_head_sha256`,
  `definition_label`, and `definition_text`.
- Review: `schema: ResearchSemanticReviewV1`, `schema_version: 1`, `event_type: review`, the
  verified-source map, `prior_semantic_head_sha256`, `definition_id`, `review_decision`, and
  `review_text`.
- Freeze: `schema: ResearchSemanticFreezeV1`, `schema_version: 1`, `event_type: freeze`, the
  verified-source map, `prior_semantic_head_sha256`, `definition_id`, and `review_id`.

The semantic artifact hash is the hash of that exact map and its ID is respectively
`sd_<sha256>`, `sr_<sha256>`, or `sf_<sha256>`. Receipt identity and operational time are not
semantic-artifact inputs. `payload_sha256` is the hash of the exact `SemanticOwnerActionV1`
payload below. `ResearchSemanticEventIdentityV1` contains exactly `schema`, `schema_version`,
`event_type`, the verified-source map, `sequence`, `prior_semantic_head_sha256`,
`semantic_artifact_id`, `semantic_artifact_sha256`, `definition_id`, `review_id`,
`review_decision`, the decoded canonical `payload`, `payload_sha256`, `receipt_id`, `actor`,
`reason`, and `recorded_at`. `event_sha256` hashes that exact map and `event_id` is
`se_<event_sha256>`. Persisted reads recompute all four hashes and fail closed on any gap, bad
reference, invalid transition, or receipt mismatch.

For that identity map, `schema` is exactly `ResearchSemanticEventIdentityV1` and
`schema_version` is exactly `1`.

The exact `SemanticOwnerActionV1` payload has `schema: SemanticOwnerActionV1`,
`schema_version: 1`, and no extra keys. Common keys are `schema`, `schema_version`, `event_type`,
`verified_read_sha256`, `projection_sha256`, `run_id`, `cutoff_confirmed_at`, and
`expected_semantic_head_sha256`. A definition adds `definition_label` (1..256 safe characters)
and `definition_text` (1..8192); a review adds `definition_id`, `review_decision` (`approve` or
`reject`), and `review_text` (1..8192); a freeze adds `definition_id` and `review_id`.
The server mechanically recomputes and must exactly match all source fields from the current
`VerifiedBlindSemanticReadV1`; the browser never supplies an authoritative cutoff. The expected
semantic head is the latest event hash, or the SHA-256 of the canonical empty
`ResearchSemanticHeadV1` for that project. It is bound in addition to the existing case revision,
because semantic appends do not change `research_case_revision`.

The generic owner-action executor is not used for `record_semantic_event`: it currently consumes
a receipt before delegating to a CLI subprocess. After WebAuthn verification, one dedicated
`BEGIN IMMEDIATE` transaction re-reads the unused challenge and credential counter, current case
revision, current semantic head, active case/source contracts, and mechanically verified semantic
source; validates the exact payload and transition; then increments the counter, consumes the
challenge, appends the receipt, and appends one semantic event. Any failure rolls back all four
effects. The receipt outcome is exactly `status: semantic_event_recorded`,
`semantic_event_id`, and `semantic_event_sha256`. The event must equal its receipt on these exact
bindings: `action_type = record_semantic_event`; project IDs; receipt `artifact_hash` = event
`semantic_artifact_sha256`; receipt `expected_case_revision` = event `case_revision`; receipt
`request_hash` = event `payload_sha256`; actor; reason; and receipt `performed_at` = event
`recorded_at`. The receipt outcome IDs/hashes must also match the event. These rules make linkage
bijective.

A failure before commit leaves the challenge unused, credential counter unchanged, and no receipt
or event; the same still-valid assertion may retry the exact transaction. Once commit succeeds,
the action is complete even if the HTTP response is lost. A retry of that consumed challenge with
the exact original request hash performs a read-only linkage validation and returns the already
committed receipt/event result; it never verifies new authority, increments the counter, executes,
or appends again. A different request hash or any linkage defect fails closed. This is idempotent
response recovery, not reusable authorization. Public semantic presentation remains deferred to
S5c.

CLI authority does not widen: `alpha research semantic-projection PROJECT_ID --json` remains the
verified read source and there is no direct semantic-write CLI command. REST adds no route: only
the existing owner-auth challenge/perform endpoints accept the new closed action and special-case
its atomic transaction. MCP adds no read or write and remains pinned at 62 tools. S5b does not add
a screen, frontend-derived authority, D1/D2 transition, promotion, holdout, paper, broker, order,
or future-value reveal; the S5a projection remains `semantic_status: unfrozen`.

Migration takes one `BEGIN IMMEDIATE` lock from before creation and exact verification of
`workstation.sqlite3.v4.bak` through the receipt-table rebuild, v5 DDL, `foreign_key_check`, v5
marker, and commit. The backup rejects symlinks/non-files and requires `integrity_check = ok`,
`user_version = 4`, and exact logical fingerprint equality. A waiting migrator re-reads the
version under the lock and returns after v5 wins. Failure rolls back to v4 while retaining the
verified backup for an exact retry. V5 receipt/semantic objects are protected and excluded from
steady-state schema healing; a missing object, hash/sequence/transition defect, or receipt/event
mismatch fails closed without repair. After a committed v5 migration there is no automatic
downgrade or backup restore. Recovery requires a separate owner-approved forensic, data-loss, and
forward-migration procedure; S5b adds no recovery command.

All supported openings finish at v5 through the same reviewed v4-to-v5 boundary. A fresh v0 store
creates v5 atomically. Existing v1, v2, and v3 stores first use their existing exact
`.v1.bak`/`.v2.bak`/`.v3.bak` migration discipline to commit v4, then re-read `user_version` and
run the specified v4-to-v5 transaction, including a new exact `.v4.bak`. An existing v4 store runs
that transaction directly. `PRAGMA foreign_key_check` must return zero rows before the v5 marker.
Every waiting migrator re-reads the version under each lock and a v5 winner returns; no path runs
the receipt rebuild twice.

## Governance boundaries

- D1 remains owner-only through the existing trusted CLI and approved research contract.
- D2 remains sealed, one-shot, and owner-authorized through the existing executor.
- Promotion, holdout, paper, broker, and order authority remain unchanged.
- MCP remains pinned at 62 tools. This ADR adds no MCP tool and grants no MCP owner
  mutation, semantic labeling, D1 launch, D2, or promotion capability.
- Touch ID owner presence and exact payload/revision binding remain the authority for
  closed research-lifecycle actions.
- Blind semantic delivery is split deliberately. Its first slice obtains each cutoff from the
  mechanically recomputed `d0_acceptance.json` measurement event and rejects unless normalized
  identities and clocks in integrity-checked `events.json` and `chart-data.json.events` exactly
  match that acceptance source. A caller or browser never supplies the time. The pure
  `alpha_study` projection never imports or calls a detector; the CLI boundary invokes the existing
  ControlStore D0 verifier, which mechanically recomputes the registered fixture before supplying
  verified artifact bytes. The CLI emits a closed `VerifiedBlindSemanticReadV1` envelope whose
  only keys are `schema`, `schema_version`, `source_verification`, `authority`, `run_id`,
  `projection`, and `content_sha256`; `authority` is always `none`, and the hash covers the other
  six canonical semantic fields rather than itself. That slice cannot claim an owner label or
  freeze. A later additive
  SQLite v5 slice may add append-only
  semantic-definition/review events only with exact Touch ID receipt, payload-hash, and
  case-revision binding; it does not create a second research authority or any MCP capability.
- External packages are not dependencies of this ADR or S0. Future adapters/workers
  require separate version, lock, licence, provenance, isolation, and acceptance review.
- Existing ALPHA data authority remains provider-, venue-, family-, unit-, frequency-,
  and timestamp-specific. An adapter may not silently substitute any of those fields.
- The final deletion or replacement of legacy orchestration requires old/new parity and
  explicit owner approval.

## Staged implementation

The dated FeaturePlan at
`docs/superpowers/plans/2026-08-21-generic-study-composition.md` is normative for
execution order, verification, rollback, and scope. Its slices are:

1. S0: plan and ADR only.
2. S1: authority and contract map.
3. S2: empty `alpha-study` package seam and import boundary.
4. S3: strict canonical projections and provenance.
5. S4: one existing operator parity slice with D0/bias/determinism checks.
6. S5a1: pure byte-bound non-authoritative semantic projection contract.
7. S5a2: verified completed-D0 artifact resolver, CLI envelope, and future-poison guard.
8. S5a3: `GET /api/research/cases/{project_id}/semantic-projection`, with no request body or
   query parameters, returning the unchanged verified CLI envelope through strict nested response
   models. CLI unavailability is a 404; structurally malformed parsed CLI output is a redacted 502.
   Only generated OpenAPI/types and operation-governance records change—no handwritten frontend
   client, presentation, or mutation surface.
9. S5b: additive SQLite v5 semantic definition/review events and Touch ID binding.
10. S5c: semantic presentation inside the existing Research screen.
11. S6: owner-only D1 integration mapped to existing contracts and ledgers.
12. S7: individually approved external adapters/workers/oracles.
13. S8: acceptance studies, UI projections, and cleanup only after parity.

Every slice is additive and independently revertable. No later slice may widen scope
because an external library or a favorable research result makes it convenient.

## Non-decisions

This ADR does not:

- authorize any runtime implementation by itself;
- authorize autonomous Codex, Luna, Terra, or any other agent to approve or launch D1;
- create a second D1/D2, evidence, attempt, approval, or promotion store;
- change the MCP tool count or add MCP capabilities;
- approve TA-Lib, Twelve Data, Alphalens, mplfinance, Qlib, RD-Agent, PyPortfolioOpt,
  Riskfolio-Lib, `bt`, Zipline Reloaded, pfhedge, pybotters, or any other dependency;
- replace `alpha-backtest` or treat an external backtester as authoritative;
- authorize broker, exchange, paper, order, execution, distribution, hosting, or
  multi-user behavior;
- treat advisor or multi-agent agreement as empirical evidence.

## Acceptance

The owner's instruction to implement the approved staged plan accepts the projection-only
boundary and contract map. Runtime implementation remains conditional on these invariants:

- the 62-tool MCP pin and owner-only D1 boundary remain unchanged;
- each proposed contract maps to one existing authority with no competing source;
- event clocks and feature/vintage lineage are sufficient for all approved domains;
- external dependencies are deferred until their own adapter decisions;
- every implementation slice has a verified command, expected result, and rollback;
- private local-only scope and third-party compliance boundaries remain intact.

S0 acceptance was limited to `gate.py plan-check`, ADR existence, and whitespace validation.
S1 adds this accepted authority map and synchronizes the ADR index, operating manual, and
append-only delivery history without changing runtime behavior.

## Consequences

Positive consequences:

- Generic study composition can be added without weakening the established research
  authority or creating a second control plane.
- Existing D0/D1/D2, evidence, owner-presence, data-lineage, and promotion contracts
  remain the single source of truth.
- External capabilities can be evaluated independently after the internal seam is
  proven.
- Each slice has a bounded rollback and a concrete verification gate.

Costs and limitations:

- The report's broad feature list is intentionally deferred.
- Contract reconciliation is required before any new schema or package code.
- Some desired cross-domain views may need separate domain projections rather than one
  universal row type.
- Runtime changes will require current-state documentation updates in the same slice;
  S0 deliberately makes no such changes.
