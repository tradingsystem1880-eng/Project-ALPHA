---
owner: invariants router
sources:
  - tests/unit/test_filesystem_contract.py
verified: 8115bbcdee4c05e0
---
# Invariants: which file to load
| file | owns | load when |
|---|---|---|
| [research-integrity.md](research-integrity.md) | project-wide honesty rules: point-in-time, fills, authority | any change to research, data or results |
| [engineering.md](engineering.md) | project-wide coding rules | writing or reviewing code |
| [documentation.md](documentation.md) | rules for documents under docs/ | adding or changing a document |
| [testing.md](testing.md) | test layout, markers, tiers, sweeps | adding or moving tests |
| [core.md](core.md) | alpha_core: domain values, errors, settings | editing alpha-core |
| [data.md](data.md), [data-freeze-before-replace.md](data-freeze-before-replace.md) | alpha_data: storage, snapshots, pull freeze | editing alpha-data |
| [data-crypto.md](data-crypto.md) | alpha_data crypto: storage, identity, offline Bybit context | editing crypto storage or identity |
| [data-context.md](data-context.md) | alpha_data context: macro series, SEC filings, derivatives | editing context data |
| [data-options.md](data-options.md) | alpha_data options: chain records, point-in-time store, fixture | editing options data |
| [data-free-sources.md](data-free-sources.md) | free data on the Dell and provider limits | adding or judging a free data source |
| [data-bar-timeframes.md](data-bar-timeframes.md) | bars of any timeframe in the store | touching bar timeframes |
| [crypto-providers.md](crypto-providers.md) | crypto provider modules and coverage profiles | editing crypto providers |
| [patterns.md](patterns.md) | alpha_patterns: pattern geometry, indicators | editing alpha-patterns |
| [strategies.md](strategies.md) | alpha_strategies: signals, sizing, rule specs | editing alpha-strategies |
| [backtest.md](backtest.md) | alpha_backtest: Nautilus harness, fees, results | editing alpha-backtest |
| [validation.md](validation.md), [validation-factor-statistics.md](validation-factor-statistics.md) | alpha_validation rules | editing alpha-validation |
| [research.md](research.md) | alpha_research: phase primitives | editing alpha-research |
| [forecast.md](forecast.md) | alpha_forecast: Kronos facade, quantile signal | editing alpha-forecast |
| [study.md](study.md) | alpha_study: study contracts, authority projections | editing alpha-study |
| [mcp.md](mcp.md) | alpha-mcp tools and their limits | editing the MCP server |
| [web-api.md](web-api.md) | Workstation backend: CLI relay, JSON, SSE | editing alpha_web routes |
| [web-api-reads.md](web-api-reads.md) | what the backend reads, writes and relays | changing what a route reads or writes |
| [web-frontend.md](web-frontend.md) | Workstation single-page app | editing the browser app |
| [web-run-detail.md](web-run-detail.md) | run detail, journey, Setup Lab, RD-Agent panel fields | editing the run detail panels |
| [web-research.md](web-research.md) | assistant, rule conditions, scans, case read plane | editing research surfaces in the web app |
| [workers.md](workers.md) | shared rules; Qlib, literature, AFML workers | editing anything under workers/ |
| [rdagent.md](rdagent.md) | RD-Agent worker: boundary, runtimes, gateway, factor loop, memory, viewer | editing workers/rdagent/ |

## Command line
| file | owns | load when |
|---|---|---|
| [cli-runs.md](cli-runs.md), [cli-nightly.md](cli-nightly.md) | runs, publication; the nightly run | `alpha run`, `alpha nightly` |
| [cli-setups.md](cli-setups.md) | `alpha setup find`, `study`, `trade` | `alpha setup` |
| [cli-research.md](cli-research.md) | governed Research Case commands | `alpha research` |
| [cli-control-store.md](cli-control-store.md) | SQLite control plane, receipts, jobs, holdouts | control store, jobs, confirmations |
| [cli-trial-ledger.md](cli-trial-ledger.md) | one trial ledger over spine and RD-Agent | `alpha ledger` |
| [cli-toolbox.md](cli-toolbox.md) | toolbox catalogue: adding a check, honesty rules | `alpha tool`, adding a check |
| [cli-investigation-tools.md](cli-investigation-tools.md) | follow-up questions on one rule test | investigating a recorded rule test |
| [cli-cost-classes.md](cli-cost-classes.md) | default costs and periods by asset class | `alpha test` costs line, `costs = "class-default"` |
| [cli-rule-readings.md](cli-rule-readings.md) | rule-test reading: words, aim, faults | `alpha test` text, the stored `reading` |
| [cli-results-check.md](cli-results-check.md) | draft checks and run comparisons | `alpha results check` or `compare` |
| [cli-crypto-data.md](cli-crypto-data.md) | `alpha data`, crypto data house | `alpha data`, `alpha crypto-data` |
| [cli-ml.md](cli-ml.md) | Qlib exchange, Kronos composition | `alpha ml`, `alpha forecast` |
| [cli-native.md](cli-native.md) | native upstream lanes: RD-Agent loop, rule studies | native loops, costed rule studies |
| [cli-paper.md](cli-paper.md), [cli-follow.md](cli-follow.md) | paper trading, scheduler; paper follow journal | `alpha paper`, `alpha follow`, `forward/` |
| [cli-assistant.md](cli-assistant.md) | advisory assistant, Codex investigations | `alpha assistant`, investigations |
