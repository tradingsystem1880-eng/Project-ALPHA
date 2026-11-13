---
owner: rd-agent worker
sources:
  - workers/rdagent/*.py
  - workers/rdagent/pyproject.toml
  - workers/rdagent/uv.lock
verified: 0377681b
---

# RD-Agent worker workspace

## Purpose

Flat entry scripts and pinned locks that run Microsoft RD-Agent's native loops (synthetic
fixtures, rule and costed probes, the stock RDLoop) in their own environments for the CLI's
native job supervisor. It is a separate uv project (`package = false`) with its own lock; no ALPHA
package imports it, though its probes import ALPHA packages inside qualified profile
environments. It has no market, inference or evidence authority.

## Read first

| Read | Section | When |
|---|---|---|
| [worker invariants](../../docs/reference/invariants/workers.md) | Shared rules | always |
| [worker invariants](../../docs/reference/invariants/workers.md) | RD-Agent worker | always |
| [command line native](../../docs/reference/invariants/cli-native.md) | — | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | changing what a native result may claim |

## How to change it

- Code: the scripts in `workers/rdagent/` and the lock files beside them.
- Tests live in the root suite: `tests/unit/test_native_*.py`. Tests that need the RD-Agent source
  skip unless `ALPHA_RDAGENT_SOURCE` (and, for stock lanes, `ALPHA_STOCK_PYTHON`) is set.
- There is no CI gate component for this worker; run `uv run python scripts/gate.py check` from
  the repository root.
- Editing `alpha_core`, `alpha_patterns` or `alpha_strategies` source changes the installed rule
  profiles' measured environment; rebuild them (see the native file).

## Outputs

- Root tests under `tests/unit/test_native_*.py`.
- The owning document: `docs/reference/invariants/workers.md` § RD-Agent worker.
