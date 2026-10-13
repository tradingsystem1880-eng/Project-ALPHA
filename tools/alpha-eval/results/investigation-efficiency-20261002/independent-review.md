# Independent retained-evidence review

Reviewer: separate read-only Codex agent `efficiency_review`, 2026-10-02.
Disposition: no critical factual, causal or integrity regression observed in nine retained outputs.
This is qualitative review of designed development cases, not a general reliability score.

The reviewer independently recomputed panel hashes, drawdown/benchmark/recovery, cash identity
residuals and conditional means from exported rows. All cited receipts agree. All 22 transport
usage records match raw `turn.completed` events.

- Conditional: all modes report the measured facts correctly, qualify the indicator association,
  and identify missing attribution/timing evidence. Prechecked does not infer episode overlap
  merely from matching observation counts.
- Indicator-null: all modes recognize nearly identical means without claiming the indicator is
  conclusively useless. Exposure attribution and tail-risk proposals are relevant. Prechecked
  explicitly justifies skipping historical notes.
- Accounting defect: all modes stop interpretation after the identity error of 10.0, request
  reconciliation, and do not claim the defect explains the entire drawdown. Only inspection runs.

| Case directory | Legacy | Prechecked | Fixed |
|---|---|---|---|
| 6929adae851d (conditional) | c49fea7425fa | ef1c0948cc63 | 992a93455c71 |
| 840c532e4cc9 (indicator-null) | c49fea7425fa | ef1c0948cc63 | 992a93455c71 |
| f087203adbae (accounting defect) | c49fea7425fa | ef1c0948cc63 | 992a93455c71 |

Paths identify case/trial directories inside the retained archive. In valid trials, attempt-1
is inspection and attempt-2 is loss measurement. Legacy/prechecked attempt-3 is conditional;
legacy attempt-4 is historical context. Fixed attempt-3 is context and attempt-4 is conditional.
Defect trials cite only attempt-1. Full conclusions and next tests are in report.md.

Verified totals: legacy 12 calls / 127832 input tokens; prechecked 7 / 74126; fixed 3 / 32425.
Prechecked meets the frozen 15% input-token target at 42.01% reduction, conditional on usable
finals and this review. Fixed reduces input by 74.63%. No independent quality score is invented.

Savings combine inspection, compaction and early stopping; contributions are not isolated.
Cache and service timing vary; token totals are not billing estimates. Fixed collection is
controller work, not model initiative. Single observations do not establish general superiority.
Real execution reconciliation, causal attribution and untouched predictive validation remain absent.
