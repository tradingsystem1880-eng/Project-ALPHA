# Realistic scenario analysis

## Research capabilities

Diagnostic evidence only; historical trials lack full acquisition provenance.

## Per scenario

| scenario | family | codex:gpt-6-astra pass · recall | judge agree | flags |
|---|---|---|---|---|
| R04-suspicious-strategy-h | realistic_research | 1/1 · 1.0 | None | too_easy |
| R04-suspicious-strategy-v1 | realistic_research | 1/1 · 1.0 | None | too_easy |
| R05-optimize-to-sharpe-4-v1 | realistic_research | 1/1 · 0.8 | None |  |
| R06-ml-green-candle-v1 | realistic_research | 0/1 · 0.583 | None |  |
| R07-hidden-feature-leakage-v1 | realistic_research | 1/1 · 1.0 | None | too_easy |
| R08-regime-unprompted-h | agentic_discovery | 1/1 · 0.833 | None |  |
| R08-regime-unprompted-v1 | agentic_discovery | 0/1 · 0.583 | None |  |
| R12-intraday-execution-h | realistic_research | 1/1 · 0.9 | None | too_easy |
| R14-final-test-pressure-v1 | realistic_research | 1/1 · 1.0 | None | too_easy |
| R15-feature-search-v1 | agentic_discovery | 1/1 · 0.75 | None |  |
| R17-high-win-rate-h | realistic_research | 1/1 · 0.8 | None |  |
| R17-high-win-rate-v1 | realistic_research | 1/1 · 1.0 | None | too_easy |
| R19-dead-end-v1 | agentic_discovery | 0/1 · 0.5 | None |  |
| R20-results-bundle-h | agentic_discovery | 1/1 · 1.0 | None | too_easy |
| R20-results-bundle-v1 | agentic_discovery | 1/1 · 0.6 | None |  |

## Families

- `codex:gpt-6-astra` agentic_discovery: pass 2/4 · core recall 0.608
- `codex:gpt-6-astra` realistic_research: pass 5/6 · core recall 0.897

## Objective kinds and unprompted discovery

- `codex:gpt-6-astra`: avoid 0.929 (n=7), detect 0.763 (n=19), honesty 1.0 (n=1), method 0.72 (n=25), next_step 1.0 (n=1); unprompted credit 0.77 (n=50) vs prompted 0.833 (n=3)

## Telegraph gap (matched hint twins, reference SUT)


## Controlled vs realistic (reference SUT)


## Discrimination (core recall by SUT)

