# Owner-actions checklist

Everything in this repo that needs the owner's own hands: credentials, OAuth, approvals, and
opt-ins that an agent cannot and should not do for you. It is a register, not a to-do list —
several rows are deliberately left undone.

**Never paste a secret into a repository file, a commit message, or an agent session.** Every
row below names variables and services only. Values belong in the macOS keychain or in the local
git-ignored `.env` (mode `0600`), and are exported into the single process that needs them.

Verified against this machine on 2026-08-19; the "verify" column is the command that re-checks
the row.

## Credentials — the keychain launcher is the canonical path

`scripts/alpha-with-keychain-provider <provider> <action>` reads one named keychain item, exports
it into exactly one child process, and drops it. Nothing lands in `.env`, no value reaches shell
history, and an agent can run the launcher without ever seeing the secret. Use it in preference
to exporting anything by hand.

```bash
scripts/alpha-with-keychain-provider tiingo check
```

| Provider | Keychain service | Variable | What it unlocks | Verify |
|---|---|---|---|---|
| Tiingo | `project-alpha-tiingo` | `ALPHA_TIINGO_API_KEY` | authoritative stock/ETF EOD — the receipt→candidate→quality→canonical promotion path, and the daily scheduler | `scripts/alpha-with-keychain-provider tiingo check` |
| QuantPad | `project-alpha-quantpad` | `QUANTPAD_API_KEY` | research-only bulk daily bars (`rd_` dataset registration) and the archive lane | `scripts/alpha-with-keychain-provider quantpad check` |
| CoinGecko | `project-alpha-coingecko` | `ALPHA_COINGECKO_API_KEY` | crypto reference/catalog acquisition | `scripts/alpha-with-keychain-provider coingecko check` |
| Finnhub | `project-alpha-finnhub` | `ALPHA_FINNHUB_API_KEY` | `alpha screener quote/news` | `scripts/alpha-with-keychain-provider finnhub quote` |
| IBKR | `project-alpha-ibkr-paper-account` | `ALPHA_IBKR_PAPER_ACCOUNT`, `ALPHA_IBKR_GATEWAY_IMAGE`, `TWS_USERNAME`, `TWS_PASSWORD` | native IBKR Paper boundary | `uv run alpha provider check ibkr` |

`alpha provider check` is registered for `tiingo`, `quantpad`, `coingecko`, and `ibkr`, and writes
a redacted `ProviderCheckReceiptV1` under `data_dir`. Finnhub has no receipted readiness
path, so the launcher rejects `finnhub check` with exit 64 rather than pretending. Use
`finnhub quote` instead: it is a bounded live probe — fixed provider, fixed SPY symbol, no
arguments accepted — so it verifies the credential without becoming a general data tool.

`yfinance`, `ccxt`, `stooq`, `binance`, `bybit`, `geckoterminal`, and `coinmetrics` need no
credential and already report `configured: true`.

**All five keychain items exist on this machine** (verified 2026-08-19 by metadata read, no
values seen). Tiingo, QuantPad and the IBKR account were created 2026-08-04 with account
`project-alpha`; CoinGecko 2026-08-14 and Finnhub 2026-08-19 with account `hunternovotny`. The
launcher looks items up by *service* only, so the inconsistent account names are harmless — but
match the existing account when you update an item, or you will create a second one beside it.

Nothing is missing. Providers report `configured: false` only because a plain shell has not
exported anything; the launcher is what makes them configured, per-process.

**All four credentialed data providers were verified live on 2026-08-19** — Tiingo, QuantPad
and CoinGecko each returned `verified` with a fresh receipt, and Finnhub returned a live SPY
quote. IBKR returned `connectivity_failed`; see below.

### Finnhub — the key is exposed and the owner has accepted that

A Finnhub API key was pasted in plaintext into an agent session on 2026-08-19. It is in the
session transcript and in the on-disk session JSONL, so it must be treated as public. No agent
used it and none will.

**The owner was told and chose not to rotate it (2026-08-19).** That is a reasonable call for
this key specifically — Finnhub here is read-only market data on a free tier, the blast
radius is quota theft rather than trading or account access, and nothing else in ALPHA
depends on it. It is recorded rather than silently dropped so the decision is visible if the
key is ever upgraded to a paid tier, where the calculus changes.

To rotate later: replace it at finnhub.io, then overwrite the item yourself. The
`project-alpha-finnhub` item already exists (created 2026-08-19, account `hunternovotny`), so
this is an **update** — `-U` overwrites in place, and matching `-a` keeps it to one item:

```bash
security add-generic-password -U -a hunternovotny -s project-alpha-finnhub -w "<NEW-ROTATED-KEY>"
```

Verify with the launcher, which injects the key into one process and prints no secret:

```bash
scripts/alpha-with-keychain-provider finnhub quote
```

**Reading or writing a keychain *value* is always yours.** `.claude/settings.json` denies
`security add-generic-password`, `security delete-generic-password`, `security dump-keychain`,
and every `find-generic-password -w` form. Agents may read item *metadata* only:

```bash
security find-generic-password -s project-alpha-tiingo
```

### IBKR — preview before any release

The what-if lane exists so the paper boundary can be exercised without releasing an order:

```bash
uv run alpha provider check ibkr --json
uv run alpha paper ibkr-what-if-plan --json
uv run alpha paper ibkr-what-if-execute --json
```

`ibkr-what-if-execute` writes a preview receipt; `alpha paper ibkr-run` is the only command that
releases a real paper order and is denied to agents outright.

**Checked 2026-08-19: `connectivity_failed`, because Docker is not running.** The receipt reads
`docker_cli: true, docker_daemon: false` — the CLI is installed but the daemon is down, so the
gateway container cannot start. Start Docker Desktop and re-run the check. Two owner review
items are also still open in the same receipt and no agent can clear them:
`image_digest_reviewed: false` and `signed_local_app_reviewed: false`.

### Bulk crypto storage — configured and verified

The QuantPad archive and crypto acquisition lanes write to an external volume and fail closed if
it is absent, full, or a different disk. Verified 2026-08-19 from the main checkout:

- `/Volumes/Expansion/Project-ALPHA/crypto-data` is mounted, 1.8 TiB free (3% used).
- `ALPHA_BULK_VOLUME_UUID` is set and **matches the mounted volume's UUID**, which is the check
  that matters — the store compares them on every publish, so a same-path replacement disk is
  rejected rather than silently written to.

Nothing to do unless the drive is swapped, in which case update the setting to the new UUID:

```bash
diskutil info /Volumes/Expansion | grep 'Volume UUID'
```

## Approvals

| What | Why it matters | How | Verify |
|---|---|---|---|
| Claude Code project MCP servers | `~/.claude.json` has `enabledMcpjsonServers: []` for the repo root and every worktree, and the root has `hasTrustDialogAccepted: false`. This is why the `codex` MCP tools attach and then drop mid-session. | In an interactive `claude` session in the repo, accept the trust dialog and run `/mcp` to enable `alpha` and `codex` | `/mcp` lists both as connected |
| Codex project trust | lets Codex run in this directory without re-prompting | already set — `trust_level = "trusted"` for `/Users/hunternovotny/Desktop/Project-ALPHA` in `~/.codex/config.toml` | `grep -A2 'Project-ALPHA' ~/.codex/config.toml` |
| Codex ChatGPT login | the optional second-model seam | see `codex-second-model-runbook.md` | `python3 scripts/codex_bridge.py probe` |
| claude.ai connectors (Linear, Slack, Notion, …) | 14 plugin MCP servers await OAuth | authorize in claude.ai connector settings, or `/mcp` in an interactive session | those tools stop reporting as unauthenticated |

## Opt-ins currently off (deliberately)

| Flag | Unlocks | Note |
|---|---|---|
| `ALPHA_PAPER_ENABLED=true` | public Binance data + local Nautilus sandbox orders | never a live-capital route |
| `ALPHA_IBKR_PAPER_ENABLED=true` | native IBKR Paper intent release (needs `ALPHA_PAPER_ENABLED` too) | loopback port + DU account only; live ports are rejected |

Set these only in the one command that needs them — never in `.env`, never exported into a shell
that launches an agent. **Verify:** `uv run alpha info system --json`.

## Deliberately deferred

**Owner token — deliberately left unset; the logbook is the chosen control.**
Configuring `ALPHA_OWNER_TOKEN` would gate `gate.py override|ack|baseline` behind a secret you
would have to manage, and it carries a trap: **the hooks read the environment of the shell that
launched Claude Code**, so exporting it in that terminal hands the *agent* owner authority —
hidden-holdout reads, ack-free protected edits, config-change bypass — which is strictly worse
than leaving it unset.

With it unset, every escape is agent self-serve and every one is recorded in the hash-chained
journal at `.claude/state/harness-audit.jsonl` as
`authorized_by: agent (owner token not configured)`. Read it with:

```bash
uv run python scripts/gate.py audit --digest
```

One screen: escapes rolled up by the file they touched, what the harness blocked, config changes,
Codex calls, and a chain-integrity line. `--since ISO` widens or narrows the window (default 7
days). The session brief prints the escape count with the same command as the pointer, and
`gate.py audit --verify` re-hashes the whole chain. Counts and paths only — the journal never
records file contents.

**Branch push / PR.** `claude/blissful-edison-00b74b` has no upstream and has never been pushed.
That is intentional; push and open the PR from the main session, not from a fork.

## Environment gotchas

- **Worktrees do not inherit `.env` or `data/`.** `AlphaSettings` reads `env_file=".env"`
  relative to the current directory, so a worktree reports zero configured providers and
  `data_dir exists: false` even when the main checkout at `~/Desktop/Project-ALPHA` is fully set
  up. Run provider/system checks from the main checkout before believing something is broken.
- **The harness only exists where this branch is checked out.** `.claude/` and `scripts/` are
  tracked files on this branch and absent from `main`. A Claude session rooted at a worktree on
  `main` therefore has no hooks *and* no permission allowlist, so ordinary commands fall through
  to the auto-mode classifier and get refused far more often — which reads as "Claude cannot do
  anything" but is the opposite: it is the harness being missing, not present. Merging this
  branch to `main` is what makes the expanded permissions apply everywhere. Until then, work from
  a worktree on this branch, and check with `ls .claude/settings.json scripts/claude_hooks.py`.
- **Check for a live escape token before trusting a commit gate.** `gate.py audit --digest`
  prints a `LIVE` block when a one-shot `override`/`ack` is armed but unused; an override armed
  for a commit that never happened fires silently on the next one. Drop a stale one with
  `uv run python scripts/gate.py ack --clear` (or `override --clear`), which records the drop
  in the journal — deleting the state file by hand leaves the journal implying it is still armed.
- **`/usr/bin/python3` is 3.9** and has no `tomllib`. Stdlib-only harness scripts must run under
  `.venv/bin/python -S`.
- **`.claude/state/mutation/` holds ~329 MB** of leftover mutation-testing staging in the
  harness worktree. It is git-ignored and safe to delete when you want the disk back; nothing
  reads it between runs.
