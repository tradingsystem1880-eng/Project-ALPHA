# ALPHA Quant Platform area map

**ALPHA Quant Platform** is the user-adopted platform name. This navigation label does not
expand the existing private, local scope or grant research, paper, broker or order authority.
Start with the [context index](README.md), [architecture](../ARCHITECTURE.md) and
[capability authority matrix](../governance/capability-authority-matrix.md).
All capability rows inherit the index's last source-inspected commit.

## Capability routes

Research reports are historical rationale; current contracts, source and receipts determine
behavior. Each test link identifies a verification location, not a test executed for this map.

| Capability | Research rationale | Decisions | Plan/spec | Code and representative checks |
|---|---|---|---|---|
| Data lineage and point-in-time access | [Market data](../../research/01-free-market-data.md); [storage](../../research/02-storage-layer.md) | [Two clocks](../adr/0004-two-clock-corporate-actions.md); [PIT firewall](../adr/0005-point-in-time-firewall.md); [family authority](../adr/0032-governed-crypto-data-house.md) | [Daily-data hardening spec](../superpowers/specs/2026-08-03-daily-data-ibkr-paper-hardening.md) | [Data package](../../packages/alpha-data/); [data rules/module map](../../.claude/rules/alpha-data.md); [availability guard](../../tests/bias_guards/test_defillama_availability.py), scoped to DefiLlama |
| Governed research and study composition | [Synthesis](../../research/00-SYNTHESIS.md), historical starting point; dedicated study research report: none identified | [Research cases](../adr/0019-governed-research-cases-before-strategy-development.md); [D1 admission](../adr/0025-empirical-d1-research-runner-admission.md); [D2 authority](../adr/0026-d2-confirmation-readiness-gate-promotion-override.md); [study boundary](../adr/0035-generic-study-composition-and-external-capability-adapters.md) | [Research Scientist spec](../superpowers/specs/2026-08-06-research-scientist-program-design.md); [study plan](../superpowers/plans/2026-08-21-generic-study-composition.md) | [Research CLI](../../apps/alpha-cli/src/alpha_cli/research_cmds.py); [control store](../../apps/alpha-cli/src/alpha_cli/control_store.py); [study package](../../packages/alpha-study/); [gate watermark checks](../../tests/integration/test_research_gate_watermark_cli.py); [study authority checks](../../tests/unit/study/test_authority.py) |
| Backtesting and statistical validation | [Engine research](../../research/03-backtesting-engine.md); [statistical research](../../research/04-statistical-validation.md) | [t+1 fills](../adr/0003-t+1-fill-encoding.md); [null model](../adr/0006-two-tier-null-model.md); [run identity](../adr/0013-run-identity-v3-and-causal-artifacts.md); [four-family path risk](../adr/0029-four-family-monte-carlo-validation.md) | [Four-family validation spec](../superpowers/specs/2026-08-12-four-family-monte-carlo-validation.md) | [Engine package](../../packages/alpha-backtest/); [validation package](../../packages/alpha-validation/); [gauntlet composition](../../apps/alpha-cli/src/alpha_cli/_gauntlet.py); [null-model integration checks](../../tests/integration/test_gauntlet_null_model.py) |
| Model candidates and isolated workers | [Strategy/ML research](../../research/06-strategy-encoding-ml.md) | [Forecast facade](../adr/0008-vendored-kronos-and-alpha-forecast-layer.md); [Qlib isolation](../adr/0016-isolated-qlib-worker.md); [candidate governance](../adr/0028-governed-market-state-and-model-candidates.md) | [Qlib worker spec](../superpowers/specs/2026-07-19-workstation-v3-qlib-worker-design.md) | [Forecast package](../../packages/alpha-forecast/); [Qlib worker and checks](../../workers/qlib/README.md); [forecast module map](../../.claude/rules/alpha-forecast.md); dedicated cross-candidate test: none identified in this inspection |
| Workstation and advisory investigations | [Engineering research](../../research/07-architecture-ai-workflow.md), general rationale; dedicated investigation research report: none identified | [Collaboration boundary](../adr/0022-codex-collaboration-surface.md); [local confirmation](../adr/0038-local-confirmation-and-terminal-archive-charts.md) | [Workstation investigations plan](../superpowers/plans/2026-10-04-workstation-investigations.md) | [Web module map](../../.claude/rules/alpha-web.md); [frontend guide](../../apps/alpha-web/frontend/README.md); [investigation runbook](../operations/codex-investigations.md); [real-backend journey](../../apps/alpha-web/frontend/e2e/real-backend.spec.ts) |
| Separately gated paper operations | [Feeds/paper research](../../research/05-paper-trading-feeds.md), historical rationale | [Operational sessions](../adr/0012-operational-paper-sessions.md); [data/broker boundary](../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md); [readiness](../adr/0031-provider-readiness-and-paper-acceptance-v2.md) | [Provider/paper spec](../superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md) | [CLI module map](../../.claude/rules/alpha-cli.md); [local operations runbook](../operations/README.md); dedicated paper-acceptance test/receipt: not selected or verified in this inspection |

## Trace the workflow without granting authority

Use the existing [research flow](../atlas/research-flow.md),
[curated lifecycle definitions](../../architecture/atlas/definitions/research-lifecycle.json)
and [data-lineage definitions](../../architecture/atlas/definitions/data-lineage.json).
Those definitions already carry `last_verified_commit` and provenance; this map does not
refresh their verification metadata or certify generated Atlas freshness.

The [research contracts](../operations/research-platform-contracts.md) and
[bounded workflow](../operations/bounded-research-workflow.md) explain operational constraints.
Research comes before strategy; D1 discovery and one-shot D2 remain governed admissions.
Study projections, model candidates, literature claims and advisory investigations confer no
empirical admission, promotion or execution authority. Path risk is not proof of edge.
For the purposes, assumptions and interpretation of all four retained Monte Carlo families,
read the [four-family Monte Carlo overview](../operations/monte-carlo/README.md).
Provider configuration is not data qualification; paper readiness remains separately gated.

## Historical and external evidence

The [June synthesis](../../research/00-SYNTHESIS.md) contains dated recommendations and scope
assumptions. Read accepted ADRs, current contracts and source before treating any recommendation
as implemented. Plans can describe incomplete or superseded work; consult their status and
[delivery history](../BUILD-STATUS.md), then seek a matching current receipt.

The October 14 archive's 46 files and 296 links are privately verified, but public intake is
pending and the corpus is not in GitHub. See the [intake boundary](README.md#external-research-intake).
This map imports no private archive contents or links and establishes no archive-to-code mapping.

## Verification status and remaining gaps

Last source inspection is recorded in the [index](README.md#source-inspection-and-executed-evidence).
No capability test, live provider check, browser journey or full gate is claimed passed by this map.
Selected checks are representative, not exhaustive capability coverage. Missing research, decision,
plan or test relationships must stay visible until inspected evidence supports a link.
Runtime/provider/private-suite acceptance and fresh aggregate receipts remain separate work.
