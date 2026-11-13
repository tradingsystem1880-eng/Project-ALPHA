# Restructure the flat alpha_cli package into subpackages

**Risk:** H

## Scope

`apps/alpha-cli/src/alpha_cli/` has 172 top-level modules (84,205 lines, 2026-11-14) and one subpackage
(`figures/`, 3 modules). `main.py` registers 25 sub-apps by module-path strings
(`("crypto-data", "alpha_cli.crypto_data_cmds", ...)`); `-m` entry points include
`alpha_cli.main`, `alpha_cli.comparison_acquisition_worker` and `alpha_cli.native_qlib_pipeline`.

## Why

A flat package of 172 modules has no visible structure; ownership and layering inside the CLI are
implicit.

## Invariants at risk

- String-registered sub-apps and `-m` module paths break silently if modules move.
- `_identity.execution_fingerprint` hashes every `alpha_cli` file with its package-relative path as
  the label, so relocating any module changes every new run's execution fingerprint.
- Import-linter contracts reference module paths.

## Proof required before/after

- Before: an ADR deciding the package layout and accepting the fingerprint change; a test that
  imports every string-registered sub-app and `-m` target.
- After: that test passes; CLI help output (`alpha --help` tree) is unchanged; `scripts/fs.py orient
  --component alpha-cli` shows only path changes; import-linter passes; CI passes.

## Suggested slicing

1. Write the ADR and the registration test.
2. Move one domain (for example `crypto_*`) into a subpackage with re-export shims.
3. Repeat per domain; drop shims last.
