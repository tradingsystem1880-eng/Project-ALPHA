---
paths:
  - "packages/alpha-options/**"
  - "packages/alpha-screener/**"
---
# alpha_options + alpha_screener rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.
### `alpha_options` (`packages/alpha-options/src/alpha_options/`) — options & derivatives analytics. core only (+ numpy/scipy).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `black_scholes.py` | Pure European-option pricing/greeks/IV (no market data, no look-ahead surface) | `bs_price`, `bs_greeks` (vega/1pt, theta/day, rho/1%), `implied_vol`, `Greeks` |

### `alpha_screener` (`packages/alpha-screener/src/alpha_screener/`) — screener & news via finnhub (opt-in, API-key-gated). core only; the one network edge.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `models.py` | Frozen response values | `Quote`, `NewsItem` |
| `parse.py` | Pure finnhub-response parsers (fail loud on malformed / unknown-symbol bodies) | `parse_quote`, `parse_news` |
| `finnhub.py` | The one network edge (lazy `import finnhub`; gated on `ALPHA_FINNHUB_API_KEY`) | `fetch_quote`, `fetch_news` |

