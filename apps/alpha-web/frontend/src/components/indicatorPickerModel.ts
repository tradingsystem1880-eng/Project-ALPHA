import { parseIndicatorSpec, type OverlayConfig } from '../panels/chartOverlaysModel'

export function replaceIndicator(config: OverlayConfig, previous: string, text: string): OverlayConfig {
  const next = parseIndicatorSpec(text)
  return { ...config, indicators: [...new Set(config.indicators.map(spec => spec === previous ? next : spec))] }
}
export function readFavorites(value: unknown): string[] {
  const result: string[] = []
  for (const item of Array.isArray(value) ? value : []) {
    if (typeof item !== 'string') continue
    try { const spec = parseIndicatorSpec(item); if (!result.includes(spec)) result.push(spec) }
    catch { /* Invalid saved preferences never become CLI input. */ }
  }
  return result
}
