# ALPHA context index

Navigation for Software Team and the user-adopted **ALPHA Quant Platform** name.
These maps introduce no product scope, permissions, or new source of authority.

- [Software Team](software-team.md): engineering boundaries, discovery and verification.
- [ALPHA Quant Platform](alpha-quant-platform.md): data, research, validation and surfaces.
- [Foundation status baseline (2026-10-18)](../BUILD-STATUS.md#2026-10-18-foundation-status): verified deliveries, pending evidence and deferred scope; see later dated updates for new checks.
- [Mac handover update (2026-10-19)](../BUILD-STATUS.md#2026-10-19-mac-handover-update): current bounded workstation evidence and remaining physical handover blockers.
- [Mac workstation handover refresh](../operations/mac-workstation-handover-2026-10-19.md): bounded startup/UI evidence and the remaining physical handover blockers.
- [Evidence and recovery](../operations/development-loop.md#evidence-and-recovery): preflight, preservation, retries and authorization.
- [Cleanup execution retrospective](../operations/retrospectives/2026-10-17-cleanup-execution.md): dated incidents and evidence limits.
- [Context ownership and test-layout pilot](../superpowers/plans/2026-10-16-context-ownership-and-test-layout-pilot.md): context stewardship/retrieval ([PR68](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/68)), unavailable-reference annotation ([PR69](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/69)) and bounded semantic-payload test isolation ([PR71](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/71)) are delivered; broader cleanup remains pending.

## Read authority before capability

Start with [AGENTS.md](../../AGENTS.md) and the authoritative operating manual
[CLAUDE.md](../../CLAUDE.md), then applicable [path rules](../../.claude/rules/).
The [capability authority matrix](../governance/capability-authority-matrix.md)
owns surface permissions and the distinction between stored, configured, verified,
qualified, research evidence, paper readiness and execution authority.
The [architecture](../ARCHITECTURE.md) maps current boundaries; the
[ADR index](../adr/README.md) records decisions and supersession.
Specs/plans record dated intent; [build history](../BUILD-STATUS.md) records delivery.
Neither a research recommendation nor a dated completed plan proves current behavior.

## Stewardship and retrieval

Use the existing [artifact ownership roles](../superpowers/plans/2026-10-16-context-ownership-and-test-layout-pilot.md#scope-and-ownership).
The operating manual/rules and authority matrix retain permissions; ADRs retain decisions;
dated specs/plans and build history retain intent and delivery. Atlas retains generated discovery.
When changing a capability, its source/document steward checks the corresponding map row and
records missing relationships. Navigation stewardship maintains these links and inspection evidence;
it cannot approve the capability, change domain authority or promote a dated plan into evidence.

Each route below takes one hop to the named area-map row and one to a linked destination.
Representative checks identify bounded verification locations, not complete capability coverage.

| Retrieval task | Area-map row | Relationship limits |
|---|---|---|
| CLI change boundary | [Software Team: Architecture and change workflow](software-team.md#capability-routes) | Sole composer, rules, composition source and public seam checks; engineering delivery plan is context, not a dedicated CLI-boundary spec. |
| New data-family boundary | [Quant Platform: Data lineage and point-in-time access](alpha-quant-platform.md#capability-routes) | Family authority and provider-design amendment; contract checks do not prove new-provider acceptance. |
| D2 authority | [Quant Platform: Governed research and study composition](alpha-quant-platform.md#capability-routes) | D2 decision, confirmation plan, store/executor and mechanical-classification checks; owner approval remains required. |
| Randomized-price null | [Quant Platform: Backtesting and statistical validation](alpha-quant-platform.md#capability-routes) | Null ADR, composition and selection/tier checks; dedicated null plan/spec not identified. Four-family path risk remains separate. |
| Cloud readiness | [Software Team: Verification and process ownership](software-team.md#capability-routes) | Setup/process plans, entrypoint and mocked checks; dedicated cloud ADR not identified. No environment-readiness claim. |
| Current full-gate rule | [Software Team: Verification and process ownership](software-team.md#capability-routes) | Manual, component runner and frozen-receipt checks; the delivered engineering plan is historical context, not a current passing receipt. |

## Source inspection and executed evidence

Last source inspection for these maps: commit
`dd5a924d709b8d60c97492043f2a82dac976105a` (2026-10-16).
This identifies the inspected base, not a passing test run or a commit containing this draft.
Each capability row inherits that inspection reference; linked tests are representative
verification locations, not executed evidence. Missing relationships remain explicit.
Protected test targets are checked by path/Git metadata only; their content was not inspected.
Executed checks require their own command, exit, scope and tested-tree receipt.
A receipt from another tree or environment does not certify this draft.

[Atlas](../../tools/alpha-atlas/README.md) supplies the existing provenance model:
`owner`, `created_from`, `last_verified_commit`, source anchors and computed evidence levels.
Its `tested` level is not a fresh aggregate-gate pass. Preserve generated outputs;
changed anchors require re-verification rather than an updated date alone.
Atlas's documentation extractor currently covers ADRs and specs; these maps link research
and plans directly without claiming they have been added to the generated graph.

## Recheck a changed context row

Review the three context pages' local file/directory links and Markdown heading fragments.
For each capability row's linked implementation/check file, confirm it exists at the inspected
commit and compare it to the current tree with existing Git metadata commands, for example:

```sh
git cat-file -e dd5a924d709b8d60c97492043f2a82dac976105a^{commit}
git cat-file -e dd5a924d709b8d60c97492043f2a82dac976105a:apps/alpha-cli/src/alpha_cli/_gauntlet.py
git diff --name-only dd5a924d709b8d60c97492043f2a82dac976105a -- apps/alpha-cli/src/alpha_cli/_gauntlet.py
```

Repeat for the affected row's file anchors, including staged and unstaged changes. Directory
links locate packages; they do not certify every descendant. A missing commit/target, broken
heading or changed file requires review and renewed inspection evidence. Do not advance the
inspection date or commit merely to hide drift. Protected targets permit existence/Git metadata
checks only; never open their contents or add fragments that require a content read.

These are scoped navigation checks, not a new persistent gate. Valid links and unchanged bytes
establish syntactic freshness only: they cannot establish that a claim is correct, a test is
adequate, a provider is ready or a check passed. Review public source against existing decisions
and record semantic gaps separately. Reuse Atlas's documented `generate --check` through the
existing authorized gate for its own inputs; do not edit generated outputs or ingest these maps
into a second graph. Keep scoped check scripts/results with the task's private recovery evidence;
full acceptance still requires the unchanged canonical gate on the exact candidate tree.

## Retrieve narrowly

From the repository root, use the existing interfaces when authorized:

```sh
uv run python scripts/gate.py orient
alpha info commands --all --json
alpha info procedures --json
```

These are discovery commands, not permission to execute an operational procedure.
Follow a capability's research → decision → plan → source/test links; consult the
relevant package rule for symbol detail instead of copying module inventories here.

## External research intake

The October 14 research archive has **46 files and 296 links privately verified**,
as reported for this draft. Public privacy/provenance intake remains pending;
the corpus is **not in GitHub**. The private verification was not repeated in this checkout.
No private chat URLs, personal quotations, archive contents or sensitive details belong here.

Before public intake, retain a private hash inventory and reconcile duplicates, conflicts,
source dates, authorship and supersession against tracked research and decisions.
Check credentials, identifiers, private conversations, metadata, owner data and hidden tests.
Verify licenses, redistribution rights, source attribution and quotation permissions;
private retention permission does not establish public redistribution rights.
Publish only explicitly authorized, sanitized derivatives with their own provenance.
Private verification alone grants neither public intake nor research/execution authority.
