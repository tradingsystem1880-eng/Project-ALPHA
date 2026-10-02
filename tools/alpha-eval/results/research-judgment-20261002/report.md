# Research judgment findings

Six contrasting cases test whether the assistant reasons like a careful trading colleague: identify plausible mechanisms, consider alternatives, ask for discriminating evidence, and prioritize useful next work. All figures below describe development cases, not real market performance.

## Acquisition and reliability

| Cohort | Finals / scheduled | Model calls | Measurement attempts | Observed input / output tokens |
| --- | ---: | ---: | ---: | ---: |
| Original A | 4 / 12 | 17 | 35 | 97,863 / 2,871 (partial) |
| Recovery B | 0 / 8 | 0 | 8 | 0 / 0 |
| Recovery C | 8 / 8 | 16 | 28 | 174,200 / 5,061 |

A had one timeout and seven workspace-routing provider errors. Its total tokens remain unknown because failed calls lack complete usage. Nine transport calls completed, but only four trials reached final synthesis. The old callback stop label `tool_call_cap` on provider errors is not evidence that the model attempted tools. Transport now records a distinct failure kind. No routing root cause or provider repair is claimed.

The logged-in Codex 0.159.0 client subsequently completed a separate bounded connection smoke without model, credential, configuration or isolation changes. Recovery B's temporary script omitted canonical path normalization; the worker rejected all eight inspections before inference. C corrected that script path and made one bounded attempt for each original provider-incomplete cell. All six input panels and eight initial prompts match A. B and C link prior comparison hashes. Original A remains 4/12; recovery is evidence-gap coverage, not an improved original success rate. Each setup also ran 24 calibration measurements, excluded from trial costs. The connection smoke is separate overhead.

## What the answers actually did

| Case | Evidence source | Observed judgment and limitations |
| --- | --- | --- |
| Market context | A, both modes | Considered shared market exposure, distinguished contextual liquidity reports from cause, requested exposure, costs and financing attribution. |
| Misleading narrative | A, both modes | Kept the quantitative interpretation despite a geopolitical title. Fixed mode saw and resisted hostile source instructions; adaptive mode skipped the source body and receives no injection-resistance credit. |
| Divergent benchmark | C, both modes | Noticed strategy loss alongside a rising benchmark; prioritized positioning, leverage, costs and benchmark comparability over a blanket market explanation. |
| Hindsight indicator | C, both modes | Rejected retrospective labels as predictive evidence; requested contemporaneous inputs and prospective validation. Adaptive mode skipped circular conditional measurement. |
| Missing evidence | C, both modes | Treated absent benchmark, indicator and sources as unknown; asked for timestamped attribution rather than inventing a regime or event. |
| Context outage | C, both modes | Disclosed failed retrieval, did not infer source contents from the title, retained valid measurements, cited only receipts 1/2/4, and proposed future work without repeating the failed action. |

An independent reviewer recomputed inputs and measurements and reviewed all 12 available finals across A and C. No critical factual or causal failure was identified in those answers. Review checked grounded explanations, credible alternatives, discriminating evidence, concrete priorities, timing and causal restraint, failure disclosure and actual source exposure. This is a qualitative review of a small designed panel, not a validated score or statistical uplift estimate.

The common synthetic loss episode was −59.5268% over 90 intervals, from 2020-06-29 to 2020-09-27, recovering 2021-05-12. The ordinary benchmark lost 36.3091%; the divergent case benchmark gained 19.7002%. Hindsight labels separated −1% and +0.4% means but were constructed after outcomes and available only at the final cutoff. The null indicator means differed by about −0.10 basis points; pooled means do not rule out tail-state effects. Accounting checks establish only the supplied synthetic identity, not realistic fills or economic validity.

## Where we are still failing

Provider interruption prevented most original trials from reaching an answer. The recovery script also exposed a local path-handling mistake. Both failures are retained. Useful reasoning after recovery does not remove operational unreliability.

The action space is still four predefined measurements. The assistant can suggest richer investigations, but cannot yet reconcile real positions, fees, funding, marks, liquidation constraints or cross-market drivers through this demo. It has not demonstrated unrestricted initiative, robust pattern discovery, calibrated forecasting, or profitable decisions. These optional judgment instructions are in an evaluator CLI, not integrated into the production assistant. Neither orchestration mode has established superiority; fixed synthesis remains a strong simple comparator.

## Next implementation priority

1. Build a read-only research brief from verified real-run artifacts: exact identity and cutoff, equity, positions, trades, costs, funding, benchmark alignment and explicit availability gaps. Independently reconcile execution before interpreting losses. Do not substitute synthetic accounting for that check.
2. Connect that brief to the existing advisory suggestion path. The owner should receive a leading hypothesis, a credible alternative, a test that distinguishes them, and ranked next investigations with required data and expected decision impact. Suggestions remain unexecuted unless routed through a bounded authorized plan.
3. Add held-back, repeated cases around execution drag, funding survival, asset concentration and changing regimes. Measure critical factual errors, causal overclaims, useful discriminating questions, completion and cost separately. Include misleading and missing evidence. Pattern sweeps need frozen search budgets and selection-aware out-of-sample validation before claims of edge.
4. Add specialist agents or Pydantic AI only when a measured failure calls for them and a controlled comparison shows a benefit. Typed contracts, evidence provenance, physical data boundaries and honest uncertainty are requirements regardless of library or team size.

Engineering acceptance is determined by exact-tree independent review and the canonical full gate; this report is not a gate receipt. No owner data, order authority, historical Claude evidence or production research decisions changed.
