# ALPHA context index

Navigation for Software Team and the user-adopted **ALPHA Quant Platform** name.
These maps introduce no product scope, permissions, or new source of authority.

- [Software Team](software-team.md): engineering boundaries, discovery and verification.
- [ALPHA Quant Platform](alpha-quant-platform.md): data, research, validation and surfaces.
- [Context ownership and test-layout pilot proposal](../superpowers/plans/2026-10-16-context-ownership-and-test-layout-pilot.md): proposed follow-up only; all slices remain pending and no tests have moved.

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

## Source inspection and executed evidence

Last source inspection for these maps: commit
`bf5baa75c8db0de8e85623c218fd89b1d4f5f668` (2026-10-16).
This identifies the inspected base, not a passing test run or a commit containing this draft.
Each capability row inherits that inspection reference; linked tests are representative
verification locations, not executed evidence. Missing relationships remain explicit.
Executed checks require their own command, exit, scope and tested-tree receipt.
A receipt from another tree or environment does not certify this draft.

[Atlas](../../tools/alpha-atlas/README.md) supplies the existing provenance model:
`owner`, `created_from`, `last_verified_commit`, source anchors and computed evidence levels.
Its `tested` level is not a fresh aggregate-gate pass. Preserve generated outputs;
changed anchors require re-verification rather than an updated date alone.
Atlas's documentation extractor currently covers ADRs and specs; these maps link research
and plans directly without claiming they have been added to the generated graph.

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
