# Owner-actions checklist

Everything in this repo that needs the owner's own hands: credentials, OAuth, approvals, and
opt-ins that an agent cannot and should not do for you. It is a register, not a to-do list —
several rows are deliberately left undone.

**Never paste a secret into a repository file, a commit message, or an agent session.** Every
row below names variables and services only. Values belong in the macOS keychain or in the local
git-ignored `.env` (mode `0600`), and are exported into the single process that needs them.

Verified against this machine on 2026-08-19; the "verify" column is the command that re-checks
the row.

## Credentials — all currently unset

`alpha info providers --json` reports `configured: false` for these. `yfinance`, `ccxt`,
`stooq`, `binance`, `bybit`, `geckoterminal`, and `coinmetrics` need no credential and already
report `configured: true`.

| Provider | Variable(s) | What it unlocks | Without it |
|---|---|---|---|
| Tiingo | `ALPHA_TIINGO_API_KEY` | authoritative stock/ETF EOD — the receipt→candidate→quality→canonical promotion path, and the daily scheduler | no authoritative equity history; Yahoo/Stooq stay comparison-only |
| Finnhub | `ALPHA_FINNHUB_API_KEY` | `alpha screener quote/news` | screener commands fail loud |
| QuantPad | `QUANTPAD_API_KEY` | research-only bulk daily bars (`rd_` dataset registration) | research data plane limited to what is already snapshotted |
| CoinGecko | `ALPHA_COINGECKO_API_KEY` | crypto reference data | that provider stays unconfigured |
| IBKR | `TWS_USERNAME`, `TWS_PASSWORD`, `ALPHA_IBKR_PAPER_ACCOUNT`, `ALPHA_IBKR_GATEWAY_IMAGE` | native IBKR Paper boundary | `ibkr-preflight`/`ibkr-run` unavailable |

`docs/operations/README.md` says the Tiingo, QuantPad, and IBKR-account values are held in the
macOS keychain services `project-alpha-tiingo`, `project-alpha-quantpad`, and
`project-alpha-ibkr-paper-account`, and loaded per-process, e.g.

```bash
export ALPHA_TIINGO_API_KEY="$(security find-generic-password -w -s project-alpha-tiingo)"
```

**UNVERIFIED:** whether those keychain entries actually exist on this machine — keychain access
is blocked in agent sessions, by design. Check it yourself with (prints metadata, not the value):

```bash
security find-generic-password -s project-alpha-tiingo
```

If they exist, nothing is missing; the providers simply report unconfigured until a process
exports them. If they do not, obtaining the tokens is the first real task.

**Verify:** `uv run alpha info providers --json` — `configured` flips to `true` in any shell that
has exported the variable.

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

**Owner token — left unconfigured, by decision.** `gate.py override|ack|baseline` would require
`ALPHA_OWNER_TOKEN` whose sha256 matches `.claude/owner.local.json` (created by
`uv run python scripts/gate.py owner-init`, interactive, once). Until then every escape is
agent self-serve, audited as `authorized_by: agent (owner token not configured)`, and flagged in
the statusline, the session brief, and `doctor`. That is the current state and it is fine: the
audit trail is complete either way.

If you ever do configure it, note the trap: **the hooks read the environment of the shell that
launched Claude Code.** Exporting `ALPHA_OWNER_TOKEN` in that terminal hands the *agent* owner
authority — hidden-holdout reads, ack-free protected edits, config-change bypass — which is
strictly worse than leaving it unset. Export it only in your own separate shell where you run
`gate.py` by hand.

**Branch push / PR.** `claude/blissful-edison-00b74b` has no upstream and has never been pushed.
That is intentional; push and open the PR from the main session, not from a fork.

## Environment gotchas

- **Worktrees do not inherit `.env` or `data/`.** `AlphaSettings` reads `env_file=".env"`
  relative to the current directory, so a worktree reports zero configured providers and
  `data_dir exists: false` even when the main checkout at `~/Desktop/Project-ALPHA` is fully set
  up. Run provider/system checks from the main checkout before believing something is broken.
- **`/usr/bin/python3` is 3.9** and has no `tomllib`. Stdlib-only harness scripts must run under
  `.venv/bin/python -S`.
- **`.claude/state/mutation/` holds ~329 MB** of leftover mutation-testing staging in the
  harness worktree. It is git-ignored and safe to delete when you want the disk back; nothing
  reads it between runs.
