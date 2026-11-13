# Software Team area map

Entry point: [context index](README.md). Existing manuals, rules and decisions retain authority.
All rows inherit the index's last source-inspected commit; no linked test is claimed executed.
This is an engineering navigation map, not a new team structure or operating policy.

## Capability routes

| Capability | Research rationale | Decisions | Plan | Code and representative checks |
|---|---|---|---|---|
| Architecture and change workflow | [Engineering research](../../../research/07-architecture-ai-workflow.md), historical rationale | [Layered DAG](../../adr/0001-strict-layered-dag.md); [sole composer](../../adr/0002-cli-sole-composer-subprocess-surfaces.md); [agent-neutral engineering](../../adr/0037-agent-neutral-research-engineering.md) | [Reproducible research delivery](../../superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md) | [Import contracts](../../../pyproject.toml); [component gate](../../../scripts/gate_components.py); [engineering awareness checks](../../../tests/unit/test_repo_awareness_drift.py); [CLI rules/module map](../../../.claude/rules/alpha-cli.md); [engine composition](../../../apps/alpha-cli/src/alpha_cli/_runner.py); [gauntlet composition](../../../apps/alpha-cli/src/alpha_cli/_gauntlet.py); [lightweight public seam checks](../../../tests/unit/test_public_seams.py), not complete DAG enforcement. Dedicated current CLI-boundary spec: not identified |
| Context discovery and change impact | Dedicated research report: none identified | [One file system](../../adr/0040-one-file-system-atlas-retired.md); [agent-neutral engineering](../../adr/0037-agent-neutral-research-engineering.md) | None (follow-up file-system restructure planned) | [File-system command](../../../scripts/fs.py); [orientation](../../../scripts/fs_orient.py); [document search](../../../scripts/fs_search.py); [orientation checks](../../../tests/unit/test_fs_orient.py); [search checks](../../../tests/unit/test_fs_search.py) |
| Verification and process ownership | Dedicated research report: none identified | [Engineering authority](../../adr/0037-agent-neutral-research-engineering.md); dedicated cloud ADR: none identified | [Cloud setup](../../superpowers/plans/archive/2026-10/2026-10-15-cloud-setup.md); [owned processes](../../superpowers/plans/archive/2026-10/2026-10-15-cloud-readiness-owned-processes.md); [engineering delivery](../../superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md), historical full-gate context | [Gate](../../../scripts/gate.py); [test-process owner](../../../scripts/run_owned_test.py); [setup entrypoint](../../../scripts/cloud_setup.sh); [mocked setup checks](../../../tests/unit/test_cloud_setup.py); [component runner](../../../scripts/gate_components.py); [component checks](../../../tests/unit/test_gate_components.py). Current rule: [CI is the merge gate](../../adr/0039-ci-is-the-merge-gate.md) |

## Working boundaries

Use the [development loop](../../operations/development-loop.md) and the applicable
[feature workflow](../../../.agents/skills/alpha-feature-workflow/SKILL.md).
For review, use [code review and quality](../../../.agents/skills/code-review-and-quality/SKILL.md)
and [verification before completion](../../../.agents/skills/verification-before-completion/SKILL.md).
Follow the task's authorized scope; a navigation command does not authorize installation,
publication, owner actions or broad test execution.

CI on the pull request runs the [component definitions](../../../scripts/gate_components.py)
(backend, frontend, literature, Qlib, eval) and is the merge gate. Local checks are
feedback; they do not substitute for CI.
Read [cloud lifecycle guidance](../../../README.md) before relying on prepared dependencies.
A configured cache path or saved installation recipe does not prove assets exist in a fresh task.
Provisioning failures remain failures until verified after an authorized environment correction.

## Reuse the existing index

Use `uv run python scripts/fs.py orient` (optionally `--component NAME`) for package and module
discovery; it is computed from the tree, so do not maintain another module list. Use
`uv run python scripts/fs.py search "QUERY"` to find the owning document for a topic.

## Verification status and gaps

This map records source inspection only. Existing documentation consistency tests are linked
above; actual checks of this draft must be reported separately with commands and exits.
No fresh full/component receipt, private-suite result, runtime readiness, or provider acceptance
is asserted here. Missing dedicated research/ADRs in the table are navigation gaps, not requests
to create decisions retroactively. The external archive's [intake status](README.md#external-research-intake)
is separate from these tracked sources.
