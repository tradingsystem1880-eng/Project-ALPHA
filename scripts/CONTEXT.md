---
owner: development tooling
sources:
  - scripts/gate.py
  - scripts/gate_components.py
  - scripts/gate_select.py
  - scripts/gate_preflight.py
  - scripts/fs*.py
  - scripts/commands_reference.py
  - scripts/roadmap_index.py
verified: 0377681b
---

# scripts workspace

## Purpose

The developer and CI tooling: the gate (`gate.py`: the fast local check, CI job steps, quant
sweeps), test selection, the file-system tools (`fs.py orient|search|stale`), generators for
committed documents, OpenAPI checks and the agent hooks. Scripts are top-level modules on the
mypy and pytest path, not a package; the harness scripts are standard library only. They never
read owner data, credentials or hidden tests.

## Read first

| Read | Section | When |
|---|---|---|
| [engineering rules](../docs/reference/invariants/engineering.md) | Checks and commits | always |
| [testing invariants](../docs/reference/invariants/testing.md) | Markers and tiers | always |
| [testing invariants](../docs/reference/invariants/testing.md) | Quant sweeps | changing mutation, semgrep, determinism or raise-cov |
| [documentation invariants](../docs/reference/invariants/documentation.md) | Generated files | changing a generator |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Owner authority | changing `claude_hooks.py` |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Protected and hidden tests | changing search, hooks or test selection |

## How to change it

- Protected files (change only in a reviewed pull request that lists them): `scripts/gate*.py`,
  `scripts/git_guard.py`, `scripts/harness_*.py`.
- Where things are: `gate.py` + `gate_components.py` (CI job steps) + `gate_select.py` (tests mapped
  from changed files); `fs.py` with `fs_orient.py`, `fs_search.py`, `fs_stale.py`; generators
  `roadmap_index.py`, `commands_reference.py`, `generate_web_openapi.py`, `check_openapi_operations.py`.
- Tests: `tests/unit/test_gate_*.py`, `test_git_guard.py`, `test_fs_*.py`, `test_roadmap_index.py`,
  `test_commands_reference.py`, `test_claude_harness_*.py`, `test_mutation_*.py` (all in `tests/unit/`).
- Check: `uv run python scripts/gate.py check` (its mypy step covers the harness scripts listed in
  `gate.HARNESS_SCRIPTS`; a new script is type-checked through its test's import).
- Every generator has a `--check` mode and a freshness test; keep that pattern for new ones.

## Outputs

- A unit test for every new script or subcommand, with throwaway git repositories where it reads git.
- Regenerated outputs committed with the change (`docs/roadmap/README.md`, `docs/reference/commands.md`).
- The owning document: `docs/reference/invariants/testing.md` for the gate and sweeps;
  `docs/reference/invariants/documentation.md` for generators.
