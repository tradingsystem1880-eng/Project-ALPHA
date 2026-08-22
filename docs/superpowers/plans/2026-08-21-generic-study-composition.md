# Generic Study Composition and External Capability Adapters — Implementation Plan

```json
{
  "schema_version": 1,
  "title": "Generic study composition as a governed projection layer",
  "context": "The attached deep-research-report.md is proposal context for Project ALPHA at commit a3a519b35732bdd4c8874689f980c6d3f75acd5f. The approved implementation direction is narrower than that report: alpha-study is a research-plane composition/projection package only; existing alpha_research, alpha_cli, the control store, immutable artifacts, owner-only D1/D2 transitions, Touch ID owner actions, and the 62-tool MCP surface remain authoritative. S0 created the plan and proposed ADR; S1 accepted the authority map and synchronized current-state documentation. Runtime work begins only at S2.",
  "assumptions": [
    {
      "statement": "The repository baseline is commit a3a519b35732bdd4c8874689f980c6d3f75acd5f and CLAUDE.md is the authoritative operating manual.",
      "verified_by": "git rev-parse HEAD and CLAUDE.md:1-15"
    },
    {
      "statement": "Existing research authority remains in alpha_research plus alpha_cli/control-store orchestration; a new package must not create a second D1/D2 or promotion path.",
      "verified_by": "CLAUDE.md:44-52, CLAUDE.md:76, .claude/rules/alpha-research.md:9-22, docs/adr/0025-empirical-d1-research-runner-admission.md, docs/adr/0026-d2-confirmation-readiness-gate-promotion-override.md"
    },
    {
      "statement": "MCP remains a bounded top-of-DAG surface pinned at 62 tools and cannot gain D1 owner mutation authority in this plan.",
      "verified_by": "CLAUDE.md:49-52 and .claude/rules/alpha-mcp.md:8-13"
    },
    {
      "statement": "The repository is permanently private and local-only; third-party notices, provider terms, and data-retention restrictions remain applicable.",
      "verified_by": "CLAUDE.md private-local-scope golden rule and docs/adr/0032-governed-crypto-data-house.md:1-40"
    },
    {
      "statement": "S0 is documentation-only and is limited to the two files named in this plan.",
      "verified_by": "git status --short before and after the S0 edits"
    }
  ],
  "alternatives_considered": [
    "Implement the attached report as written: rejected because its autonomous MCP D1 writes, new ledgers, broad schema, and external integrations would conflict with existing owner-only research authority and duplicate current control-plane contracts.",
    "Create a second independent research control plane in alpha-study: rejected because it would create competing sources of truth for D1, D2, promotion, attempts, approvals, and evidence.",
    "Add external packages before the internal seam is proven: rejected because dependency versions, licences, provider entitlements, worker isolation, and point-in-time semantics are not yet approved or mapped.",
    "Modify CLAUDE.md, indexes, or runtime files in S0: rejected because this slice is explicitly limited to the plan and ADR; behavior-changing slices must update current-state documentation with their own verified change."
  ],
  "pre_mortem": [
    "The new package becomes an accidental second authority: fail if alpha-study writes approvals, D1/D2 state, promotion records, broker state, or authoritative control rows; prevent this with projection-only interfaces, import-linter rules, and authority tests before any runtime slice.",
    "A broad EventTableV1 hides domain-specific clocks: fail if macro vintages, feature availability, factor observations, or venue identity cannot be represented without look-ahead; require an explicit contract map and per-field availability lineage before schema implementation.",
    "An MCP convenience path bypasses owner presence: fail if a proposed tool can approve, launch owner-only D1, read D2, promote, reveal holdout, or record owner semantic labels; keep MCP at 62 tools and use existing public read/projection seams only.",
    "External adapters destabilize the local gate or data authority: fail if an optional dependency is imported at normal startup, lacks a lock/licence/provenance record, or changes provider/venue/unit/frequency semantics; defer all external runtime dependencies until an isolated adapter slice is separately approved.",
    "The migration deletes legacy behavior before parity: fail if a generic projection cannot reproduce the selected existing research case or if rollback requires data rewriting; keep every slice additive and revertable until parity and owner deletion approval."
  ],
  "slices": [
    {
      "title": "S0 plan and ADR (this slice)",
      "verify": "uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-08-21-generic-study-composition.md && test -s docs/adr/0035-generic-study-composition-and-external-capability-adapters.md && git diff --check -- docs/superpowers/plans/2026-08-21-generic-study-composition.md docs/adr/0035-generic-study-composition-and-external-capability-adapters.md",
      "expected": "plan-check accepts the FeaturePlan; ADR exists; diff has no whitespace errors; no files outside the two S0 documents change",
      "rollback": "git revert the S0 documentation commit, or remove only the two S0 files before commit",
      "files": [
        "docs/superpowers/plans/2026-08-21-generic-study-composition.md",
        "docs/adr/0035-generic-study-composition-and-external-capability-adapters.md"
      ],
      "status": "done"
    },
    {
      "title": "S1 authority and contract map",
      "verify": "Review the proposed-to-existing contract matrix; run uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-08-21-generic-study-composition.md and uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_repo_awareness_drift.py tests/unit/test_claude_md_relocation.py; confirm the audited CLAUDE.md acknowledgement",
      "expected": "Every proposed alpha-study contract has exactly one existing authority, an explicit projection direction, immutable identity/hash rules, and a documented rejection or deferral for unmapped fields; ADR index, operating manual, and delivery history agree",
      "rollback": "Revert the S1 documentation/decision commit; do not migrate or rewrite existing control-store records",
      "files": [
        "docs/adr/0035-generic-study-composition-and-external-capability-adapters.md",
        "docs/superpowers/plans/2026-08-21-generic-study-composition.md",
        "docs/adr/README.md",
        "docs/BUILD-STATUS.md",
        "CLAUDE.md"
      ],
      "status": "done"
    },
    {
      "title": "S2 alpha-study package seam",
      "verify": "Before protected config edits run uv run python scripts/gate.py ack --reason \"Add the accepted alpha-study DAG and coverage boundary\"; add alpha-study to root workspace dependency/source metadata, isort ownership, coverage sources, import-linter roots, and every bidirectional forbidden contract; then run uv run ruff check ., uv run mypy packages apps tests, uv run lint-imports, uv run pytest -q -m \"not network\", uv run python scripts/gate.py fast, and uv run python scripts/gate.py full before commit",
      "expected": "An additive package seam is enforced in both directions: alpha-study composes only core/data/patterns/research; lower layers, MCP, and web cannot import it; coverage includes alpha_patterns and alpha_study without lowering 93%; no research behavior, authority, CLI, MCP count, or web behavior changes; fast and full stamps bind to the exact tree",
      "rollback": "Revert the S2 additive package commit; remove only newly added alpha-study files and its contract/configuration entries",
      "files": [
        "packages/alpha-study/**",
        "pyproject.toml",
        "tests/unit/study/**"
      ],
      "status": "done"
    },
    {
      "title": "S3a canonical lineage and observation tables",
      "verify": "Before rule/manual edits run uv run python scripts/gate.py ack --reason \"Publish the accepted alpha-study V1 lineage and observation contracts\"; run uv run pytest -q tests/unit/study -m \"not network\", uv run mypy packages/alpha-study, uv run python scripts/gate.py determinism, uv run python scripts/gate.py fast, and uv run python scripts/gate.py full before commit",
      "expected": "FeatureValueV1, EventTableV1, and the separate FactorObservationTableV1 use strict exact-key schemas, UTC causal clocks, finite typed values, immutable artifact/snapshot/computation lineage, canonical ordering, and tamper-evident hashes; semantic timestamps affect identity while operational timestamps are absent; no outcome, authority, persistence, or execution behavior is added",
      "rollback": "Revert the S3a contract commit; retain existing alpha_research artifacts and inference byte-identically",
      "files": [
        "packages/alpha-study/**",
        "tests/unit/study/**",
        ".claude/rules/alpha-study.md",
        "CLAUDE.md",
        "docs/ARCHITECTURE.md",
        "docs/BUILD-STATUS.md"
      ],
      "status": "done"
    },
    {
      "title": "S3b operator and existing-authority references",
      "verify": "uv run pytest -q tests/unit/study -m \"not network\" && uv run mypy packages/alpha-study && uv run python scripts/gate.py determinism && uv run python scripts/gate.py fast && uv run python scripts/gate.py full before commit",
      "expected": "OperatorRegistrationV1 is closed and Git-owned; DetectorValidationV1 and ExplorationMandateV1 are non-authoritative immutable references to exact existing D0 artifacts, contracts, frozen plans, topology, fingerprints, reservations, and approved budgets. They expose no producer pass flag, approval, launchability, mutable status, remaining budget, or parallel ledger",
      "rollback": "Revert the S3b reference-contract commit; leave all D0 recomputation, contract approval, reservation, and launch truth in the existing CLI and ControlStore",
      "files": [
        "packages/alpha-study/**",
        "tests/unit/study/**",
        ".claude/rules/alpha-study.md",
        "CLAUDE.md",
        "docs/ARCHITECTURE.md",
        "docs/BUILD-STATUS.md"
      ],
      "status": "done"
    },
    {
      "title": "S3c derived study projections",
      "verify": "uv run pytest -q tests/unit/study -m \"not network\" && uv run mypy packages/alpha-study && uv run python scripts/gate.py determinism && uv run python scripts/gate.py fast && uv run python scripts/gate.py full before commit",
      "expected": "FindingV1, MechanismGraphV1, AdvisorProposalV1, and StudyWorkspaceManifestV1 are deterministic source-linked projections only; they contain no raw dataset copy, writable authority, owner approval, D2 reveal, promotion, paper, broker, or order claim",
      "rollback": "Revert the S3c projection commit; retain authoritative artifacts, ControlStore records, and existing workspace/UI behavior unchanged",
      "files": [
        "packages/alpha-study/**",
        "tests/unit/study/**",
        ".claude/rules/alpha-study.md",
        "CLAUDE.md",
        "docs/ARCHITECTURE.md",
        "docs/BUILD-STATUS.md"
      ],
      "status": "done"
    },
    {
      "title": "S4 one existing operator parity slice",
      "verify": "Before protected bias-guard edits run uv run python scripts/gate.py ack --reason \"Add future-poison protection for the accepted study projection\"; run uv run pytest -q tests/unit/study tests/bias_guards -m \"not network\", uv run python scripts/gate.py fast, and uv run python scripts/gate.py full before commit",
      "expected": "One existing governed operator is projected without a second source of truth; known-truth, future-append, availability-clock, determinism, lineage, old/new parity, and the must-fail leaky twin pass; fast and full stamps bind to the exact tree",
      "rollback": "Revert the S4 adapter/tests commit; leave the legacy operator path active and unchanged",
      "files": [
        "packages/alpha-study/**",
        "tests/unit/study/**",
        "tests/bias_guards/**",
        ".claude/rules/alpha-study.md",
        "CLAUDE.md",
        "docs/ARCHITECTURE.md",
        "docs/BUILD-STATUS.md"
      ],
      "status": "done"
    },
    {
      "title": "S5a1 byte-bound blind semantic contract",
      "verify": "Run strict schema/tamper/cardinality/value/order tests, the study suite, mypy, Ruff, all import contracts, perturbed-environment determinism, independent review, fast gate, and full gate before commit",
      "expected": "The pure alpha_study contract hashes complete D0 acceptance/events/chart bytes, requires exact one-event identity and clock agreement, derives numeric chart points only from the bound chart series, and emits only pre-cutoff values plus an aggregate masked count. It remains authority none, semantic status unfrozen, and lineage not_checked; it never imports or calls a detector.",
      "rollback": "Revert the additive S5a1 package commit; retain every D0 artifact and CLI/web behavior unchanged",
      "files": [
        "packages/alpha-study/**",
        "tests/unit/study/**",
        ".claude/rules/alpha-study.md",
        "CLAUDE.md",
        "docs/ARCHITECTURE.md",
        "docs/BUILD-STATUS.md"
      ],
      "status": "done"
    },
    {
      "title": "S5a2 verified D0 resolver and CLI semantic read",
      "verify": "Before protected bias-guard edits run uv run python scripts/gate.py ack --reason \"Add future-poison protection for the verified blind semantic read\"; test bounded selected-byte reads, verify/read race hashes, wrong lineage/no D0, manifest/artifact tamper, no-write database equality, CLI JSON, and the unchanged 62-tool MCP denial. The future-poison guard compares cutoff and every emitted pre-cutoff point identity, clock, and value while allowing the bound chart hash and aggregate masked_count to change; it asserts no post-cutoff identity, clock, feature, or value is emitted, and its must-fail leaky twin exposes the appended poisoned post-cutoff value. Run focused, determinism, fast, and full gates before commit",
      "expected": "A narrow read-only ControlStore helper derives the current active exploration contract from the research case, including the exploration parent when the current contract is confirmatory, and rejects unless exactly one attempt for that active lineage has phase pilot, kind d0-synthetic-pilot, status completed, an immutable run, and the registered double-bottom operator. It invokes the existing mechanical D0 verifier, then reads only bounded regular d0_acceptance.json, events.json, and chart-data.json files and rechecks each selected byte hash against the verified manifest. The acceptance validator delegates the existing canonical, identity, and mechanical checks to exact in-memory bytes after binding; detector, fixture, estimator, power, and other quantitative semantics are unchanged. The CLI accepts only PROJECT_ID and --json and returns a strict VerifiedBlindSemanticReadV1 whose exact keys are schema, schema_version, source_verification, authority, run_id, projection, and content_sha256; their fixed values include schema VerifiedBlindSemanticReadV1, schema_version 1, source_verification verified_completed_d0_recomputation, and authority none. content_sha256 is the established canonical JSON SHA-256 of the other six fields and excludes itself; no extra key is accepted. It creates no event, reservation, attempt, receipt, job, phase transition, owner-freeze claim, or MCP tool.",
      "rollback": "Revert the S5a2 read-helper/CLI/guard commit; retain S5a1 and all immutable D0 records unchanged",
      "files": [
        "apps/alpha-cli/src/alpha_cli/control_store.py",
        "apps/alpha-cli/src/alpha_cli/research_cmds.py",
        "apps/alpha-cli/src/alpha_cli/research_runtime.py",
        "apps/alpha-cli/src/alpha_cli/study_semantic.py",
        "packages/alpha-study/src/alpha_study/__init__.py",
        "tests/unit/test_research_control_store.py",
        "tests/unit/study/test_double_bottom_adapter.py",
        "tests/integration/test_research_cli.py",
        "tests/integration/test_research_mcp.py",
        "tests/bias_guards/test_verified_semantic_read_future_poison.py",
        ".claude/rules/alpha-cli.md",
        "docs/**",
        "CLAUDE.md"
      ],
      "status": "done"
    },
    {
      "title": "S5a3 web-only semantic GET projection",
      "verify": "Test exact subprocess argv with no cutoff flag, non-object/invalid/extra parsed output, strict nested literals/hashes/UTC/finite floats/counts, GET success, 404 CLI unavailability, redacted 502 structurally malformed parsed CLI output, GET-only OpenAPI with no query/body parameters, generated OpenAPI/types freshness, generated operation classification/matrix freshness, unchanged handwritten frontend client/types, unchanged mutation routes, unchanged 62-tool MCP, fast gate, and full gate before commit",
      "expected": "GET /api/research/cases/{project_id}/semantic-projection has no request body or query parameters and invokes only alpha research semantic-projection PROJECT_ID --json through the existing bounded subprocess seam. It returns the exact CLI object through three strict Pydantic models: the outer VerifiedBlindSemanticReadV1 has exactly schema=VerifiedBlindSemanticReadV1, schema_version=1, source_verification=verified_completed_d0_recomputation, authority=none, 16-lowercase-hex run_id, projection, and lowercase-SHA-256 content_sha256; its BlindSemanticProjectionV1 child has exactly schema=BlindSemanticProjectionV1, schema_version=1, authority=none, cutoff_source=d0_acceptance_measurement_reference, lineage_verification=not_checked, semantic_status=unfrozen, matching 16-hex run_id, three lowercase artifact SHA-256 values, canonical UTC-Z cutoff_confirmed_at, a nonnegative strict masked_count, points, and lowercase content_sha256; each point has exactly point_id, canonical UTC-Z available_at, and a strict finite float value. Web does not recompute hashes, detector geometry, cutoff, or masking. CLI subprocess/unavailable failures map to 404; a parsed non-object or any missing, extra, malformed, noncanonical, nonfinite, or wrong-literal response maps to a redacted 502 without returning the invalid payload. Only openapi.json, generated.ts, and generated operation-governance records change; handwritten client.ts/types.ts and all frontend presentation remain unchanged. No browser cutoff, owner action, job, D1/D2 control, promotion, paper, broker, order, or MCP capability is added.",
      "rollback": "Revert the S5a3 web projection commit; retain the verified CLI read and all existing Workstation screens unchanged",
      "files": [
        "apps/alpha-web/src/alpha_web/_research.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/src/alpha_web/api/research.py",
        "apps/alpha-web/frontend/openapi.json",
        "apps/alpha-web/frontend/src/api/generated.ts",
        "docs/governance/openapi-operation-classification.json",
        "docs/governance/capability-authority-matrix.md",
        "tests/unit/test_web_research_projection.py",
        "tests/integration/test_web_api_research.py",
        "tests/integration/test_research_mcp.py",
        ".claude/rules/alpha-web.md",
        "docs/**",
        "CLAUDE.md"
      ],
      "status": "done"
    },
    {
      "title": "S5b SQLite v5 semantic definition and owner review",
      "verify": "Before runtime work, freeze the valid v5 schema, receipt-table CHECK widening, sd_/sr_/sf_/se_ canonical identities, exact SemanticOwnerActionV1 variants, semantic-head plus case-revision binding, atomic receipt/event transaction, migration/recovery policy, and CLI/REST/MCP boundary in this plan and ADR; run plan-check and obtain independent Terra APPROVE. For implementation, test v1/v2/v3 progression through committed v4 and the exact v4 backup, lossless receipt-row rebuild, rollback/retry, post-commit response-loss idempotent return, concurrent migrators, protected-v5 no-heal, canonical hashes, contiguous definition->review->freeze sequencing, rejected-review denial, stale case/head/source, payload tamper, receipt/event bijection, injected atomic failure, unchanged semantic read/GET, REST special dispatch, OpenAPI freshness, and the 62-tool MCP denial; run focused, determinism, fast, and full gates before every commit.",
      "expected": "Schema v5 is logically additive and preserves every v4 row; one transactional physical rebuild widens only the owner_action_receipts action_type CHECK with record_semantic_event. The new strict append-only research_semantic_events table records canonical definition, review, and freeze artifacts bound to the active case contract, S5a exploration source contract, case revision, semantic head, mechanically reverified semantic read/hash/run/cutoff, verified actor/reason, and exactly one receipt. One dedicated BEGIN IMMEDIATE transaction consumes the Touch ID assertion, writes its receipt, and writes exactly one event or rolls everything back. There is no direct CLI write, mutable frozen flag, parallel attempt ledger, D1/D2 transition, future reveal, new REST route, frontend authority, or MCP semantic capability.",
      "rollback": "Before commit/deployment, revert the S5b change. Migration failure rolls the database transaction back to v4 and retains only the verified exact v4 backup for retry. After a committed v5 migration, never auto-downgrade, overwrite the v5 database, restore the backup, heal missing protected v5 objects, or discard semantic events; recovery requires a separate owner-approved forensic data-loss assessment and forward migration.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/control_store.py",
        "apps/alpha-cli/src/alpha_cli/owner_auth.py",
        "apps/alpha-web/src/alpha_web/api/owner_auth.py",
        ".claude/rules/alpha-cli.md",
        ".claude/rules/alpha-web.md",
        "CLAUDE.md",
        "tests/unit/test_research_control_store.py",
        "tests/unit/test_owner_auth_store.py",
        "tests/unit/test_owner_auth.py",
        "tests/unit/test_owner_auth_api.py",
        "tests/integration/test_research_cli.py",
        "tests/integration/test_web_api_research.py",
        "docs/**"
      ],
      "status": "pending"
    },
    {
      "title": "S5c existing-screen semantic presentation",
      "verify": "Run the affected frontend unit, generated-contract, lint, production-build, accessibility/E2E checks plus the Python integration, fast, and full gates before commit",
      "expected": "The existing ResearchCockpit renders only the S5a masked response and S5b owner state through server projections. No seventh Workstation screen, browser-side mask, raw artifact download, MCP action, D1/D2 control, promotion, paper, broker, or order control is added.",
      "rollback": "Revert the S5c UI/projection commit; retain S5a/S5b server contracts and all existing six-screen behavior",
      "files": [
        "apps/alpha-web/frontend/**",
        "apps/alpha-web/src/**",
        "tests/integration/**",
        "docs/**",
        "CLAUDE.md"
      ],
      "status": "pending"
    },
    {
      "title": "S6 owner-only D1 integration",
      "verify": "uv run pytest -q tests/integration/test_research_program_acceptance.py tests/unit/test_research_control_store.py -m \"not network\" && uv run python scripts/gate.py full",
      "expected": "The projection maps to the existing owner-approved D1 contract, attempt ledger, budgets, and launch reservations; out-of-scope calls fail; MCP remains 62 tools and cannot launch owner-only D1",
      "rollback": "Revert the S6 integration commit; disable only the new projection path and keep existing alpha research run behavior authoritative",
      "files": [
        "packages/alpha-study/**",
        "apps/alpha-cli/**",
        "tests/unit/study/**",
        "tests/integration/**"
      ],
      "status": "pending"
    },
    {
      "title": "S7 individually approved external adapters",
      "verify": "Before code, pass a separate ADR-0011 evidence packet covering the concrete capability gap, smallest boundary, exact revision, maintenance/security evidence, direct/transitive lock impact, licence/terms, deterministic offline behavior and test double, secrets, removal path, captured fixtures, and separately authorized network smoke; then run the adapter suite, uv run ruff check ., uv run mypy packages apps tests, uv run lint-imports, uv run python scripts/gate.py fast, and uv run python scripts/gate.py full before commit",
      "expected": "Each candidate has an explicit adopt/defer/reject decision; each adopted optional adapter has an exact lock/version/licence/provenance record, cannot write authoritative state, preserves provider-native identity, availability, units, and retention constraints, and is not required for normal startup",
      "rollback": "Revert only the adapter commit and remove its optional extra/worker; preserve all ALPHA-owned artifacts and authority records",
      "files": [
        "packages/alpha-study/**",
        "packages/alpha-data/**",
        "packages/alpha-strategies/**",
        "packages/alpha-backtest/**",
        "workers/**",
        "tests/adapters/**"
      ],
      "status": "pending"
    },
    {
      "title": "S8 acceptance, UI projections, and cleanup",
      "verify": "Run the complete Python and frontend gates, the three approved synthetic/technical, macro, and cross-sectional acceptance studies, and an owner parity review before any deletion",
      "expected": "All studies use the common projection API, no D2/promotion/execution authority is added, existing cases remain behaviorally preserved, and cleanup is separately owner-approved",
      "rollback": "Revert the acceptance/UI/cleanup commit; do not rewrite or delete legacy orchestration until parity evidence is preserved",
      "files": [
        "packages/alpha-study/**",
        "apps/alpha-cli/**",
        "apps/alpha-web/**",
        "tests/**",
        "docs/**"
      ],
      "status": "pending"
    }
  ],
  "tier_impact": ["dag", "protected", "bias", "determinism"],
  "docs_to_update": [
    "docs/superpowers/plans/2026-08-21-generic-study-composition.md",
    "docs/adr/0035-generic-study-composition-and-external-capability-adapters.md",
    "docs/adr/README.md",
    "docs/ARCHITECTURE.md",
    "docs/BUILD-STATUS.md",
    "CLAUDE.md",
    ".claude/rules/alpha-study.md"
  ],
  "out_of_scope": [
    "All S0 runtime changes; no package, CLI, MCP, REST, web, worker, data, strategy, validation, or test implementation in this slice",
    "Any new MCP tool or change to the pinned 62-tool surface",
    "Autonomous or MCP-launched D1, D2 access, holdout reveal, strategy promotion, paper, broker, order, or owner-approval authority",
    "Replacing or duplicating existing alpha_research, alpha_cli, control-store, ResearchGatePacket, D2 boundary, Touch ID, or promotion contracts",
    "External dependency installation or runtime integration, including TA-Lib, Twelve Data, Alphalens, mplfinance, Qlib, RD-Agent, PyPortfolioOpt, Riskfolio-Lib, bt, Zipline, pfhedge, and pybotters",
    "Ambiguous repository identities and unverified licence/version/platform claims from the report",
    "Big-bang migration, deletion of legacy workflows, or raw-data copying into study workspaces",
    "Distribution, hosting, multi-user, sale, or production scope; Project ALPHA remains private and local-only",
    "Changing AGENTS.md, harness policy, generated capability counts, or owner-auth authority beyond the exact S5b Touch ID-bound semantic definition/review actions; no other workflow behavior may change beyond the mechanical fourteenth-wheel build/import smoke required by S2"
  ],
  "files": [
    "docs/superpowers/plans/2026-08-21-generic-study-composition.md",
    "docs/adr/0035-generic-study-composition-and-external-capability-adapters.md",
    "packages/alpha-study/**",
    "apps/alpha-cli/**",
    "apps/alpha-web/**",
    "tests/**",
    "docs/**",
    "pyproject.toml",
    "uv.lock",
    "CLAUDE.md",
    ".claude/rules/alpha-study.md",
    "docs/operations/claude-code-harness.md",
    "scripts/gate.py",
    ".github/workflows/ci.yml"
  ]
}
```

## S5b invariant freeze

S5b follows the exact schema, identity, payload, sequencing, atomicity, migration, recovery, and
authority contract in ADR-0035's `S5b semantic owner-event freeze` section. The implementation is
split into bounded red-to-green slices:

1. Documentation freeze only: `plan-check`, documentation truth checks, and independent Terra
   review. Runtime remains untouched.
2. Schema v5: exact `.v4.bak`, one lossless receipt-table rebuild solely to add
   `record_semantic_event`, new protected semantic DDL, rollback/retry, and concurrent-migrator
   tests. V1/v2/v3 fixtures prove their existing migrations commit v4 before the common
   v4-to-v5 path runs.
3. Ledger: canonical `sd_`/`sr_`/`sf_` artifacts and `se_` events, contiguous append-only
   transitions, current case/source contracts, verified semantic source, stale case/head/source,
   receipt bijection, and tamper tests.
4. Owner presence: special atomic WebAuthn assertion/credential/challenge/receipt/event transaction,
   injected rollback points, changed-payload replay denial, and read-only idempotent recovery of an
   already committed result after response loss. Existing owner actions retain ADR-0030 behavior.
5. REST contract: add the one literal to strict models, route it only through the atomic path,
   prove `_action_argv`/`_run_json` are not used, and refresh only generated OpenAPI/types and
   operation-governance outputs.
6. Boundary regression and state documentation: existing semantic CLI/GET bytes stay unchanged and
   unfrozen, the Research router mutation set and handwritten frontend remain unchanged, MCP stays
   at 62 tools, and current-state docs describe only delivered behavior.

Exact focused tests are
`tests/unit/test_research_control_store.py`, `tests/unit/test_owner_auth_store.py`,
`tests/unit/test_owner_auth.py`, `tests/unit/test_owner_auth_api.py`,
`tests/integration/test_research_cli.py`, `tests/integration/test_web_api_research.py`, and
`tests/integration/test_research_mcp.py`. No hidden holdout, bias-guard, oracle, harness, MCP config,
or import-linter file is read or changed.

Use each path-scoped acknowledgement immediately before editing that one file. Never arm these
together: the acknowledgement is one-shot and a later command would replace the earlier token.

```text
# Run, then edit only .claude/rules/alpha-cli.md:
uv run python scripts/gate.py ack --path .claude/rules/alpha-cli.md --reason "Document receipt-bound SQLite v5 semantic events without widening authority"

# After the prior acknowledgement has been consumed, run, then edit only .claude/rules/alpha-web.md:
uv run python scripts/gate.py ack --path .claude/rules/alpha-web.md --reason "Document atomic Touch ID semantic-event dispatch without a new route"

# After the prior acknowledgement has been consumed, run, then edit only CLAUDE.md:
uv run python scripts/gate.py ack --path CLAUDE.md --reason "Record the delivered S5b authority and recovery boundary"
```

No acknowledgement is armed for unprotected runtime/test files. If owner-token policy denies the
`CLAUDE.md` acknowledgement, implementation stops for owner direction rather than bypassing it.

## S0 delivery boundary

This slice records the bounded decision and release sequence only. The attached
report remains proposal context. No instruction embedded in that report authorizes
runtime edits, external network/dependency work, new authority, or a change to the
MCP surface. Any later slice requires its own implementation, verification, and
current-state documentation update where behavior changes.
