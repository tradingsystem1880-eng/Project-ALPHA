// Research-gate override watermark (spec §15, ADR-0026): a run launched under an owner
// research-gate override permanently carries `EXPLORATORY / RESEARCH GATE NOT COMPLETED`.
// The string is Python-authoritative (alpha_cli.run_store.RESEARCH_GATE_OVERRIDE_WATERMARK,
// recorded in the immutable manifest and joined into run identity); the SPA only relays what
// the projection recorded — it never derives, upgrades, or drops the marker.

export interface WatermarkedRun {
  research_gate_watermark?: string | null
}

export function researchGateWatermark(run: WatermarkedRun | null | undefined): string | null {
  const value = run?.research_gate_watermark
  return typeof value === 'string' && value.length > 0 ? value : null
}

// R6h (spec §15): `open` is the only state that locks strategy-creation and optimisation
// affordances in the SPA. `not_required` (grandfathered), `passed`, and `overridden`
// (owner-recorded, permanently watermarked) never lock, and a missing state — a
// non-research context with no linked project — is never treated as a gate.
export type ResearchGateState = 'not_required' | 'open' | 'passed' | 'overridden'

export interface StrategyGateLock {
  reason: string
}

export function strategyGateLock(
  state: ResearchGateState | null | undefined,
): StrategyGateLock | null {
  if (state !== 'open') return null
  return {
    reason:
      'This project’s research gate is open: strategy creation and optimisation stay '
      + 'disabled until the owner closes the research case with an advance_to_strategy '
      + 'decision — or records a trusted-local CLI override, which permanently watermarks '
      + 'every run.',
  }
}
