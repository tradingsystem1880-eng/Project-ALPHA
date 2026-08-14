# Local Daily Data and Paper Operations

This runbook is for the single-operator local deployment. Do not commit `.env`, Tiingo/IBKR
credentials, account identifiers, Docker secrets, generated journals, or copied market data.

The supplied Tiingo token, QuantPad token, CoinGecko Demo key, and IBKR Paper account identifier are
stored in the macOS keychain services `project-alpha-tiingo`, `project-alpha-quantpad`,
`project-alpha-coingecko`, and `project-alpha-ibkr-paper-account`. Repository files contain only
those service names. The local `.env` is git-ignored and mode `0600`; it must not receive vendor or
broker secrets.

For CoinGecko, run exactly one bounded authenticated readiness check with:

```bash
scripts/alpha-with-keychain-provider coingecko check
```

The launcher injects `ALPHA_COINGECKO_API_KEY` into only that replacement process. CoinGecko market
reference, GeckoTerminal pool data, and Coin Metrics network data remain separate families;
CoinGecko verification does not qualify any downloaded dataset.

## 1. Use QuantPad for external historical research

The project-scoped `.codex/config.toml` registers QuantPad's OAuth MCP endpoint. Start a new Codex
session, run `/mcp`, and complete the QuantPad sign-in. Use MCP only for:

- symbol search and symbology resolution;
- coverage and schema discovery;
- recent usage/quota inspection; and
- a small OHLCV shape/quality preview (at most 500 bars and 31 days).

Do not loop previews to build history. For bars beyond that bound, ticks, L1, L2/`mbp-10`,
notebooks, or backtests, use QuantPad's official REST API/Python SDK. Load the API key into only the
process that needs it. The checked launcher retrieves one named item and replaces itself with the
exact check or Workstation process:

```bash
scripts/alpha-with-keychain-provider quantpad check
```

Use `get_coverage` before every bulk request and project only required order-book columns. Store
bulk results outside tracked repository paths. They remain research scratch data until ALPHA has a
tested receipt/candidate/quality adapter; they must not be relabeled as canonical data or paper
evidence. Website scraping, nonpublic endpoints, redistribution, public display, and model training
are prohibited. Obtain written QuantPad permission before permanent bulk archiving or retention
after a subscription ends. See ADR-0018.

## 2. Configure daily Tiingo work

Copy `daily-paper.example.json` outside the repository's tracked files and set the canonical symbol,
Tiingo provider symbol, exact Nautilus instrument ID, asset class, venue/calendar/currency, strategy,
NAV, history start, correction delay, and order cutoff. Set `ALPHA_TIINGO_API_KEY` through the OS
keychain service `project-alpha-tiingo`; `scripts/run_daily_scheduler.sh` retrieves it without
putting the token in the plist. For example, add/update the key manually with macOS `security`
without committing the command or its value to a repository file.

Run a manual, non-ordering status/tick first:

```bash
uv run alpha paper scheduler-status --config /absolute/private/daily-paper.json
uv run alpha paper scheduler-tick --config /absolute/private/daily-paper.json
uv run alpha data source-status SPY --json
```

Inspect any quarantined receipt with `alpha data audit PROVIDER RECEIPT_ID`. Promote it only after
review with `alpha data repair PROVIDER RECEIPT_ID --approve-differences`. If promotion itself was
interrupted, restore the exact pre-promotion bytes with
`alpha data rollback-promotion SYMBOL --acknowledge`. These are distinct recovery operations.

Install the example launch agent only after replacing every absolute placeholder. It runs a short
tick every 300 seconds and at load; it is not a persistent daemon. Keep stdout/stderr and config
paths private. A cycle crash is visible in `scheduler-status`; after diagnosing canonical state,
clear only that exact cycle marker with
`alpha paper scheduler-repair SYMBOL YYYY-MM-DD --config ... --acknowledge`.

The Readiness Center and `alpha info providers --json` are local projections and never probe a
provider. `scripts/alpha-with-keychain-provider tiingo check` performs one bounded SPY
authentication/schema check and stores a redacted `ProviderCheckReceiptV1`. That receipt does not
qualify data: ingestion, audit, and promotion remain separate steps.

## 3. Prepare IBKR Paper

Owner prerequisites are an IBKR paper account, permissions/subscriptions, Docker, and an independently
reviewed IB Gateway image digest. Inject `TWS_USERNAME`/`TWS_PASSWORD` using Docker secrets or an OS
keychain-backed wrapper. Set only process-local values for:

```text
ALPHA_IBKR_PAPER_ACCOUNT=DU...
ALPHA_IBKR_GATEWAY_IMAGE=registry/image@sha256:<reviewed-64-hex-digest>
```

Verify the boundary without enabling orders:

```bash
uv run alpha paper ibkr-preflight SPY.ARCA --asset-class etf
```

`alpha provider check ibkr` reports Docker CLI, daemon, reviewed image digest, masked DU account,
loopback port 4002 reachability, permissions, and market-data state without starting or stopping
Docker. Freeze a non-transmitting preview contract offline with:

```bash
uv run alpha paper ibkr-what-if-plan \
  --limit-price 640 --collar-low 600 --collar-high 680 \
  --expires-at YYYY-MM-DDTHH:MM:SS+00:00
```

This creates no broker connection and earns no paper-readiness credit. IBKR requires the API
`transmit` field to be true to process a what-if request; `whatIf=true` prevents order placement,
and the plan records `broker_order_transmitted=false` separately. Execute exactly once after a new
current owner checkpoint:

```bash
uv run alpha paper ibkr-what-if-execute PLAN_HASH --confirm-non-transmitting-preview
```

The executor verifies the frozen account and contract, compares SPY position before and after,
rejects order-status or execution callbacks, and writes only a redacted receipt.

For one approved equity release, take the `intent_id`, snapshot, expected/next sessions, and cutoff
from the immutable scheduler outcome/intent. Enable both flags only in that execution process:

```bash
ALPHA_PAPER_ENABLED=true ALPHA_IBKR_PAPER_ENABLED=true \
uv run alpha paper ibkr-run SPY \
  --instrument-id SPY.ARCA \
  --snapshot daily-SPY-YYYY-MM-DD \
  --expected-session YYYY-MM-DD \
  --next-session YYYY-MM-DD \
  --order-cutoff YYYY-MM-DDTHH:MM:SS+00:00 \
  --intent <64-hex-intent-id> \
  --nav 100000
```

Any argument/intent, quote, cutoff, account, position, open-order, or journal mismatch fails closed.
The first valid `ibkr-run` attempt atomically and permanently claims the intent before constructing
the broker node. Never rerun the same intent after a crash or ambiguous acknowledgement; reconcile
the account and wait for a newly generated decision intent.
`alpha paper stop SESSION_ID` requests cancellation of ALPHA-owned open DAY orders and never
flattens. `alpha paper reconcile SESSION_ID --json` reports machine state but cannot approve it.

The IBKR Paper account identifier is also held in the keychain. Load it only for the preflight or
paper process that needs it:

```bash
export ALPHA_IBKR_PAPER_ACCOUNT="$(security find-generic-password -w -s project-alpha-ibkr-paper-account)"
```

Do not store TWS/IB Gateway usernames or passwords in `.env`; use Docker secrets or a separate
keychain-backed gateway wrapper.

## 4. Dell mini deployment candidate

An i5/16-GB Dell mini is sufficient for a loopback IB Gateway container, the five-minute scheduler,
light ingestion, reconciliation, and monitoring. It is not yet an approved host and should not hold
the only canonical dataset or a large L2 archive. Before moving any process, record its exact CPU,
storage, Linux distribution, disk encryption, LAN address, SSH-key policy, backup target, Docker
version, time synchronization, and unattended-restart behavior. Keep the Mac as the development and
recovery authority until a separate multi-host operations/threat-model review is complete.

## 5. Acceptance

Run `alpha paper readiness --json`. `PaperAcceptanceV2` recomputes every predicate from immutable,
plan-bound, hash-chained typed callback facts; producer `passed` fields and legacy journal scenarios
earn no credit. `paper_passed` remains false until every separately authorized real paper scenario
is mechanically present. IBKR Paper fills are simulator observations, not evidence of live fill
quality. Futures remain research-unsupported and live-capital routing does not exist.
