**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Forward configured Matplotlib configuration and cache placement to CLI children",
  "context": "Preserve independently reviewed frozen selector tree deb10cc217a7a7359f08e38a6cd4cc1542b9971e in a separate curated successor. Add only MPLCONFIGDIR to the existing default-deny web-to-CLI process environment; this is a narrow configuration contract expansion, not a general isolation boundary.",
  "assumptions": [
    {
      "statement": "Only the trusted server process environment supplies MPLCONFIGDIR; a present value may have been inherited from its launching shell.",
      "verified_by": "Inspection of _catalog._cli_environment, fixed executable argv/env launch seams and strict request models. No environment-map request input is added."
    },
    {
      "statement": "Matplotlib uses MPLCONFIGDIR for configuration and cache, and an unusable or untrusted path does not establish isolation.",
      "verified_by": "Independent source audit and generic Claude design advice. Actual Matplotlib path/cache behavior is not exercised in this source stage."
    }
  ],
  "alternatives_considered": [
    "Adding HOME/XDG variables would widen the boundary unnecessarily; only MPLCONFIGDIR is authorized.",
    "Adding a default, normalization, ownership/symlink checks or startup rejection changes the existing forwarding contract and is excluded.",
    "Replacing the browser fixture or mutating worker/model filters would not verify the original direct web-to-CLI path and is excluded."
  ],
  "pre_mortem": [
    "A configured directory can contain matplotlibrc; use a newly created empty owned writable absolute directory for actual checks, never copied owner configuration.",
    "A CWD matplotlibrc can take precedence; future renderer checks also require a verified owned CWD without that file.",
    "A passed stdlib child test proves environment propagation only, not Agg rendering, all-descendant caches, font discovery, home isolation or network isolation."
  ],
  "slices": [
    {
      "title": "Add focused public forwarding tests and the single-key production contract",
      "verify": "Installed Python 3.12 through scripts/run_owned_test.py: test-first new cases, then all test_web_invoke.py cases plus the exact safe cache import-boundary node; changed-file Ruff and strict mypy.",
      "expected": "Configured values are exact, unset remains absent, all other filters/defaults and original tests remain intact; stdlib-only fake child receives the configured valid directory.",
      "rollback": "Retain failed evidence and discard only this separate successor; preserve the frozen predecessor.",
      "files": [
        "apps/alpha-web/src/alpha_web/_catalog.py",
        "tests/unit/test_web_invoke.py"
      ],
      "status": "done"
    },
    {
      "title": "Document limits, verify scope and freeze for independent review",
      "verify": "Existing FeaturePlan validator, manual byte budget, exact-path diff checks and preservation manifest; independent frozen-source review before broader execution.",
      "expected": "Seven authorized paths only; <=6000 combined manual bytes with every prior instruction retained; original source/evidence and all 149 omissions preserved.",
      "rollback": "Preserve predecessor and all evidence; do not modify frozen candidate after review without a new identity.",
      "files": [
        "CLAUDE.md",
        "README.md",
        "docs/operations/development-loop.md",
        "docs/BUILD-STATUS.md",
        "docs/superpowers/plans/2026-11-09-web-matplotlib-environment.md"
      ],
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "README.md",
    "docs/operations/development-loop.md",
    "docs/BUILD-STATUS.md",
    "docs/superpowers/plans/2026-11-09-web-matplotlib-environment.md"
  ],
  "out_of_scope": [
    "Path validation, default paths, HOME/XDG/credential expansion, API/frontend/browser-config/selector/harness changes or worker/model filter changes.",
    "Real Matplotlib/renderer/engine/model/provider/browser workloads, broad/full gates, Atlas/preflight and protected tests.",
    "Owner data/configuration, dependency installation/resolution, network/code fetch, history recovery, commits and publication."
  ],
  "files": [
    "apps/alpha-web/src/alpha_web/_catalog.py",
    "tests/unit/test_web_invoke.py",
    "CLAUDE.md",
    "README.md",
    "docs/operations/development-loop.md",
    "docs/BUILD-STATUS.md",
    "docs/superpowers/plans/2026-11-09-web-matplotlib-environment.md"
  ]
}
```

**Delivery state:** Scoped implementation and focused checks completed; independent frozen-source review and broader runtime verification remain pending.

## Contract and trust

Only `MPLCONFIGDIR` joins the existing web-to-CLI process allowlist. A present server
process value passes verbatim, including an empty, relative or unusable value. The
filter does not validate, normalize, create or default the path. Unset stays absent,
so existing fallback behavior remains unchanged. This is trusted operator input,
including inherited shell state, not a browser/request environment setting. The
fixed executable, separate argv/env, other filters and dedicated worker/model
environments remain unchanged.

The directory is configuration input as well as cache storage. Tests that launch
children use fresh empty owned writable absolute directories; no owner config is
copied or read. Pure edge-value tests call only the environment builder. A future
renderer stage must also verify an owned CWD without matplotlibrc. Existing Agg
selection and rcParams-default rendering protections remain unchanged.

## Evidence limits and documentation

Generic Claude consultation informed the configuration/cache trust distinction,
literal forwarding tests and warning against isolation claims. Its proposed
startup validation is deliberately outside this forwarding-only scope. It is not
an exact-source review. Independent frozen-source review remains required.

The focused fake-child check uses only Python standard-library imports, not the
actual alpha executable or Matplotlib. The separate cache-seam import-boundary
node checks its existing no-heavy-import assertion. Neither establishes actual
Matplotlib config/cache placement, downstream inheritance through other filters,
byte-identical figures, whole-home/host isolation, Python bytecode isolation,
font-discovery isolation, network isolation or sandboxing. Actual renderer and
default/browser verification remain separate approved stages.

README's adjacent setup paragraph merits a concise description of the new process
setting and a link to detailed development-loop guidance. The manual retains every
prior instruction while fitting the unchanged 6000-byte combined budget; the
current-state entry is appended. No upstream fetch or gate attestation is made
under this task's network/history restrictions. Dates use the task's UTC date,
2026-11-09, rather than inherited successor directory labels. DAG, look-ahead,
numerical determinism, research admission and execution authority are unchanged.

## Focused results

The test-first run produced seven expected configured-forwarding failures and four
passing unset controls. After the one-key change, all 36 focused public cases
passed: 24 original invocation cases, 11 new contract/stdlib-child cases, and the
exact existing cache import-boundary node. Scoped Ruff/format and strict mypy on
the two changed Python files passed. The renderer/version-parity neighbor was not
run. Failed and successful receipts remain separate and bound to external evidence.
