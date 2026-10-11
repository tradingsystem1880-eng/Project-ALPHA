# Bounded controller evidence — 2026-09-30

This is a deterministic CLI smoke test, not a fresh agent trial or model ranking. New model calls: zero. Historical Claude/Codex trials and judgments were not rewritten.

The controller used a separate copy of the retained immutable `realdesk-2026` snapshot, ORCA, cutoff 2022-10-17, the fixed momentum configuration, and a 900-second dispatch budget. Its baseline completed in 2.10 seconds and validation in 5.78 seconds on this local run. These timings exclude preflight/reconciliation and are not a controlled speedup estimate against prior agent conversations.

| Evidence | Baseline | Validation |
|---|---:|---:|
| Equity observations, including initial value |1440|883|
| Expected observations from snapshot/splitter |1440|883|
| Fill events |21|3|
| Denied/rejected orders |0|4|
| Closed trades |1|1|
| Validation result |Not applicable|FAIL|

The actual validation measurement ends 2022-08-09 because the existing splitter drops the incomplete trailing test block; the requested knowledge cutoff remains 2022-10-17. These populations are separate and must not be added together. A negative validation is completed evidence, not an admission or a reason to tune.

`controller-plan.json` binds snapshot, source implementation and runtime fingerprints. `controller-receipt.json` includes both digests and exact run IDs. `controller-manifest.json` binds the original local attempt records, logs and receipt; raw paths remain in the external smoke directory recorded by `evidence-index.json`. Identical-plan replay returned the same receipt and all completion hashes were verified. `retained-execution-digest.json` independently reads the historical validation, recovering the same four denied orders.

No autonomous narrative, pressure-turn stopping, general strategy search or agent-wide temporal isolation was tested. R19 used a rules strategy, which this first momentum-only controller cannot execute; its benchmark failure remains unresolved. The next work should extend bounded typed operator coverage and enforce a physically restricted fresh agent data view before adding reviewers.
