import { describe, expect, it } from 'vitest'

import { researchGateWatermark } from './researchGateModel'

const WATERMARK = 'EXPLORATORY / RESEARCH GATE NOT COMPLETED'

describe('researchGateWatermark', () => {
  it('relays the recorded marker verbatim', () => {
    expect(researchGateWatermark({ research_gate_watermark: WATERMARK })).toBe(WATERMARK)
  })

  it('is null for unmarked runs — the SPA never invents or upgrades gate state', () => {
    expect(researchGateWatermark({ research_gate_watermark: null })).toBeNull()
    expect(researchGateWatermark({})).toBeNull()
    expect(researchGateWatermark(null)).toBeNull()
    expect(researchGateWatermark(undefined)).toBeNull()
    expect(researchGateWatermark({ research_gate_watermark: '' })).toBeNull()
  })
})
