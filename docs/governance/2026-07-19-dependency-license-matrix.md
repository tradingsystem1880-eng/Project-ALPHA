# Dependency and License Matrix — Post-v2 Provider/Paper Track

- **Reviewed:** 2026-07-19
- **Scope:** direct Python runtime dependencies with architectural/legal significance, vendored
  code, and upstream projects considered by the attached workstation recommendation
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
| nautilus-trader | 1.228.0 | [LGPL-3.0](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE) | authoritative engine and reviewed Binance/sandbox factories | pin exactly `1.228.0`; upgrade only after compatibility review |
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

The vendored `alpha_forecast._vendor.kronos` source is pinned upstream code under MIT terms and is
kept behind the `alpha_forecast` facade. Its license/notices must stay with any permitted
distribution.

This table intentionally does not claim to be a software-bill-of-materials. `uv.lock` and
`apps/alpha-web/frontend/package-lock.json` are the complete resolution inputs; a distributable
release needs an automated exact-version/transitive notice report.

## Considered Upstream Projects

| Project | License reviewed | Capability overlap/gap | Disposition for this track |
|---|---|---|---|
| NautilusTrader | [LGPL-3.0](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE) | Already supplies engine, Binance data, sandbox execution | **Adopted already**; exact compatibility pin, no replacement |
| OpenBB | [AGPL-3.0](https://github.com/OpenBB-finance/OpenBB/blob/develop/LICENSE) | Provider federation pattern; ALPHA already has data/CLI/UI authorities | Architecture reference only; no code/runtime dependency |
| Qlib | [MIT](https://github.com/microsoft/qlib/blob/main/LICENSE); [official dependency manifest](https://github.com/microsoft/qlib/blob/main/pyproject.toml) | ML workflow/recorder capabilities beyond this track, but broad stack and environment conflict | Deferred separate environment; immutable snapshot in, timestamped OOS signals/provenance out |
| FinancePy | [GPL-3.0](https://github.com/domokane/FinancePy/blob/master/LICENSE) | Broader derivatives products not presently required | Deferred product-specific external worker + fresh legal review |
| TradingAgents | [Apache-2.0](https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE) | AI research overlay; ALPHA already has MCP/research desk | Research-only candidate; no execution authority or runtime dependency |
| TensorTrade | [Apache-2.0](https://github.com/tensortrade-org/tensortrade/blob/master/LICENSE) | RL experiments; not an execution/validation authority | Isolated research candidate only; separate spec/environment |
| Alpaca Python SDK | [Apache-2.0](https://github.com/alpacahq/alpaca-py/blob/master/LICENSE) | Broker/data provider not needed for Binance sandbox scope | Not adopted; evidence gate if a broker-specific use case appears |
| Vollib | License must be re-verified from the exact package/source revision before use | Potential options parity oracle; no current capability gap | Not adopted; parity-only proposal requires its own evidence/test plan |
| Twelve Data SDK | License and service terms must be re-verified before use | Additional keyed data coverage not needed now | Not adopted |

Process isolation is a risk-control and replaceability technique, not a declaration that a license
has no effect. Any future AGPL/GPL/LGPL integration still requires review of the exact use,
modifications, linking/deployment model, notices, and distribution behavior.

## Required Review on Change

Update this matrix and the [risk register](2026-07-19-post-v2-risk-register.md) when any of these
occurs:

- a direct or vendored dependency is added, removed, relicensed, or materially upgraded;
- NautilusTrader moves off `1.228.0`;
- a deferred upstream candidate becomes executable in the ALPHA runtime;
- the Workstation binds beyond loopback or becomes multi-user/hosted;
- ALPHA is prepared for publication or distribution; or
- the owner chooses a root project license.
