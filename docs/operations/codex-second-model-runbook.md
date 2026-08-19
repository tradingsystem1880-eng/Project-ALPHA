# Codex second-model runbook

Codex is an **optional** second model attached to the harness for code review and source-checked
research. Nothing in this repo depends on it: every gate, hook and CI job passes with Codex
uninstalled, logged out, rate-limited or timing out. If you only want the gates to be green, you
can stop reading here.

Authentication is **ChatGPT OAuth**, not an API key. No OpenAI key is ever stored in this repo,
in `.env`, or in the keychain for this purpose.

## 1. Log in (and re-log in)

The OAuth flow opens a browser and needs your ChatGPT credentials, so it is always run by the
owner, in a normal terminal — never inside an agent session.

```bash
codex logout && codex login && codex login status
```

`codex login` prints a URL and waits; approve in the browser, and `login status` should end with
a line containing `Logged in using ChatGPT`. That exact substring is what the harness looks for
(`gate.codex_probe`, `scripts/gate.py` — it matches `logged in` and rejects `not logged`), so
a successful re-login needs no repo change.

Re-login is the fix for essentially every Codex problem. It is safe to run at any time; it
touches only `~/.codex/`.

## 2. Where the credentials live

| Thing | Path | Notes |
|---|---|---|
| Auth | `$CODEX_HOME/auth.json` | `CODEX_HOME` defaults to `~/.codex`. Holds `auth_mode: chatgpt`, an access token, an id token, a refresh token, and `last_refresh`. `OPENAI_API_KEY` is null. |
| Model list | `$CODEX_HOME/models_cache.json` | Written by the CLI. The bridge refuses a model that is absent from it. |
| Global config | `$CODEX_HOME/config.toml` | Default model, reasoning effort, and per-project `trust_level`. |
| Project config | `.codex/config.toml` (this repo) | Registers the `alpha` and `quantpad-data` MCP servers for interactive Codex sessions. |

None of these are in the repository, and none should ever be copied into it. Refresh is
automatic: the CLI rotates the access token using the refresh token and updates `last_refresh`.
You do not refresh anything by hand.

## 3. Model resolution

`--model` > `$ALPHA_CODEX_MODEL` > `gpt-5.3-codex-spark` (`resolve_model`,
`scripts/codex_bridge.py:84`). Whatever wins **must appear in `models_cache.json`**, otherwise
the bridge reports `unavailable: model '<name>' not in models cache (...)` and lists what is
available. Reasoning effort defaults to `xhigh`.

If you change the default model in `~/.codex/config.toml`, the bridge does *not* follow it — set
`ALPHA_CODEX_MODEL` instead, or pass `--model`.

## 4. The two entry points

**`scripts/codex_bridge.py`** — the harness-attached, non-interactive seam. Stdlib only, always
prints one JSON object, always exits 0.

```bash
python3 scripts/codex_bridge.py probe
python3 scripts/codex_bridge.py review --uncommitted
python3 scripts/codex_bridge.py review --diff /path/to/some.diff
python3 scripts/codex_bridge.py research --question "..."
```

Every call runs `codex exec` with `--ephemeral`, sandbox `read-only`, and an output JSON schema
from `scripts/schemas/`, under a wall-clock cap (review 900 s, research 600 s). Diffs are capped
at 200 000 bytes and prompt-injection patterns in the reviewed text are neutralised before the
model sees them.

**`.mcp.json` `codex` server** — the interactive path, for talking to Codex from a Claude Code
session as MCP tools. Unrelated to the bridge; it needs the project MCP servers to be enabled
(see `owner-actions-checklist.md`).

## 5. Verify

```bash
codex login status
python3 scripts/codex_bridge.py probe
uv run python scripts/gate.py doctor
```

Expected: `login status` says logged in using ChatGPT; `probe` prints
`{"available": true, "model": "gpt-5.3-codex-spark", ...}`; `doctor` shows an `ok` row for
`codex second model`. For an end-to-end check that actually calls the model, run
`python3 scripts/codex_bridge.py review --uncommitted` on a branch with real changes and confirm
you get `"available": true` with a `findings` list.

To check the MCP path instead, start a Codex session and run `/mcp`.

## 6. When it is unavailable

Every failure mode below produces `available: false`, an `unavailable:<reason>` string, and
**exit code 0**. Nothing blocks, nothing retries automatically, and no gate changes result.

| Symptom in the reason string | Cause | Fix |
|---|---|---|
| `codex CLI not on PATH` | not installed | install the Codex CLI |
| `codex present but not logged in` | logged out, or refresh token revoked/expired | re-login (§1) |
| `codex login status failed` | CLI crashed or hung past 20 s | re-run; then re-login |
| `model '<x>' not in models cache` | model renamed/retired, or cache stale | run any `codex` command to refresh the cache, or pick a listed model |
| `codex exceeded <n>s wall-clock cap` | slow or oversized request | raise `--timeout`, or shrink the diff |
| `codex exit <n> without output` | quota, rate limit, or transport error | wait and retry; check `codex login status` |
| `codex output was not the <kind> schema` | model returned malformed JSON | retry; if persistent, lower effort or shrink input |

Because unavailability is never an error, a silently-logged-out Codex looks exactly like "no
second opinion was offered". If you expect review findings and get none, run `probe` first.
