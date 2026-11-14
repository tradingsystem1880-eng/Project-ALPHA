# Free real market data on the Dell

**Delivery state:** Completed — downloads done and checked on branch `m5/free-real-data`; done when its pull request merges.
**Build class:** small — no code was needed: every download used existing `alpha` commands; only documents changed, written by Claude.

Filed straight into the archive, as `2026-11-14-rdagent-model-gateway` was: the work-in-progress
ceiling (34, a ratchet) admits no new live plan, and the work was finished in one sitting.

## For the owner

- Crypto: real Binance daily prices for 15 major coins against USDT, as far back as Binance's
  free archive goes (2017 for the oldest), are now on the Dell, checked and frozen-able.
- Stocks: none yet. Yahoo's terms forbid automated downloading and Stooq blocks it, so neither
  was used. You choose what happens next (see `05-handoff.md`).
- Everything is labelled not yet confirmed.

```json
{
  "schema_version": 1,
  "title": "Free real market data on the Dell",
  "context": "The owner chose free, keyless real data on the Dell (Yahoo, Stooq, crypto exchanges) with results labelled not yet confirmed; until then the Dell held only made-up data.",
  "assumptions": [
    {"statement": "Keyless providers already exist: yfinance and stooq adapters for stocks, Binance public archives and REST in the crypto data house, CCXT Binance in the stock store.", "verified_by": "reading packages/alpha-data/src/alpha_data/adapters/ and crypto/providers/binance.py"},
    {"statement": "Binance Vision archives may be used for personal, non-production backtesting under CC BY-NC-SA 4.0.", "verified_by": "Binance Vision Dataset Terms PDF, version 1.0, last updated 2026-08-26, read on data.binance.vision"},
    {"statement": "Yahoo's terms forbid automated data collection without prior permission and query1.finance.yahoo.com robots.txt disallows all paths.", "verified_by": "legal.yahoo.com Terms of Service section 2(d) and the robots.txt file, read 2026-11-14"},
    {"statement": "Stooq serves a JavaScript browser-verification page to automated clients and its robots.txt disallows all user agents except two search engines.", "verified_by": "one request with a generic client name and stooq.com/robots.txt, 2026-11-14"},
    {"statement": "A Binance daily bar becomes visible only after its UTC day closes in the archive reader.", "verified_by": "apps/alpha-cli/src/alpha_cli/_chart_data.py skips a bar while open time plus one day is after the cutoff; a query to 2022-06-30 ended at 2022-06-29"}
  ],
  "alternatives_considered": [
    "Use the existing yfinance adapter anyway: rejected, Yahoo's terms forbid automated collection and the source counts as blocking automated access.",
    "Use the existing stooq adapter, which solves Stooq's browser-verification check: rejected, that is getting past a bot check.",
    "Build the offline local-file import now for hand-downloaded stock files: deferred, it needs the owner's choice of stock source and the snapshot source-labelling decision named in the backlog note.",
    "Add a new confidence field to receipts: not done, receipts and manifests are hash-bound and the existing labels plus capability lines already say not yet confirmed."
  ],
  "pre_mortem": [
    "A free source revises history: Binance's archive and its live API already disagree on volume on 10 BTC days; recorded, prices match, data stays not yet confirmed.",
    "Disk fills: the owner's 10 GB reserve refuses any write that would cross it; total stored is far below the 8 GB budget.",
    "Data mistaken for confirmed evidence: every capability line starts with not yet confirmed and the stock-store copy reads legacy_unqualified."
  ],
  "slices": [
    {"title": "Data folder and storage reserve", "verify": "uv run python scripts/storage_settings.py show --data-dir /home/hunta/alpha-clean-base/data", "expected": "reserve 10.0 GB, owner-set", "rollback": "delete /home/hunta/alpha-clean-base/data", "status": "done"},
    {"title": "Terms and access checks for Yahoo, Stooq and Binance", "verify": "04-verify.md quotes each page", "expected": "Binance permitted for personal backtesting; Yahoo and Stooq refuse automated access", "rollback": "none needed", "status": "done"},
    {"title": "Binance spot daily backfill of 15 USDT pairs and a spot market list", "verify": "uv run alpha data chart-datasets --json", "expected": "15 groups, qualified", "rollback": "remove the data folder", "status": "done"},
    {"title": "As-of read, snapshots, verification and one backtest on real data", "verify": "commands in 04-verify.md", "expected": "real rows, integrity OK, eligible, run written", "rollback": "none needed", "status": "done"},
    {"title": "Data-layer page, capability map, status", "verify": "uv run python scripts/gate.py check --all", "expected": "All checks passed", "rollback": "revert the document changes", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/reference/project/components/data-layer.md", "docs/roadmap/capabilities.toml", "STATUS.md"],
  "out_of_scope": ["packages/alpha-research/src", "packages/alpha-validation/src", "adapter and provider code", "keyed providers", "data files in git", "research approvals"],
  "files": [
    "docs/work/archive/2026-11/2026-11-14-free-real-data-dell/",
    "docs/reference/project/components/data-layer.md",
    "docs/roadmap/capabilities.toml",
    "docs/roadmap/README.md",
    "STATUS.md"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [data layer](../../../../reference/project/components/data-layer.md) | Real data on the Dell | always |
| [command line data invariants](../../../../reference/invariants/cli-crypto-data.md) | Backfill, Bulk storage | running downloads |
| [storage settings](../../../../operations/storage-settings.md) | — | the data folder |

## Slices

As in the JSON block. No code changed, so nothing went to Codex.

## Test plan

No new code, so no new tests. The proof is the recorded runs in `04-verify.md` and the full
gate on the document changes.

## Look-ahead, determinism and import impact

No code touched. The as-of reads used the existing loaders; the archive reader hides a daily bar
until its UTC day has closed (checked on a real query). No import change.
