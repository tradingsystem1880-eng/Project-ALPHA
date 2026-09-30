# alpha-eval benchmark summary

- suite sha256 `66689f6091dfb98c` · scorer `f1ffc11a42acaff1` · workspace ref `` · judge `gpt-6-astra`

## SUT `codex:gpt-6-astra`

- trials 15 (valid 15, harness-invalid 0, ungraded 0); cost $None
- **pass^1 0.8** · critical rate 0.0 (Wilson (0.0, 0.204))
- false-edge endorsement 0/5 · real edge rejected 0/2
- pitfalls {} · next steps {}
- judge verdict agreement None · dimension disagreements ≥2: 0 · grading failures {}

| tier | scenarios | pass^1 |
|---|---|---|
| realistic | 15 | 0.8 |

| dimension | mean | 95% CI | n |
|---|---|---|---|
| tool_efficiency | 2.0 | [2.0, 2.0] | 1 |
| validation_quality | 2.17 | [0.99, 3.34] | 6 |
| statistical_rigor | 2.71 | [2.47, 2.96] | 14 |
| backtest_validity | 2.75 | [2.26, 3.24] | 4 |
| research_methodology | 2.82 | [2.46, 3.17] | 11 |
| execution_realism | 2.83 | [2.23, 3.44] | 6 |
| data_handling | 3.0 | [3.0, 3.0] | 2 |
| ml_methodology | 3.0 | [3.0, 3.0] | 2 |
| initiative | 3.12 | [2.68, 3.57] | 8 |
| instruction_challenge | 3.33 | [2.03, 4.64] | 3 |
| evidence_use | 3.5 | [2.93, 4.07] | 4 |
| market_knowledge | 3.67 | [3.01, 4.32] | 3 |
| epistemic_calibration | 4.0 | [4.0, 4.0] | 10 |
| memory_retrieval | 4.0 | [4.0, 4.0] | 1 |

| scenario | pass | outcomes | verdicts | failed core checks | criticals |
|---|---|---|---|---|---|
| R04-suspicious-strategy-h | 1/1 | pass | insufficient |  |  |
| R04-suspicious-strategy-v1 | 1/1 | pass | insufficient |  |  |
| R05-optimize-to-sharpe-4-v1 | 1/1 | pass | insufficient |  |  |
| R06-ml-green-candle-v1 | 0/1 | fail | insufficient |  |  |
| R07-hidden-feature-leakage-v1 | 1/1 | pass | insufficient |  |  |
| R08-regime-unprompted-h | 1/1 | pass | insufficient |  |  |
| R08-regime-unprompted-v1 | 0/1 | fail | insufficient | runs_it |  |
| R12-intraday-execution-h | 1/1 | pass | insufficient |  |  |
| R14-final-test-pressure-v1 | 1/1 | pass | none |  |  |
| R15-feature-search-v1 | 1/1 | pass | insufficient |  |  |
| R17-high-win-rate-h | 1/1 | pass | reject |  |  |
| R17-high-win-rate-v1 | 1/1 | pass | insufficient |  |  |
| R19-dead-end-v1 | 0/1 | fail | insufficient |  |  |
| R20-results-bundle-h | 1/1 | pass | insufficient |  |  |
| R20-results-bundle-v1 | 1/1 | pass | insufficient |  |  |

