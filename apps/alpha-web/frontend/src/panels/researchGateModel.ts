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
