# Design — `alpha-web`: a local web IDE over Project ALPHA (QuantPad parity Phase 4)

## Context

The final QuantPad-parity surface: a **local web IDE**. Phases 1–3 gave ALPHA a Verdict, a
prop-firm simulator, and a conversational MCP server; Phase 4 puts a **browser GUI** on the same
research loop so a run can be configured, launched, watched live, and explored without the
terminal. It stays **$0 / local / single-user** and, like the MCP server, is **purely additive**:
it shells out to the installed `alpha` CLI and reads the byte-stable artifacts the CLI writes. It
sits atop the import DAG (nothing imports it).

This is the last of the four phases (1 = Verdict #8, 2 = prop-firm #9, 3 = MCP #10).

## Decisions (user-approved)

- **Full IDE** scope: run browser, a configurable new-run form (the "param editor"), a **live
  streaming run console**, run detail (manifest + embedded tear sheet + equity chart), and a
  **command console** ("agent" panel).
- **Server-rendered**: FastAPI + Jinja2 templates + **HTMX** (and the HTMX SSE extension for live
  output). No build step, one language, easy for an AI agent to maintain.
- **Subprocess integration**: endpoints run `alpha <cmd>` and read back manifests — the same
  pattern as the MCP server; the CLI stays the single source of truth.

### The agent-panel / $0 tension (explicit)

A true in-app LLM agent needs an API key, which collides with the $0 ethos. So the "agent panel"
ships as a **streaming command console**: the user types an `alpha` subcommand (or picks a
suggestion) and watches it run live. The **real conversational path is the Phase-3 MCP** connected
to a Claude client — the run detail/console pages link to that setup. (An optional, opt-in
`ANTHROPIC_API_KEY`-gated true-agent mode is noted as a post-v1 enhancement, not built here.)

## Architecture

New uv workspace member `apps/alpha-web/`:

```
apps/alpha-web/
  pyproject.toml                 # name=alpha-web; deps: alpha-cli, fastapi, jinja2, uvicorn,
                                 #   sse-starlette; script: alpha-web = alpha_web.app:main
  src/alpha_web/
    __init__.py
    app.py                       # FastAPI app factory + routes + main() (uvicorn)
    _invoke.py                   # subprocess core: launch `alpha`, stream stdout, parse run id
    _runs.py                     # filesystem reads: list_runs / get_run / equity series
    templates/                   # Jinja: base, index (run browser), run_detail, new_run, console
    static/                      # a little CSS; uPlot (vendored) for the equity chart
```

### Routes (HTMX, server-rendered)

| Route | Renders / does |
|---|---|
| `GET /` | **Run browser** — table of stored runs (run_id, command, label, verdict/pass badge) from the manifests, newest first |
| `GET /runs/{run_id}` | **Run detail** — manifest summary, pass/Verdict badges, an equity chart (uPlot over `equity_curve.parquet`), and the run's `tearsheet.html` embedded in an `<iframe>` when present |
| `GET /new` | **New-run form** — pick command (backtest / validate / optim / propfirm / portfolio / cross-sectional), strategy, and params/flags (the "param editor") |
| `POST /runs` | Launch the chosen `alpha` command as a background job; return a fragment that opens the live console for that job |
| `GET /jobs/{job_id}/stream` | **SSE**: stream the subprocess stdout line-by-line; on exit, emit a final event linking to `/runs/{run_id}` (or the error) |
| `GET /console` + `POST /console/run` + its SSE | **Command console** — type any `alpha` args, stream output live (the "agent" panel) |
| `GET /api/runs/{run_id}/equity` | JSON `{ts[], equity[]}` for the chart (reads the parquet) |

### Backend cores

- **`_invoke.py`** — `launch(args) -> Job` starts `alpha <args>` with `ALPHA_DATA_DIR` in the env
  and a line-buffered pipe; `stream(job)` yields stdout lines for SSE; on completion it parses the
  `-> run <id>` token (when a `run_type` is known) so the console can link to the result. A small
  in-process `JOBS` registry maps a `job_id` to its process + captured output. Fail-loud: a
  non-zero exit streams the stderr and marks the job failed.
- **`_runs.py`** — `list_runs()` / `get_run()` over the run-type dirs (mirrors the MCP server's
  reader and `report_cmds._RUN_DIRS`); `equity_series(run_id)` reads `equity_curve.parquet` →
  `(timestamps, values)` for the chart.

All reads/writes go through `AlphaSettings().data_dir`, shared with the CLI and the MCP server.

### Determinism & isolation

The web layer adds no seeds or run logic — run ids, manifests, and determinism are entirely the
CLI's. Each launched run is its own subprocess (the engine never runs in the web process). The
server binds `127.0.0.1` only (local single-user); no auth, no external exposure.

## Testing (no network)

- **Unit** (`tests/unit/test_web_runs.py`): `_runs.list_runs/get_run/equity_series` over a temp
  store with hand-written manifests + a small parquet.
- **Unit** (`tests/unit/test_web_invoke.py`): `launch`/`stream`/run-id parse with a fake fast
  command (e.g. a tiny `python -c` instead of `alpha`) — no engine.
- **Integration** (`tests/integration/test_web_app.py`): FastAPI `TestClient` against a temp
  `ALPHA_DATA_DIR` seeded with `seed_store` — `GET /` lists a pre-created run, `GET /runs/{id}`
  renders the manifest + equity JSON, `POST /runs` launches a small backtest and the job reaches a
  terminal state linking to a real run, and the equity `GET /api/...` returns the series. Marked
  not-network.
- Full CI gate (ruff, format, `lint-imports` incl. a new "nothing imports alpha_web" contract,
  `mypy --strict`, pytest) green before each commit.

## Build order (vertical slices, TDD)

1. **Scaffold** the member (pyproject + deps + DAG contract + empty app) — `uv sync`, `alpha-web`
   entry point resolves.
2. **`_runs` + run browser + run detail** (manifest summary + embedded tear sheet + equity chart).
3. **`_invoke` + new-run form + `POST /runs` + SSE live console**.
4. **Command console** ("agent" panel) reusing the SSE console + the MCP-bridge note.
5. **Docs** (CLAUDE.md module map + build status, README "Web IDE" section, `alpha-web` launch).

## Out of scope (v1)

- In-app LLM agent (needs a key; the MCP is the conversational path). Optional opt-in mode later.
- Authoring/editing strategy **Python** at runtime (strategies are registered classes; the form
  edits parameters, not code). A code editor is a possible later enhancement.
- Multi-user, auth, remote hosting, websockets (SSE suffices for one local user).
