# Terminal usability implementation and verification

> **Superseded acceptance note (2026-10-05):** pending or failed aggregate results below are historical. The canonical full gate later passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC); see `docs/BUILD-STATUS.md`.

Date: 2026-09-30. Working tree based on benchmark commit e54aa7a; benchmark session work is separate. The earlier September 29 gate does not attest this tree.

## Delivered behavior

- Compact grey Windows-style chrome, square controls, blue selection, black candle canvas and resizable Market Watch/Navigator beside the chart; optional Data Manager and maximize/restore. Workflow routes and existing capabilities remain reachable.
- Ordinary owner actions use explicit click confirmation without enrollment. ControlStore V6 preserves historical WebAuthn receipts and records local confirmation honestly; domain action checks remain authoritative. ADR-0038 documents the chosen trusted-local security model.
- External archive discovery exposes exact supported acquisition windows. Selected charts verify normalized bytes and raw lineage, validate venue/market/units, and exclude unfinished bars. Archive identity and intervals remain separate from canonical strategy context. Same-base symbols with different quote assets/venues remain distinct.
- Storage and coverage use metadata-only discovery for ordinary navigation. Feature listing filters metadata before fully verifying selected feature artifacts and their lineage. Explicit full audits remain available.
- Crypto display classification now includes hyphenated USD/USDT/USDC pairs such as BTC-USD without classifying BRK-B as crypto.

## Real owner data observations

The configured external drive was mounted and readable. API discovery returned 2,178 compatible datasets; earlier metadata inspection found 50 distinct instrument strings among those datasets. A real browser loaded 901 AAVEUSDT daily Bybit linear bars with no browser errors. The selected chart displayed its own venue, interval, market type, archive identity and base-volume units. Earlier direct selected-reader checks also loaded Binance BTCUSDT hourly and Bybit AAVEUSDT hourly bars.

During concurrent test load, read-only owner API calls completed: chart discovery 11.27s; metadata storage 6.36s; coverage 5.57s (11,774 normalized records); features 5.35s (12 verified features). These are observations, not a latency benchmark or full-drive audit. No new bulk download or owner research decision was performed.

## Verification record

- Frontend: 314 unit tests, type/build and warning-free lint passed. Configured model coverage: 93.23% statements, 82.9% branches, 94.9% lines; this is not coverage of every visual component.
- Local confirmation: 19 focused tests passed, including populated migration, rollback/retry, concurrency, historical foreign keys, replay, revision and request-origin protections.
- Bulk chart: 9 focused tests passed, including selected artifact/raw-parent tampering, unsupported identity/units, malformed Parquet, hourly and daily completion boundaries.
- Archive API: 2 focused tests passed; exact manifest forwarding and no canonical paper-marker mixing.
- Strict mypy passed across 697 files. All 13 import contracts, scoped source/test/script ruff checks, semgrep and its leak probes, OpenAPI freshness/authority and wheel build/import smoke passed.
- Independent UI and backend reviews found no remaining blockers by inspection after fixes. They did not claim a full gate pass.
- Final isolated broad Python run: 4,740 passed, 2 skipped, 2 expected failures; 93.11% backend coverage. Command: `uv run pytest -q -n auto -m "not network and not slow_oracle" --cov`.
- Final frontend component gate passed all steps, including 196 browser scenarios, generated API and SPA freshness. Browser coverage spans three viewports plus exhaustive real-backend task inventory; screenshot baselines were regenerated, visually inspected and then compared in this passing run. The component receipt was recorded before this final documentation/atlas refresh; it is not a full-repository stamp.
- One earlier concurrent Python/browser run classified a delayed ML cancellation test as failed rather than cancelled. The isolated cancellation tests and final full Python run passed without changing that test or the production deadline. Treat heavy-load heartbeat timing as an observed operational limitation, not proof that every live ML worker is ready.
- Earlier stale Touch ID wording assertions, the manual size limit and a mixed-version OpenAPI check were corrected/rechecked before final acceptance. No hidden test source was inspected.
- Canonical full gate attempted and failed at global ruff on 198 errors in the concurrent benchmark session's untracked `tmp/pdfs/alpha-benchmark-2026-09-30/build_report.py`. That file was not edited or excluded. No current-tree full-gate stamp exists.

## Boundaries and next candidates

Live exchange streaming, paid-provider credentials, broker connectivity and model-worker readiness are not established by these offline/browser checks. Archive visualization is not research admission or reconstructed point-in-time availability. The open-source review records retained engines and candidates; Dockview, Perspective, KLineChart, TA-Lib and Optuna have not been added or benchmarked in production. See [component review](2026-09-30-open-source-component-review.md).
