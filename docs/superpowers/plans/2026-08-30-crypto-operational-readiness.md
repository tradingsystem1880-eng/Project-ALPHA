# Crypto Operational-Readiness Closure — Implementation Plan

```json
{
  "schema_version": 1,
  "title": "Close private-local crypto research and non-transmitting sandbox readiness",
  "context": "Project ALPHA is being closed for one private owner Mac, crypto research, and local non-transmitting sandbox use. The generic-study branch at 0783941 contains S0-S5b but is unpublished relative to main. This program finishes the remaining study projections, adds generated per-project workspaces, collects honest owner-machine and BTC/ETH provider evidence, exercises deterministic owner journeys, regenerates governed surfaces, and publishes only after exact-tree gates and review. Live capital, broker paper readiness, commercial hosting, and exhaustive completion of the breadth archive are excluded.",
  "assumptions": [
    {
      "statement": "The starting branch is codex/generic-study-composition at 0783941, clean and 22 commits ahead of main a3a519b.",
      "verified_by": "git status --short --branch, git rev-parse HEAD, and git log --oneline on 2026-08-30"
    },
    {
      "statement": "The release target is private-local crypto research plus non-transmitting sandbox use; paper, broker, live-capital, hosting, distribution, and multi-user authority remain disabled or out of scope.",
      "verified_by": "CLAUDE.md private-local scope and authority rules; ADR-0032 and ADR-0033"
    },
    {
      "statement": "The current MCP surface remains exactly 62 tools and D1 launch remains owner-CLI-only.",
      "verified_by": "CLAUDE.md architecture rules, .claude/rules/alpha-mcp.md, and tests/integration/test_research_mcp.py"
    },
    {
      "statement": "Two existing governed projects are authoritative owner data and must be backfilled without rewriting their SQLite or immutable run identities.",
      "verified_by": "uv run alpha project list --json on 2026-08-30"
    },
    {
      "statement": "The configured Expansion target is not currently writable from this process, so external-storage acceptance cannot be called complete until the owner restores OS access and a fresh storage verification passes.",
      "verified_by": "uv run alpha crypto-data storage-inventory --json on 2026-08-30"
    }
  ],
  "alternatives_considered": [
    "Treat the historical crypto acceptance narrative as current readiness: rejected because provider, volume, credential, and immutable-byte state can drift and requires fresh verification.",
    "Create authoritative strategy folders or copy raw data into them: rejected because SQLite and immutable stores remain authoritative; workspaces are deterministic reference-only projections.",
    "Add new external study adapters during closure: rejected because the current BTC/ETH release bar has no demonstrated capability gap that justifies a new ADR-0011 dependency packet.",
    "Expose D1 launch or semantic authority in the browser or MCP for convenience: rejected because Touch ID and owner-CLI boundaries are release invariants.",
    "Make the 7,602-task breadth archive a release gate: rejected because bounded BTC/ETH core qualification is the release bar and the breadth profile is a continuing governed operation."
  ],
  "pre_mortem": [
    "A generated workspace becomes a second authority or copies private bytes; prevent with closed reference schemas, hash-only indexes, deterministic generation, and no-authority tests.",
    "Atomic replacement destroys the last valid workspace after a partial write; prevent with sibling staging, complete self-verification before rename, and explicit tamper recovery.",
    "Semantic UI presentation leaks masked future values or derives authority client-side; prevent with exact server projection relay, secrecy fixtures, and mutation-denial tests.",
    "Cross-provider BTC/ETH data are silently conflated; prevent with exact provider-native identity, quote, venue, market-type, unit, and PIT-clock assertions.",
    "A historical receipt, missing credential, rate limit, or inaccessible volume is reported as a pass; prevent with fresh dated commands and blocker-preserving acceptance records.",
    "A local green tree is mistaken for publication; prevent with independent review, exact-SHA GitHub checks, merge verification, and post-merge smokes."
  ],
  "slices": [
    {
      "title": "C0 freeze and reconcile the closure program",
      "verify": "uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-08-30-crypto-operational-readiness.md && uv run pytest -q tests/unit/test_documentation_truth.py -m \"not network\" && git diff --check",
      "expected": "The program has bounded release authority, incremental TDD slices, and one honest classification for every scoped roadmap, ADR, risk, and build-status item.",
      "rollback": "Revert only this closure-plan commit; no runtime or owner data changes.",
      "files": [
        "docs/superpowers/plans/2026-08-30-crypto-operational-readiness.md"
      ],
      "status": "done"
    },
    {
      "title": "C1 render semantic state and existing D1 linkage in ResearchCockpit",
      "verify": "Run focused Python projection tests and frontend unit tests after each red-green slice; then frontend lint, coverage, production build, Playwright accessibility, generated-contract freshness, gate fast, and gate full.",
      "expected": "The existing Research screen displays only server-verified masked semantics, Touch-ID-bound definition/review/freeze state, authoritative contract/D1/budget/attempt/promotion references, and next-owner-action guidance; no authority is added.",
      "rollback": "Revert the additive projection and existing-screen UI commits; keep S5a/S5b persistence and owner authority unchanged.",
      "files": [
        "packages/alpha-study/**",
        "apps/alpha-cli/**",
        "apps/alpha-web/**",
        "tests/unit/study/**",
        "tests/integration/**",
        "docs/**",
        ".claude/rules/alpha-cli.md",
        ".claude/rules/alpha-web.md",
        "CLAUDE.md"
      ],
      "status": "pending"
    },
    {
      "title": "C2 add deterministic per-project strategy workspaces",
      "verify": "Red-green focused tests for schema, deterministic bytes, atomic replacement, tamper rejection/recovery, backfill, stale/missing references, no raw bytes, creation timing, REST relay, UI refresh, MCP count, and authority denial; then gate fast and full.",
      "expected": "StrategyProjectWorkspaceV1, sync, sync-all, recover, one read-only REST projection, one bounded refresh route, and the existing project view materialize hash-only reference indexes under data/strategy-workspaces without changing authoritative identities. Publication uses immutable revision directories plus an atomically replaced current pointer so an interrupted sync cannot damage the last valid revision.",
      "rollback": "Revert code and generated test fixtures; owner-generated workspaces are disposable projections and authoritative records remain untouched.",
      "files": [
        "apps/alpha-cli/**",
        "apps/alpha-web/**",
        "tests/**",
        "docs/**",
        ".claude/rules/alpha-cli.md",
        ".claude/rules/alpha-web.md",
        "CLAUDE.md"
      ],
      "status": "pending"
    },
    {
      "title": "C3 close S7 deferrals and S8 common-projection acceptance",
      "verify": "Run ADR/plan truth checks plus the technical-event, crypto-crowding, and cross-sectional crypto acceptance fixtures through the common projection boundary; run bias and determinism gates.",
      "expected": "Every named third-party adapter is explicitly deferred for this release, and three acceptance studies prove projection reuse without new D2, promotion, execution, or dependency authority.",
      "rollback": "Revert acceptance fixtures and documentation only; retain existing research and crypto artifacts.",
      "files": [
        "packages/alpha-study/**",
        "tests/**",
        "docs/**",
        "CLAUDE.md"
      ],
      "status": "pending"
    },
    {
      "title": "C4 qualify owner storage and BTC/ETH core providers",
      "verify": "Run storage, storage-inventory, full storage-verify, bounded profile run/resume, qualification, asset-master, snapshot, feature, comparison, redacted provider checks, and scoped network tests with exact command outputs captured.",
      "expected": "The reviewed Expansion UUID, reserve, external/internal boundary, immutable rehash, and exact Binance/Bybit/CoinGecko/Coin Metrics/GeckoTerminal BTC/ETH identities plus Coinbase comparison pass freshly; any missing access, credential, rate limit, family, or byte remains a release blocker.",
      "rollback": "Do not delete or rewrite immutable data; failed acquisitions remain honest non-evidence and resumable batches retain their checkpoints.",
      "files": [
        "data/crypto/**",
        "docs/audit/**"
      ],
      "status": "pending"
    },
    {
      "title": "C5 execute isolated deterministic and provider-backed owner journeys",
      "verify": "Run the golden research-to-workspace lifecycle in an isolated data directory, a provider-backed BTC/ETH case only to its mechanically supported state, standalone crypto sandbox separation tests, and a visible six-area Workstation walkthrough; owner performs fresh Touch ID ceremonies.",
      "expected": "Lifecycle evidence is complete and honest, unsupported/inconclusive outcomes are preserved, sandbox creates no broker/order authority, and all owner-facing recovery guidance is usable.",
      "rollback": "Remove only isolated acceptance data; never alter the two owner projects or manufacture decision/promotion evidence.",
      "files": [
        "tests/integration/**",
        "docs/audit/**"
      ],
      "status": "pending"
    },
    {
      "title": "C6 regenerate, review, publish, and post-merge smoke",
      "verify": "Run the canonical full gate, bias guards, frontend gate, literature and Qlib worker gates, live scoped acceptance, harness doctor, Atlas check, secret scan, Git integrity/diff checks, independent review, exact-SHA GitHub checks, and post-merge CLI/Workstation/workspace/storage/provider smokes.",
      "expected": "All generated surfaces and current-state documents are fresh, zero release blockers remain, the reviewed branch is merged to main, and main has a fresh exact-tree full-gate stamp while paper/broker remain disabled.",
      "rollback": "Do not merge on a failed gate or review; if post-merge smoke fails, record the exact blocker and use a forward fix rather than rewriting owner data.",
      "files": [
        "docs/**",
        "apps/alpha-web/frontend/**",
        "CLAUDE.md"
      ],
      "status": "pending"
    }
  ],
  "tier_impact": [
    "risk",
    "protected",
    "dag",
    "bias",
    "determinism"
  ],
  "docs_to_update": [
    "docs/superpowers/plans/2026-08-30-crypto-operational-readiness.md",
    "docs/superpowers/plans/2026-08-21-generic-study-composition.md",
    "docs/adr/0035-generic-study-composition-and-external-capability-adapters.md",
    "docs/governance/2026-07-19-post-v2-risk-register.md",
    "docs/ARCHITECTURE.md",
    "docs/BUILD-STATUS.md",
    "docs/atlas/**",
    "CLAUDE.md"
  ],
  "out_of_scope": [
    "Live-capital, exchange-testnet, or broker order routing of any kind",
    "IBKR Paper operational readiness or any broker-paper action",
    "Commercial hosting, distribution, sale, multi-user, or remote-service readiness",
    "Exhaustive completion of the content-addressed breadth profile (the latest frozen profile at program freeze has 7,603 tasks)",
    "New third-party adapters or dependencies",
    "Deleting the two demo projects, immutable history, failed acquisitions, or recoverable evidence",
    "Changing execution fingerprints, run IDs, SQLite authority, research-gate semantics, or the 62-tool MCP surface"
  ],
  "files": [
    "packages/alpha-study/**",
    "apps/alpha-cli/**",
    "apps/alpha-web/**",
    "tests/**",
    "docs/**",
    "CLAUDE.md"
  ]
}
```

## Scoped readiness reconciliation

This table reconciles the roadmap and current-state claims that can affect this release. Historical
delivery evidence remains immutable; a row marked complete is an implemented baseline, not a claim
that its live environment is still healthy.

| Scope item | Classification at program freeze | Closure rule |
|---|---|---|
| Research-first R1-R6 and repair Stages 0-5 | Complete baseline | Preserve existing authority and rerun acceptance. |
| Repair Stage 6 | Complete current baseline | `CLAUDE.md` is current and says the seven-stage program is implemented; the older BUILD-STATUS Stage-6-pending sentence is retained as a dated historical checkpoint, not current authority. |
| Generic-study S0-S5b | Complete baseline on unpublished branch | Review with the remaining study work before publication. |
| Generic-study S5c and S6 | Release-blocking | Finish server projection and existing-screen presentation; D1 stays CLI-only. |
| Generic-study S7 adapter candidates | Explicitly deferred | No adoption; a future candidate still requires an ADR-0011 packet. |
| Generic-study S8 | Release-blocking | Accept technical-event, crypto-crowding, and cross-sectional crypto cases through one projection boundary. |
| Crypto Data House Stages 0-6 | Complete baseline | Fresh storage/provider/core-universe evidence is still required. |
| Crypto Data House Stage 7 publication/owner pilot | Release-blocking | Exact-tree UI, live, replay, tamper, documentation, CI, and owner evidence must close. |
| Strategy project workspaces | Release-blocking | Add deterministic non-authoritative projection and backfill both existing projects. |
| R-59 through R-62 identity/unit/DEX/immutability controls | Complete baseline, reverify | Focused offline and BTC/ETH live evidence must remain green. |
| R-63 storage substitution/capacity/interruption | Release-blocking | Current Expansion access failure must be resolved; then full rehash and resume evidence must pass. |
| R-64 provider drift/rate limits | Release-blocking | Fresh redacted provider receipts and scoped live tests decide current state. |
| R-65 crypto crowding research validity | Release-blocking | Common-projection acceptance plus PIT/future-poison evidence. |
| R-66 hedged-basis sandbox separation | Release-blocking | Standalone acceptance must prove no paper, broker, or order authority. |
| R-43 through R-48 broker-paper operations | Explicitly deferred | Paper/broker remain disabled and pending after this release. |
| R-49 full QuantPad/archive breadth | Operational backlog | Continue governed checkpoint/resume/verify; it does not block BTC/ETH core readiness. |
| Content-addressed default breadth profile | Operational backlog | The latest profile `584cf038…b7bda8c` has 7,603 tasks; older 7,602-task profile `79f1c9d5…ee83a` remains immutable. Bounded cadence continues without a false completeness claim. |
| Live capital, hosting, distribution, multi-user | Explicitly deferred | Requires separate owner decision, ADR, and threat/risk review. |

## Authority freeze

- The only release meaning of “ready” is private-local research and non-transmitting sandbox use.
- Generated strategy workspaces contain references and hashes only. SQLite, immutable manifests,
  snapshots, runs, and research artifacts remain authoritative.
- The workspace command contract is exactly `alpha project workspace sync PROJECT_ID --json`,
  `alpha project workspace sync-all --json`, and
  `alpha project workspace recover PROJECT_ID --json`. A project-creation transaction commits
  before best-effort initial materialization; a projection failure never rolls back authority.
- Workspace publication writes a complete immutable revision below
  `data/strategy-workspaces/<project-slug>--<project-id>/revisions/<workspace-hash>/` and only then
  atomically replaces a small content-bound `current.json` pointer. Recovery may repoint only to a
  fully reverified revision and never repairs or overwrites tampered generated bytes in place.
- Browser refresh actions may invoke only the closed workspace synchronization operation. Semantic
  owner actions continue through fresh Touch ID; D1 launch remains owner-CLI-only.
- The semantic CLI/GET envelope remains the frozen exact seven-key S5a contract. S5b owner state
  and S6 D1 linkage are additive fields on the existing authoritative research-status projection,
  whose persisted semantic records are fully reverified before presentation.
- MCP remains pinned at 62 tools and gains no workspace mutation, semantic mutation, D1, D2,
  promotion, paper, broker, or order capability.
- Provider-native venue, market type, contract, quote, unit, cadence, and PIT clocks never collapse
  into a universal crypto identity or price.
