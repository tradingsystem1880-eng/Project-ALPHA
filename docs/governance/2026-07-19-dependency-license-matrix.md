# Dependency and License Matrix — Post-v2 and Workstation v3 Tracks

- **Reviewed:** 2026-08-03
- **Scope:** direct Python runtime dependencies, isolated workers, vendored code, and upstream
  projects considered by the post-v2 and Workstation v3 decisions
- **Status:** engineering inventory; not legal advice

## Root Project License and Distribution Gate

The Project ALPHA repository has **no root `LICENSE`, `LICENSE.txt`, `COPYING`, or declared
`project.license` metadata**. Licenses attached to third-party dependencies or the vendored Kronos
subtree do not license ALPHA's original code.

Therefore:

- no project license is inferred or selected by this change;
- personal local use remains the stated operating scope;
- publishing wheels, sharing a source/binary bundle, offering a hosted service, or otherwise
  distributing ALPHA is **blocked on an explicit owner license decision and release-time legal
  review**; and
- a release review must preserve dependency copyright/license notices and examine the exact locked
  transitive graph and frontend bundle, not only this direct-dependency summary.

## Current Direct Python Runtime Dependencies

Versions are the environment resolved from `uv.lock` on the review date. The manifests may declare
ranges except where a compatibility pin is explicitly required. "Post-v2 action" describes this
track; it is not a legal conclusion.

| Dependency | Resolved | License signal reviewed | Role/boundary | Post-v2 action |
|---|---:|---|---|---|
| pydantic | 2.13.4 | MIT | domain/API validation | retain |
| pydantic-settings | 2.14.1 | MIT | typed local configuration | retain |
| ccxt | 4.5.58 | [MIT](https://github.com/ccxt/ccxt/blob/master/LICENSE.txt) | historical crypto adapter only | retain; add validated Coinbase/Binance option |
| pandas | 2.3.3 | BSD-3-Clause | three sanctioned vendor/library edges | retain constrained edge |
| polars | 1.41.2 | MIT | default dataframe/store/artifacts | retain |
| yfinance | 1.4.1 | [Apache-2.0](https://github.com/ranaroussi/yfinance/blob/main/LICENSE.txt) | historical equity vendor edge | retain |
| nautilus-trader `[ib,docker]` | 1.228.0 | [LGPL-3.0](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE) | authoritative engine; reviewed Binance/Sandbox and native IBKR Paper factories | pin exactly `1.228.0`; upgrade only after compatibility and paper-boundary review |
| exchange-calendars | 4.13.2 | Apache-2.0 package metadata | authoritative session/DST scheduling and daily completeness checks | exact pin; calendar-version changes require data/scheduler regression review |
| numpy | 2.4.6 | BSD-3-Clause plus bundled notices | validation/forecast numerics | retain; preserve Qlib RL incompatibility gate |
| scipy | 1.17.1 | BSD-3-Clause | validation/options numerics | retain |
| torch | 2.12.1 | BSD-3-Clause | Kronos internals only | retain CPU-index policy |
| einops | 0.8.2 | MIT | Kronos internals | retain |
| huggingface-hub | 1.22.0 | Apache-2.0 | local/offline Kronos weight resolution | retain ADR-0010 policy |
| safetensors | 0.8.0 | Apache-2.0 | Kronos weight loading | retain |
| tqdm | 4.68.2 | MPL-2.0 and MIT metadata | Kronos progress dependency | retain; preserve notices on distribution |
| finnhub-python | 2.4.29 | Apache-2.0 metadata | credential-gated quote/news edge | retain |
| quantstats-lumi | 1.1.5 | Apache-2.0 metadata | tear-sheet pandas edge | retain |
| matplotlib | 3.11.0 | PSF-style license plus bundled asset notices | tear-sheet rendering | retain; release must include relevant notices |
| typer | 0.26.7 | MIT | authoritative CLI | retain |
| mcp | 1.28.0 | MIT metadata | stdio conversational surface | retain |
| fastapi | 0.138.0 | MIT | Workstation JSON backend | retain |
| uvicorn | 0.49.0 | BSD-3-Clause | loopback server | retain |
| sse-starlette | 3.4.5 | BSD-3-Clause | Workstation streams | retain |
| anyio | 4.14.0 | MIT | async web support | retain |

### IB/Docker extra and external-service review

Enabling Nautilus's pinned `ib` and `docker` extras adds `docker==7.2.0` (Apache-2.0),
`defusedxml==0.7.1` (PSF), `protobuf==5.29.5` (BSD-3-Clause), and
`nautilus-ibapi==10.45.1`. The installed `nautilus-ibapi` metadata identifies the **IB API
Non-Commercial License or IB API Commercial License**. This is not treated as an open-source grant;
distribution/hosted use requires exact terms, entitlement, and legal review in addition to ALPHA's
existing root-license blocker.

Tiingo is an external commercial data service, not code licensed by this repository. The approved
scope is private single-operator research/paper use under the owner's Tiingo plan; raw/canonical data
and charts are not redistributed or exposed publicly. IBKR account, exchange subscriptions, and API
permissions are also owner-provided service prerequisites.

QuantPad is also an external commercial data service. The approved present scope is its OAuth MCP
interface for bounded discovery/previews and its official REST/Python interface for private
historical research. No QuantPad package is yet a root runtime dependency, and its output is not a
canonical or paper-authoritative source. The public product material demonstrates API-to-Parquet
bulk workflows, while the service license separately restricts bulk export/retention without express
permission; permanent archives, post-subscription retention, redistribution, and commercial/public
use therefore remain blocked on written permission.

The IB Gateway container image is not pinned in source. Operations must provide an independently
dependency-reviewed `registry/image@sha256:<digest>`; mutable tags are rejected by code. The image's
software/license/notice inventory and credentials delivery (Docker secrets or OS-keychain wrapper)
must be reviewed before use. A digest proves identity, not licensing or trust.

The vendored `alpha_forecast._vendor.kronos` source is pinned upstream code under MIT terms and is
kept behind the `alpha_forecast` facade. Its license/notices must stay with any permitted
distribution.

This table intentionally does not claim to be a software-bill-of-materials. `uv.lock` and
`apps/alpha-web/frontend/package-lock.json` are the complete resolution inputs; a distributable
release needs an automated exact-version/transitive notice report.

## Frontend Test-only Dependencies

These packages are development/release gates and are not analytical or production runtime
authorities. Their exact transitive resolution remains pinned by the frontend lockfile.

| Dependency | Exact pin | License signal reviewed | Boundary role |
|---|---:|---|---|
| @playwright/test | 1.61.1 | Apache-2.0 | Chromium desk, responsive, keyboard, and visual-structure release tests |
| @axe-core/playwright | 4.12.1 | MPL-2.0 | WCAG A/AA serious/critical accessibility assertions inside Playwright |
| axe-core | 4.12.1 | MPL-2.0 | transitive accessibility rule engine used only by the browser test gate |
| Playwright-managed Chromium | resolved by `@playwright/test` 1.61.1 | Chromium BSD-style license plus bundled third-party notices; exact downloaded bundle requires release-time notice collection | Test-only local/CI browser; never shipped in the ALPHA wheel or used as an analytical runtime |

## Considered Upstream Projects

| Project | License reviewed | Capability overlap/gap | Disposition for this track |
|---|---|---|---|
| NautilusTrader | [LGPL-3.0](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE) | Already supplies engine, Binance data, Sandbox execution, and native IBKR Paper clients | **Adopted already**; exact compatibility pin, no replacement; IB extra terms reviewed separately above |
| Tiingo EOD | Commercial service/data terms | Missing authoritative long-history stock/ETF daily-data receipt source | **Adopted for private EOD ingestion only**; credentials stay server-side and redistribution is prohibited |
| QuantPad MCP + REST/Python data | Commercial service/data terms | Broad historical futures/equity/options bars, ticks, L1, and short-window L2 research | **Adopted as external research access only**; MCP for bounded discovery, API/SDK for bulk; no canonical/paper authority pending adapter and written retention evidence |
| IBKR Paper / IB Gateway | Commercial broker/API terms; exact image inventory varies by chosen digest | Missing stock/ETF broker-paper connectivity and reconciliation path | **Adopted paper-only through Nautilus**; loopback/4002/DU account, dual flags, digest review, no live route |
| Massive / Databento | Commercial services | Larger/intraday universes and funded research-grade futures history | Deferred until a measured capacity/research requirement and fresh evidence/license review |
| QuantConnect LEAN / MetaTrader | Engine/terminal overlap | Would duplicate Nautilus authority or add terminal-process coupling | Not adopted in this milestone |
| OpenBB | [AGPL-3.0](https://github.com/OpenBB-finance/OpenBB/blob/develop/LICENSE) | Provider federation pattern; ALPHA already has data/CLI/UI authorities | Architecture reference only; no code/runtime dependency |
| Qlib | [MIT](https://github.com/microsoft/qlib/blob/main/LICENSE); [official dependency manifest](https://github.com/microsoft/qlib/blob/main/pyproject.toml) | Cross-sectional ML workflow/recorder gap; broad stack conflicts with the root NumPy/pandas boundary | **Approved only as the ADR-0016 isolated worker**; immutable snapshot/folds in, timestamped OOS JSON/Parquet out; never a root dependency or analytical authority |
| FinancePy | [GPL-3.0](https://github.com/domokane/FinancePy/blob/master/LICENSE) | Broader derivatives products not presently required | Deferred product-specific external worker + fresh legal review |
| TradingAgents | [Apache-2.0](https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE) | AI research overlay; ALPHA already has MCP/research desk | Research-only candidate; no execution authority or runtime dependency |
| TensorTrade | [Apache-2.0](https://github.com/tensortrade-org/tensortrade/blob/master/LICENSE) | RL experiments; not an execution/validation authority | Isolated research candidate only; separate spec/environment |
| Alpaca Python SDK | [Apache-2.0](https://github.com/alpacahq/alpaca-py/blob/master/LICENSE) | Broker/data provider not needed for Binance sandbox scope | Not adopted; evidence gate if a broker-specific use case appears |
| Vollib | License must be re-verified from the exact package/source revision before use | Potential options parity oracle; no current capability gap | Not adopted; parity-only proposal requires its own evidence/test plan |
| Twelve Data SDK | License and service terms must be re-verified before use | Additional keyed data coverage not needed now | Not adopted |

Process isolation is a risk-control and replaceability technique, not a declaration that a license
has no effect. Any future AGPL/GPL/LGPL integration still requires review of the exact use,
modifications, linking/deployment model, notices, and distribution behavior.

## Workstation v3 dependency decision

Workstation v3 adds no root runtime or frontend visualization dependency for the shell, control
plane, causal charts, native tear sheet, or evidence ledger. It retains Dockview, Lightweight
Charts, uPlot, TanStack, Polars, Nautilus, QuantStats-Lumi, and the vendored Kronos facade.

Qlib is the one approved external capability addition. Its separately generated
`workers/qlib/uv.lock` is the exact resolution input for that optional process and must be reviewed
independently before distribution. The root `pyproject.toml` and `uv.lock` must remain free of Qlib,
LightGBM, MLflow, and worker-only transitive dependencies. ALPHA exchanges only validated
JSON/Parquet and never imports/deserializes the worker runtime or its model objects.

The implemented worker's direct runtime pins are:

| Worker dependency | Exact pin | License signal reviewed | Boundary role |
|---|---:|---|---|
| pyqlib | release/package `0.9.7` | MIT; notice copied to `workers/qlib/THIRD_PARTY_NOTICES.md` | fold orchestration, feature/model workflow, diagnostic recorder concepts |
| lightgbm | release/package `4.6.0` | MIT; notice copied to `workers/qlib/THIRD_PARTY_NOTICES.md` | CPU cross-sectional starter model |
| numpy | 2.2.6 | BSD-3-Clause plus bundled notices | worker-local numeric arrays; deliberately distinct from the root resolution |
| pandas | 2.3.3 | BSD-3-Clause | Qlib-compatible worker dataframe boundary |
| polars | 1.41.2 | MIT | deterministic JSON/Parquet exchange validation and publication |

The worker gate runs its own locked sync, Ruff, strict mypy, and pytest job. Distribution still
requires a generated complete transitive notice bundle; the two copied direct notices are not a
complete SBOM.

Implementation checkpoint: `workers/qlib/uv.lock` resolves both exact release pins and currently
hashes to `6616ac9c86600794d15416ca010a9f9e073ea7a100e9322b31b7a8dcb5659713`. Any worker-lock change
must update this reviewed hash and rerun the isolated gate. The removal path is bounded and recorded
in `workers/qlib/README.md`: delete the isolated project, remove root `alpha ml` projections, and
delete worker exchange/control links; no root package dependency or historical run rewrite is
required.

Optuna, DuckDB, ECharts, skfolio, LEAN, TradingAgents, FinRL, and RD-Agent are not adopted by v3.
They require a new concrete capability gap and a separate ADR-0011 acceptance record.

## Required Review on Change

Update this matrix and the [risk register](2026-07-19-post-v2-risk-register.md) when any of these
occurs:

- a direct or vendored dependency is added, removed, relicensed, or materially upgraded;
- NautilusTrader moves off `1.228.0`;
- a deferred upstream candidate becomes executable in the ALPHA runtime;
- the Workstation binds beyond loopback or becomes multi-user/hosted;
- ALPHA is prepared for publication or distribution; or
- the owner chooses a root project license.
