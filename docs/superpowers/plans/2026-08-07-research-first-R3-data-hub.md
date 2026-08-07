# Phase R3 — Research Data Hub (inventory, quality, registration, descriptives)

> **For agentic workers:** TDD per `CLAUDE.md`. Authority: spec §8 + ADR-0023 (+ADR-0018/0020).
> Audit rows: W3, W4, W8, W10 (regime tagging half). Depends on R1; parallel-safe with R2/R4.

**Goal:** "What data do we have, is it trustworthy, and can it answer the question?" becomes
answerable by owner and Codex alike: inventory/quality/snapshot projections reach MCP, research
datasets are registered against receipts, and descriptive audits run as governed artifacts —
before any hypothesis-specific computation.

**Scope:** one new CLI projection + one run class, one store table, five MCP tools (pin 54→59),
`descriptives.py`, ResearchDataExplorer panel, QuantPad receipt-backed adapter sub-slice. NOT in
scope: D1 analyses (R5), any quality-gate change, any new canonical source authority.

**Constraints:** all inventory tools read-only, projection-class timeouts; registration
fail-closed (no receipt/provenance → refuse); data-audit artifacts admissible to the Evidence Hub
data dimension only; `descriptives.py` imports alpha_core only (DAG contract); QuantPad bulk via
official SDK/REST only, `research_only` forever (ADR-0018/0020).

## File Map
```
apps/alpha-cli/src/alpha_cli/data_cmds.py           # ADD: `alpha data snapshots --json` (id, created_at, source, symbols, manifest hash)
apps/alpha-cli/src/alpha_cli/control_store.py       # ADD: research_dataset_refs DDL + register/get/list (binds ResearchDatasetRef→origin)
apps/alpha-cli/src/alpha_cli/research_cmds.py       # ADD: `alpha research data register|audit|list --json`; `run data-audit` run class
packages/alpha-research/src/alpha_research/descriptives.py (+tests, bias_guard)  # CREATE: coverage/gaps/distributions/seasonality/regime/effective-sample
packages/alpha-data/src/alpha_data/adapters/quantpad_adapter.py (+network tests)  # CREATE: receipt-backed bulk adapter (official SDK/REST), ADR-0018 fields
apps/alpha-mcp/src/alpha_mcp/server.py, _control.py, _types.py  # ADD: get_data_inventory, get_data_quality, get_data_candles,
                                                                 #      list_snapshots, get_provider_registry
tests/integration/test_research_mcp.py              # MODIFY: pin 54→59 (same commit)
apps/alpha-web/src/alpha_web/_research.py, api/research.py, api/models.py  # ADD: dataset-ref + audit projections
apps/alpha-web/frontend/src/panels/ResearchDataExplorer.tsx (+model+.test.ts)  # CREATE: coverage matrix, gap timeline, quality flags,
                                                                                #        provenance chain, descriptive views
apps/alpha-web/frontend/src/layouts/presets.ts      # MODIFY: ResearchDataExplorer into research preset (inactive right tab)
```

## Tasks
- [ ] **`alpha data snapshots --json`** — walk `data_dir/snapshots/*/manifest.json`; bounded,
      deterministic order; failing test first.
- [ ] **MCP inventory tools (+5)** — thin `_invoke.run_json` wrappers over
      `data symbols|source-status|audit|candles|snapshots` and `info providers`; strict outputs;
      candle previews bounded (≤500 bars — mirror the QuantPad discovery bound); pin 54→59 same
      commit; read-only negative tests.
- [ ] **`research_dataset_refs`** — DDL + `register_research_dataset(ref, origin)` where origin ∈
      {canonical store slice (symbol+range+provenance sha), snapshot (id+manifest hash), quantpad
      receipt (receipt id+response sha)}; fail-closed on missing receipt/provenance; contract
      drafts referencing unregistered data are rejected (extend draft validation test).
- [ ] **`descriptives.py`** — pure fns: coverage/calendar-gap summary (reuse quality vocabulary),
      return/volume distribution moments+quantiles, autocorrelation, seasonality tables,
      volatility-bucket regime tags, effective-sample/event-frequency estimates (reuse
      `power.py`); deterministic; fail-loud on NaN/inf/empty; bias_guard future-poison test on
      any windowed statistic.
- [ ] **`run data-audit`** — bounded synchronous run: registered dataset → descriptives →
      v3 artifacts + `ResearchChartData` renders (EXPLORATORY watermark) + manifest with
      `research_only` markers; **admissible only to the data dimension** (scorecard/evidence-hub
      tests assert it cannot flip effect/falsification dimensions).
- [ ] **QuantPad adapter sub-slice** — `DataAdapter`-shaped, official SDK/REST, receipt with
      request/response hashes + coverage/corrections + rate-limit metadata; `@pytest.mark.network`
      live tests; output registrable as dataset refs; NOT wired into canonical promotion
      (`_ADAPTERS` unchanged for `data pull`); provider definition marked
      `research_authority: false`.
- [ ] **ResearchDataExplorer panel** — coverage matrix (symbol × source × range × quality
      status), gap timeline, candidate/quarantine states, provenance chain
      (receipt→candidate→quality→canonical→snapshot), descriptive/seasonality/regime views,
      sample-size readouts; feeds scorecard data dimension display.
- [ ] **e2e + gates** — mocks, axe, dormancy; full gates; `static/app`; `CLAUDE.md` update.

## Done = R3 complete
Inventory/quality/snapshots on MCP; datasets registered against exact receipt-backed bytes;
descriptive understanding stored before hypothesis work; QuantPad bulk lane exists as
`research_only` scratch with receipts.

**Next:** R5 (experiment engine) once R2+R3 land; R4 in parallel.
