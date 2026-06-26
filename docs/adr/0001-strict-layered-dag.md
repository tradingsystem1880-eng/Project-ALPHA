# ADR-0001: Strict layered DAG enforced by import-linter

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Project ALPHA is written and maintained entirely by AI agents working across many sessions. The single largest reliability risk for agent-written code is **architectural drift**: a convenient import added in one session quietly couples layers that should stay independent, and by the time it's noticed the dependency graph is a ball of mud. The platform also has a hard correctness requirement — only one layer may compose the backtest engine with the validation gauntlet — that is meaningless if any module can reach across the graph at will.

We need the dependency graph to be a property the toolchain *checks*, not a guideline a reviewer hopes everyone remembers.

## Decision

Model the platform as a `uv` workspace of small `src/`-layout packages and enforce a **strict acyclic dependency DAG as a CI gate** using [`import-linter`](https://import-linter.readthedocs.io/). The graph: `alpha_core` ← `alpha_data` ← `alpha_backtest`; `alpha_strategies` and `alpha_validation` depend on `alpha_core` only; `alpha_cli` may import everything; `alpha_mcp` and `alpha_web` sit atop the DAG and nothing imports them.

Seven `[tool.importlinter]` **forbidden** contracts in the root `pyproject.toml` encode this:

1. `alpha_core` imports nothing internal.
2. `alpha_data` depends only on core.
3. `alpha_strategies` depends only on core.
4. `alpha_validation` depends only on core.
5. `alpha_backtest` depends only on core + data.
6. `alpha_mcp` sits atop the DAG (nothing imports it).
7. `alpha_web` sits atop the DAG (nothing — including `alpha_mcp` — imports it).

These run as the **`Architecture`** step (`uv run lint-imports`) in `.github/workflows/ci.yml`, positioned between `ruff format --check` and `mypy`.

**Code anchors:** root `pyproject.toml` `[tool.importlinter]` (7 contracts) and `[dependency-groups].dev` (`import-linter>=2.1`); `.github/workflows/ci.yml` (`Architecture` step); per-package `pyproject.toml` `dependencies`.

## Options Considered

### Option A: import-linter contracts as a CI gate (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Low — declarative TOML contracts; no custom tooling |
| Cost | Negligible — one fast CI step; one dev dependency |
| Correctness-risk | Low — boundaries are mechanically verified every push |
| Fit | Excellent — turns the #1 agent failure mode into a hard error |

### Option B: convention only (documented in CLAUDE.md, reviewed by eye)

| Dimension | Assessment |
|---|---|
| Complexity | Lowest — nothing to configure |
| Cost | Zero up front, high later (drift is expensive to unwind) |
| Correctness-risk | High — nothing stops an agent adding a cross-layer import |
| Fit | Poor — relies on perfect vigilance across many agent sessions |

### Option C: a single flat package (no boundaries)

| Dimension | Assessment |
|---|---|
| Complexity | Low to start, high at scale (everything reachable from everything) |
| Cost | Low packaging cost; high reasoning cost |
| Correctness-risk | High — the "only the CLI composes engine+gauntlet" rule can't be expressed |
| Fit | Poor — abandons the reliability lever entirely |

## Trade-off Analysis

The contracts cost a few minutes of setup and a small ongoing tax: a genuinely new cross-layer need requires either routing through `alpha_cli` or consciously editing a contract (which shows up in review as an architectural change, exactly as intended). That friction is the feature — it converts silent coupling into a visible, reviewable decision. Convention-only (B) is strictly dominated for an agent-built codebase: the failure mode it leaves open is precisely the one agents trigger most. A flat package (C) cannot even *state* the engine/gauntlet composition rule.

## Consequences

- **Easier:** reasoning about any package in isolation (its imports are bounded and known); onboarding a new agent session (the DAG is a hard contract, not lore); preventing cycles.
- **Harder:** adding a cross-layer dependency on a whim — it must go through `alpha_cli` or be an explicit contract edit. (Intended.)
- **Revisit when:** a new top-of-DAG surface is added (extend with an eighth/ninth "nothing imports it" contract), or a package legitimately needs to split. Keep declared `dependencies`, real imports, and contracts in agreement — all three are currently consistent.
