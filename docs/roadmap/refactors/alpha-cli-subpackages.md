# Restructure the flat alpha_cli package into subpackages

**Risk:** H

## Scope

`apps/alpha-cli/src/alpha_cli/` has 174 top-level modules and one subpackage (`figures/`, 3
modules), 87,567 lines (2026-11-14, main at `89c7706c`). By prefix: 30 `*_cmds`, 20 `_native_*`,
20 `research_*`, 19 `crypto_*`/`_crypto_*`, 7 `ml_*`/`_ml_*`, 7 `investigation_*`, 7 paper and
IBKR, 5 each `native_*`, `assistant_*`, `codex_*`, and about 40 others. `main.py` holds the one
command registry (`GROUPS`, 23 sub-apps, and `COMMANDS`) as module-path strings; `-m` targets are
`alpha_cli.main`, `alpha_cli.comparison_acquisition_worker` and `alpha_cli.native_qlib_pipeline`.

## Why

A flat package of 174 modules shows no structure: which modules belong together, and which are the
public seams, is only learnable by reading imports.

## What moving a module touches

- **Public seams.** `alpha_web` imports 15 `alpha_cli` modules (`run_store`, `durable_lease`,
  `paper_store`, `run_projection`, `job_capacity`, `artifact_contract`, `catalog`, `suite_catalog`,
  `run_context`, `owner_auth`, `ml_contract`, `paper_readiness`, `investigation_workspace_contracts`,
  `figure_cache`, `assistant_contracts`); `alpha_mcp` imports 7 of them. The import-linter
  contracts in `pyproject.toml` name these paths, and `owner_auth` carries the one
  `ignore_imports` exception (ADR-0030).
- **Approval binding.** The 40 `DAILY_GUARD_FILES` are looked up as flat names next to
  `_native_rule_environment.py` (`Path(__file__).with_name(name)`, which refuses a subpath), and the
  four research modules are hashed under the label `alpha_cli/<name>.py`. Moving any of these 43
  files means editing `_native_rule_environment.py` or `research_cmds.py`, and invalidates every
  daily-rule approval (any move) or research approval (if the label or import changes).
- **Run identity.** `_identity.execution_fingerprint` labels each file by its package-relative path,
  so every move changes new runs' execution fingerprint (as any `alpha_cli` edit does).
- **Tests.** 294 test files import `alpha_cli` modules by path, and many patch module
  attributes by string.

## Plan: small steps

1. **ADR** deciding the layout by domain (`research/`, `crypto/`, `native/`, `ml/`, `paper/`,
   `commands/`, `store/`), which modules are public seams, and that approval-bound modules stay flat
   until the owner chooses a renewal window.
2. **A registry test** that imports every `GROUPS`/`COMMANDS` entry and every `-m` target by its
   string, so a move that forgets a string fails fast.
3. **Move one unbound domain per change** with no re-export shims (update importers in the same
   change; shims would double the module count): start with leaf domains that only commands import
   (`investigation_*`, `assistant_*`, `codex_*`). Proof: the registry test, `alpha --help` output
   identical before and after, `lint-imports`, `gate.py check --all`, smoke. Invalidates nothing but
   run fingerprints.
4. **Bound modules last, in the same renewal window as the control-store split**, with the binding's
   name lookup changed to accept the new paths.

## Recommendation

Do not start now. The payoff (navigation) is smaller than the cost: every move touches tests and
import strings across the suite and conflicts with the 34 waiting features, 29 of the 174 modules
cannot move without an approval renewal, and the size limit already stops the package's files from
growing. Instead, put new modules for a feature into a domain subpackage from the start (step 1's
ADR makes that the rule), and move an existing domain only when a feature is already rewriting most
of it. Revisit after the control-store split, when the store's own new modules show the layout.
