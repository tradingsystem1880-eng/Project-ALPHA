# Dependency and License Matrix — Post-v2, Workstation v3, and Research Scientist Tracks

- **Reviewed:** 2026-08-11
- **Scope:** direct Python runtime dependencies, isolated workers, vendored code, external services,
  and upstream projects considered by the post-v2, Workstation v3, and Research Scientist decisions
- **Status:** engineering inventory; not legal advice

## Permanent Private Local-Use Scope

The Project ALPHA repository has **no root `LICENSE`, `LICENSE.txt`, `COPYING`, or declared
`project.license` metadata**. Licenses attached to third-party dependencies or the vendored Kronos
subtree do not license ALPHA's original code.

The owner has fixed ALPHA's scope as private, single-owner software used only on the owner's local
device. It will not be sold, published, shared, hosted, or used by others. A root project license,
SBOM release bundle, and distribution legal review are therefore not project requirements.

This does not erase third-party obligations. Keep dependency notices, provider/service terms,
credential rules, and data-retention restrictions intact for local use. If the owner ever changes
the private/local-only scope, stop and reopen the exact distribution and notice review before any
source, wheel, artifact, data, or hosted surface is shared.

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
| matplotlib | 3.11.0 | PSF-style license plus bundled asset notices | deterministic tear-sheet, research-chart, and Workstation figure rendering | retain; release must include relevant notices, **including the bundled DejaVu fonts whose glyph outlines are now embedded in emitted SVGs** (see below) |
| typer | 0.26.7 | MIT | authoritative CLI | retain |
| mcp | 1.28.0 | MIT metadata | stdio conversational surface | retain |
| fastapi | 0.138.0 | MIT | Workstation JSON backend | retain |
| uvicorn | 0.49.0 | BSD-3-Clause | loopback server | retain |
| sse-starlette | 3.4.5 | BSD-3-Clause | Workstation streams | retain |
| anyio | 4.14.0 | MIT | async web support | retain |
| webauthn | 3.0.0 | BSD-3-Clause package metadata | exact-origin platform-authenticator verification for closed local research owner actions | exact pin; no MCP, broker, order, holdout, paper-entry, risk-override, or research-gate-override authority |

### IB/Docker extra and external-service review

Enabling Nautilus's pinned `ib` and `docker` extras adds `docker==7.2.0` (Apache-2.0),
`defusedxml==0.7.1` (PSF), `protobuf==5.29.5` (BSD-3-Clause), and
`nautilus-ibapi==10.45.1`. The installed `nautilus-ibapi` metadata identifies the **IB API
Non-Commercial License or IB API Commercial License**. This is not treated as an open-source grant;
the private local operator must retain the required entitlement. Distribution and hosted use are
outside ALPHA's scope.

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

### Fonts embedded in emitted figures (2026-08-07)

The Workstation figure engine renders with `svg.fonttype="path"`, which converts every glyph to
an outline rather than referencing a font by name. That is a determinism requirement — a named
font resolves differently on each machine — but it changes the licence surface: Matplotlib's
bundled **DejaVu Sans** and **DejaVu Sans Mono** outlines are now present in the bytes of every
SVG the platform emits, not merely in a build input. DejaVu is distributed under the Bitstream
Vera / DejaVu licence, which permits embedding and redistribution of the glyph shapes and is
not copyleft, so no new restriction attaches to run artifacts. Two obligations follow and are
recorded here rather than discovered at release: the DejaVu and Bitstream Vera notices must ship
with any distribution that includes rendered figures, and the licence forbids selling the fonts
themselves in isolation — extracting the embedded outlines back into a font file is out of
scope for this project and must not be done.

Substituting Inter or JetBrains Mono into figures, so they match the SPA's typography, is
deferred. Both are SIL OFL 1.1 with reserved font names; embedding outlines is permitted, but
the OFL's naming and bundling clauses need their own row here before it happens.

The initial Research Scientist slice adds no academic-search package or service client. The
first-party `alpha-research` wheel uses the root's already-sanctioned Matplotlib/NumPy/SciPy stack and
adds no new third-party runtime dependency. Proposed source interfaces—OpenAlex, Semantic Scholar,
Crossref, Unpaywall, arXiv, SSRN, NBER, RePEc, and direct publisher/repository pages—remain external
metadata/document services. Gate 2 includes fail-closed URL/DNS/MIME/size/receipt validation
primitives but performs no network request or document retention. Before network automation, the
exact API terms, attribution, rate limits, metadata/full-text rights, caching, retention,
retraction/version semantics, and redistribution boundary must be recorded. Google Scholar remains
manual/browser-assisted verification and may not be scraped.

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
| QuantDinger | License and branding terms vary by reviewed subtree and must be re-verified from an exact revision | Durable-job/capability patterns and factor diagnostics, but also a separate broker/web stack | Architecture reference only; no code, service, broker, UI, or runtime dependency |
| Vibe-Trading | [MIT](https://github.com/HKUDS/Vibe-Trading/blob/main/LICENSE) plus repository notice obligations | Hypothesis/evidence workflow and source-search patterns; validation shortcuts do not meet ALPHA gates | Architecture reference only; no agent runtime, generated-code execution, or validation authority |
| AI-Trader | No repository-wide license grant verified for the reviewed source; re-verify exact revision | Networked signal/paper challenge patterns rather than governed strategy research | Conceptual caution only; no code or runtime adoption |
| atlas-gic | [MIT](https://github.com/chrisworsey55/atlas-gic/blob/main/LICENSE) | Autoresearch keep/revert framing, but released framework omits ALPHA-grade causal validation | Architecture reference only; no code or claimed results adopted |
| Karpathy autoresearch | Exact revision/license must be re-verified before reuse | Small frozen harness, one mutable target, fixed budget, and keep/reject log | Pattern adopted in the spec; no code or runtime dependency |
| Hermes agent/self-evolution variants | Exact product/revision/license not selected | General agent runtime and self-modification overlap with Codex/MCP and increases authority risk | Not adopted; proposal-only sandbox requires a measured gap and separate ADR |
| Scholarly metadata/document services | Service-specific terms; exact Gate 2 review pending | Literature discovery, DOI/version/retraction metadata, and lawful full-text resolution | Validation primitives only; no automated client, request, download, or retained corpus |
| TensorTrade | [Apache-2.0](https://github.com/tensortrade-org/tensortrade/blob/master/LICENSE) | RL experiments; not an execution/validation authority | Isolated research candidate only; separate spec/environment |
| Alpaca Python SDK | [Apache-2.0](https://github.com/alpacahq/alpaca-py/blob/master/LICENSE) | Broker/data provider not needed for Binance sandbox scope | Not adopted; evidence gate if a broker-specific use case appears |
| Vollib | License must be re-verified from the exact package/source revision before use | Potential options parity oracle; no current capability gap | Not adopted; parity-only proposal requires its own evidence/test plan |
| Twelve Data SDK | License and service terms must be re-verified before use | Additional keyed data coverage not needed now | Not adopted |

Process isolation is a risk-control and replaceability technique, not a declaration that a license
has no effect. Any future AGPL/GPL/LGPL integration still requires review of the exact use,
modifications, linking/deployment model, notices, and distribution behavior.

## Workstation v3 dependency decision

The integrated Workstation uses the purpose-built six-screen shell and server-rendered analytical
figures. The hardening program removed unused Dockview and uPlot runtime dependencies, reducing the
frontend license and attack surface while retaining Lightweight Charts and TanStack for the bounded
interactive views. Security-only transitive updates moved MIT-licensed `js-yaml` to 4.3.1 and
`nanoid` to 3.3.18; `npm audit --audit-level=high` reports zero vulnerabilities. Root Polars,
Nautilus, QuantStats-Lumi, and the vendored Kronos facade remain unchanged.

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

Optuna, DuckDB, ECharts, skfolio, LEAN, TradingAgents, QuantDinger, Vibe-Trading, AI-Trader,
atlas-gic, Hermes, FinRL, and RD-Agent are not adopted as ALPHA runtimes. The initial Research
Scientist slice adds repository-authored skills, the first-party `alpha-research` workspace wheel,
CLI-owned control/intake/dossier modules, and a pure frontend projection; it adds no third-party
package or source-service client beyond the already-reviewed Matplotlib/NumPy/SciPy resolution. Any
executable upstream adoption requires a new concrete capability gap and a separate ADR-0011
acceptance record.

## Required Review on Change

Update this matrix and the [risk register](2026-07-19-post-v2-risk-register.md) when any of these
occurs:

- a direct or vendored dependency is added, removed, relicensed, or materially upgraded;
- NautilusTrader moves off `1.228.0`;
- a deferred upstream candidate becomes executable in the ALPHA runtime;
- an academic metadata/full-text client, retained source corpus, or external agent runtime is added;
- the Workstation binds beyond loopback or becomes multi-user/hosted;
- the owner proposes publication, sale, distribution, hosting, or access by another person; or
- the owner otherwise changes the permanent private/local-only scope.

## Literature acquisition worker (`workers/literature`, ADR-0024)

The isolated literature worker has one runtime dependency: `pypdf==6.14.2` (BSD-3-Clause)
for bounded PDF text extraction. Discovery, transport, validation, hashing, and XML/JSON parsing
remain stdlib-only; arXiv XML refuses DOCTYPE/ENTITY markup. Its dev group pins the same
ruff/mypy/pytest tools already reviewed for the Qlib worker.
`workers/literature/uv.lock` is the exact resolution input for that optional process. Network
access is limited to the ADR-0024 approved metadata services (OpenAlex, Crossref, Unpaywall,
arXiv) and open-access/owner-provided documents; every stored object carries an
`UNTRUSTED_SOURCE` receipt and grants no license or redistribution right beyond the source's
own terms.
