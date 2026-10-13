**Delivery state:** Candidate on accepted PR #59 main `2172406c`; focused public checks pass; canonical full, fresh independent review, hosted acceptance and publication remain pending.

# Preserve extreme finite chart values in ticks and labels

```json
{
  "schema_version": 1,
  "title": "Extreme finite chart tick formatting",
  "context": "Owner requests all known wanted unfinished robustness work completed. Dependency audit reproduced actual tiny finite chart data yielding zero ticks, printf precision202 and RangeError. Parent explicitly assigns a separate repair; no changes to frozen PR54/55/56 or dependency patch.",
  "assumptions": [{"statement": "Only display coordinates/labels change; native observations and backend study values remain authoritative.", "verified_by": "Focused tick tests, ordinary contract tests and browser rendering/export checks."}],
  "alternatives_considered": ["Precision clamping alone rejected: it conceals nonzero ticks as zero.", "Bokeh downgrade/replacement rejected; upstream sprintf advisory remains unpatched."],
  "pre_mortem": ["Subnormal step underflow or below-ULP additions cause duplicate/nonprogressing ticks.", "Scientific labels could obscure adjacent representable ticks or overflow the plot gutter.", "Local bounds do not remove the upstream dependency advisory."],
  "slices": [
    {"title": "Safe finite tick generation and bounded distinct formatting", "verify": "npm test -- src/components/technical/technicalModel.test.ts", "expected": "Actual failure reproduces before repair; tiny/large/signed/near-equal ticks stay finite, distinct and bounded with ordinary grammar intact.", "rollback": "Revert only model and its tests.", "status": "done"},
    {"title": "Use scientific fallback on chart labels and verify readability", "verify": "npm run build; focused technical chart browser tests and independent review", "expected": "Ordinary charts unchanged; extreme labels readable without false zero or formatter error; source values/export contracts retained.", "rollback": "Revert scoped renderer/header label changes and regenerated assets.", "status": "done"},
    {"title": "Bound recorded-series edge ranges and verify narrow layouts", "verify": "scientific plot model tests and built technical-chart browser checks", "expected": "Finite values near Number.MAX_VALUE retain finite bounds; scientific tags remain within a narrow host.", "rollback": "Revert only the display-bound guard and narrow-layout regression.", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/BUILD-STATUS.md", "apps/alpha-web/frontend/README.md"],
  "out_of_scope": ["Quant arithmetic, resampling or backend data changes", "Dependency upgrades/downgrades", "Private tests/data/credentials", "Publication or merge before accepted combined-target sequence"],
  "files": ["apps/alpha-web/frontend/src/components/technical/technicalModel.ts", "apps/alpha-web/frontend/src/components/technical/technicalModel.test.ts", "apps/alpha-web/frontend/src/components/technical/technicalRenderer.ts", "apps/alpha-web/frontend/src/components/technical/TechnicalChart.tsx", "apps/alpha-web/frontend/src/components/bokehPlot.ts", "apps/alpha-web/frontend/e2e/technical-chart.spec.ts", "docs/", "apps/alpha-web/frontend/README.md"]
}
```

No statistical or backend values change. The recorded-series bounds use finite saturated padding at the representable edges; a range whose affine canvas scale cannot be represented still fails closed. The narrow-host browser regression verifies visible tag containment. The readiness docstring describes the typed overall status while retaining the legacy per-requirement details as unavailable and fail closed.

The upstream `sprintf-js` advisory GHSA-hp3w-g68c-fv3c remains unresolved; this local display correction does not remove that dependency advisory. Private coverage remains UNVERIFIED under the existing approved scope; no private access or new exception is inferred. Canonical full, fresh independent review, hosted CI and post-merge verification remain pending.

## Linux screenshot follow-up (2026-10-13)

The first PR #60 hosted run retained exact evidence for both screenshot failures. The reference and
wide host/viewport dimensions matched their baselines, but the chart's Bokeh shadow root reserved
167px at the right edge instead of 64px. The cause was a MACD histogram cancellation residual below
one ULP of its corresponding source close; its scientific tag expanded the shared frame for every
panel. The display extent now treats only those sub-ULP MACD residuals as zero. Raw backend arrays
remain unchanged, prior fixed-decimal labels are preserved, and genuine tiny MACD values relative
to tiny source closes still use scientific labels. A built-browser regression pins the inner Bokeh
gutter and fixed-decimal label; the ordinary PNG export contract remains covered. The previous full
and review do not certify this follow-up; a fresh exact-tree full, independent review, and hosted CI
are required.
