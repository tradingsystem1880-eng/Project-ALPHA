# alpha-eval benchmark summary

- suite sha256 `66689f6091dfb98c` · scorer `5a8adfa2e9a3dab5` · workspace ref `` · judge `gpt-6-astra`

## SUT `codex:gpt-6-astra`

- trials 1 (valid 1, harness-invalid 0, ungraded 0); cost $None
- **pass^1 1.0** · critical rate 0.0 (Wilson (0.0, 0.793))
- false-edge endorsement 0/0 · real edge rejected 0/0
- pitfalls {} · next steps {}
- judge verdict agreement None · dimension disagreements ≥2: 0 · grading failures {}

| tier | scenarios | pass^1 |
|---|---|---|
| atomic | 1 | 1.0 |

| dimension | mean | 95% CI | n |
|---|---|---|---|
| market_knowledge | 2.0 | [2.0, 2.0] | 1 |
| evidence_use | 3.0 | [3.0, 3.0] | 1 |
| tool_selection | 4.0 | [4.0, 4.0] | 1 |

| scenario | pass | outcomes | verdicts | failed core checks | criticals |
|---|---|---|---|---|---|
| A04-candles | 1/1 | pass | none |  |  |

