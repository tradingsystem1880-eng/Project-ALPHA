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
        "tests/unit/study/**"
      ],
      "status": "in_progress"
    },
    {
      "title": "S3c derived study projections",
      "verify": "uv run pytest -q tests/unit/study -m \"not network\" && uv run mypy packages/alpha-study && uv run python scripts/gate.py determinism && uv run python scripts/gate.py fast && uv run python scripts/gate.py full before commit",
      "expected": "FindingV1, MechanismGraphV1, AdvisorProposalV1, and StudyWorkspaceManifestV1 are deterministic source-linked projections only; they contain no raw dataset copy, writable authority, owner approval, D2 reveal, promotion, paper, broker, or order claim",
      "rollback": "Revert the S3c projection commit; retain authoritative artifacts, ControlStore records, and existing workspace/UI behavior unchanged",
      "files": [
        "packages/alpha-study/**",
        "tests/unit/study/**"
      ],
      "status": "pending"
    },
    {
      "title": "S4 one existing operator parity slice",
      "verify": "Before protected bias-guard edits run uv run python scripts/gate.py ack --reason \"Add future-poison protection for the accepted study projection\"; run uv run pytest -q tests/unit/study tests/bias_guards -m \"not network\", uv run python scripts/gate.py fast, and uv run python scripts/gate.py full before commit",
      "expected": "One existing governed operator is projected without a second source of truth; known-truth, future-append, availability-clock, determinism, lineage, old/new parity, and the must-fail leaky twin pass; fast and full stamps bind to the exact tree",
      "rollback": "Revert the S4 adapter/tests commit; leave the legacy operator path active and unchanged",
      "files": [
        "packages/alpha-study/**",
        "tests/unit/study/**",
        "tests/bias_guards/**"
      ],
      "status": "pending"
    },
    {
      "title": "S5 blind semantic projection",
      "verify": "uv run pytest -q tests/unit/study tests/integration -k \"semantic or gallery or availability\" -m \"not network\" && run the affected frontend lint/test/generated-contract/build checks, uv run python scripts/gate.py fast, and uv run python scripts/gate.py full before commit",
      "expected": "A server-enforced projection masks all post-available_at values before owner freeze; owner labels use the existing owner-authenticated path; MCP gains no owner mutation",
      "rollback": "Revert the S5 projection/UI commit; retain the existing research UI and owner-action surface",
      "files": [
        "packages/alpha-study/**",
        "apps/alpha-cli/**",
        "apps/alpha-web/**",
        "tests/unit/study/**",
        "tests/integration/**"
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
    "Changing AGENTS.md, harness policy, owner-auth authority, generated capability counts, or workflow behavior beyond the mechanical fourteenth-wheel build/import smoke required by S2"
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

## S0 delivery boundary

This slice records the bounded decision and release sequence only. The attached
report remains proposal context. No instruction embedded in that report authorizes
runtime edits, external network/dependency work, new authority, or a change to the
MCP surface. Any later slice requires its own implementation, verification, and
current-state documentation update where behavior changes.
