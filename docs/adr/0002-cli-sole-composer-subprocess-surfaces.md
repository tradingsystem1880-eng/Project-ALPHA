# ADR-0002: `alpha_cli` is the sole composer; surfaces subprocess the CLI

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Composing the backtest engine with the validation gauntlet is the platform's most dangerous seam: it is where look-ahead, non-determinism, and inconsistent provenance could leak in if done more than one way. ALPHA also ships two interactive surfaces — an MCP server (`alpha_mcp`) and a local web IDE (`alpha_web`) — that need to *drive* the research loop. The naïve approach is to import the engine and gauntlet into each surface and call them directly. That would (a) duplicate the delicate composition logic in three places, (b) drag nautilus/Cython + a multiprocessing pool into long-lived server processes, and (c) create three subtly different code paths whose results could diverge.

## Decision

Make **`alpha_cli` the single composition layer** — the only package the DAG permits to touch both the engine (`alpha_backtest`) and the gauntlet (`alpha_validation`). Every run produces a **byte-stable JSON manifest** in the run store.

The surfaces **compose nothing**. `alpha_mcp` and `alpha_web` invoke the `alpha` console script as a **subprocess**, parse the `-> run <id>` token from stdout, and read the manifest the CLI wrote back from the store. The CLI is the single source of truth; the surfaces are thin, additive presentation/transport layers over the same artifacts.

**Code anchors:**
- `apps/alpha-mcp/src/alpha_mcp/_invoke.py:run_alpha` — `subprocess.run(["alpha", *args], …, check=False)`, passes `ALPHA_DATA_DIR` via env, parses the run id (`_RUN_ID_RE`), reads the manifest, fails loud on non-zero exit / missing manifest.
- `apps/alpha-web/src/alpha_web/_invoke.py:launch` / `event_stream` — `subprocess.Popen`, tails stdout on a daemon thread, streams lines as SSE, parses the run id on the fly.
- Import-linter contracts 6 & 7 (root `pyproject.toml`) — nothing imports `alpha_mcp` or `alpha_web`.
- The lazy engine imports inside `apps/alpha-cli/src/alpha_cli/_runner.py:run_full_backtest` keep nautilus out of import paths that don't need it.

## Options Considered

### Option A: CLI composes; surfaces subprocess the CLI (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Low — one composition path; surfaces just spawn + parse |
| Cost | A subprocess fork per action (negligible vs a backtest/gauntlet run) |
| Correctness-risk | Low — one code path, one provenance, identical results everywhere |
| Fit | Excellent — surfaces stay additive; CLI stays authoritative |

### Option B: surfaces import the engine/gauntlet directly

| Dimension | Assessment |
|---|---|
| Complexity | High — composition logic duplicated and re-validated per surface |
| Cost | nautilus/Cython + process pool loaded into every server process |
| Correctness-risk | High — three drifting code paths; multiprocessing inside a server is fragile |
| Fit | Poor — collapses the "only the CLI composes" invariant |

### Option C: extract a shared in-process service library both surfaces import

| Dimension | Assessment |
|---|---|
| Complexity | Medium — a new package + a new public API surface to keep stable |
| Cost | Still loads the heavy stack in-process; more packages to version |
| Correctness-risk | Medium — better than B, but two callers can still diverge in usage |
| Fit | Medium — plausible later, but heavier than the loop currently needs |

## Trade-off Analysis

The only real cost of subprocessing is a process fork and stdout parsing per action — trivially small next to the runtime of an actual backtest or gauntlet, and it buys complete isolation of the heavy, occasionally-deadlock-prone (Cython/multiprocessing) stack from the user-facing servers. It also gives both surfaces *identical* results for free, because they literally run the same binary the user would. A shared service library (C) is the natural escape hatch if a future surface needs sub-fork-latency interactivity, but nothing today does, and it would re-import the heavyweight stack into the server. Direct imports (B) are rejected outright: they reintroduce the multi-path divergence and in-process fragility this decision exists to prevent.

## Consequences

- **Easier:** trusting that the MCP tool, the web "New run" button, and a hand-typed `alpha …` command all produce the same manifest; adding a new surface (wrap the same CLI).
- **Harder:** a surface that wants streaming *structured* intermediate state must parse stdout or poll the manifest, not call a function. (Acceptable for the current loop.)
- **Revisit when:** a surface needs interactive, sub-process-fork-latency control of a run — at which point promote the composition into a shared in-process service (Option C) while keeping the CLI as the reference implementation.
