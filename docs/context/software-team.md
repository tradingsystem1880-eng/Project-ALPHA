# Software Team area map

Entry point: [context index](README.md). Existing manuals, rules and decisions retain authority.
All rows inherit the index's last source-inspected commit; no linked test is claimed executed.
This is an engineering navigation map, not a new team structure or operating policy.

## Capability routes

| Capability | Research rationale | Decisions | Plan | Code and representative checks |
|---|---|---|---|---|
| Architecture and change workflow | [Engineering research](../../research/07-architecture-ai-workflow.md), historical rationale | [Layered DAG](../adr/0001-strict-layered-dag.md); [sole composer](../adr/0002-cli-sole-composer-subprocess-surfaces.md); [agent-neutral engineering](../adr/0037-agent-neutral-research-engineering.md) | [Reproducible research delivery](../superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md) | [Import contracts](../../pyproject.toml); [component gate](../../scripts/gate_components.py); [awareness checks](../../tests/unit/test_repo_awareness_drift.py) |
| Context discovery and change impact | Dedicated research report: none identified; use the linked design | [Agent-neutral engineering](../adr/0037-agent-neutral-research-engineering.md); dedicated Atlas ADR: none identified | [Atlas design](../superpowers/plans/2026-08-20-project-alpha-atlas-design.md) | [Orientation adapter](../../scripts/repo_orientation.py); [shared source index](../../tools/alpha-atlas/src/alpha_atlas/developer_index.py); [Atlas consistency](../../tests/unit/test_atlas_consistency.py) |
| Verification and process ownership | Dedicated research report: none identified | [Engineering authority](../adr/0037-agent-neutral-research-engineering.md); dedicated cloud ADR: none identified | [Cloud setup](../superpowers/plans/2026-10-15-cloud-setup.md); [owned processes](../superpowers/plans/2026-10-15-cloud-readiness-owned-processes.md) | [Gate](../../scripts/gate.py); [test-process owner](../../scripts/run_owned_test.py); [setup entrypoint](../../scripts/cloud_setup.sh); [setup checks](../../tests/unit/test_cloud_setup.py) |

## Working boundaries

Use the [development loop](../operations/development-loop.md) and the applicable
[feature workflow](../../.agents/skills/alpha-feature-workflow/SKILL.md).
For review, use [code review and quality](../../.agents/skills/code-review-and-quality/SKILL.md)
and [verification before completion](../../.agents/skills/verification-before-completion/SKILL.md).
Follow the task's authorized scope; a navigation command does not authorize installation,
publication, owner actions or broad test execution.

The [canonical gate](../../scripts/gate_components.py) requires backend, frontend,
literature, Qlib, Atlas and eval receipts on one unchanged tree for full acceptance.
Focused checks are scoped evidence; they do not substitute for that receipt.
Read [cloud lifecycle guidance](../../README.md) before relying on prepared dependencies.
A configured cache path or saved installation recipe does not prove assets exist in a fresh task.
Provisioning failures remain failures until verified after an authorized environment correction.

## Reuse the existing index

[Atlas definitions](../../architecture/atlas/definitions/) retain curated purposes,
limits, safe-change notes and provenance. [Generated maps](../atlas/system-map.md)
remain generated, and [Atlas's README](../../tools/alpha-atlas/README.md) explains freshness.
Use the shared source index for package/module discovery; do not maintain another module list.
The context index links research and plans that the current ADR/spec extractor does not ingest.

## Verification status and gaps

This map records source inspection only. Existing documentation consistency tests are linked
above; actual checks of this draft must be reported separately with commands and exits.
No fresh full/component receipt, private-suite result, runtime readiness, or provider acceptance
is asserted here. Missing dedicated research/ADRs in the table are navigation gaps, not requests
to create decisions retroactively. The external archive's [intake status](README.md#external-research-intake)
is separate from these tracked sources.
