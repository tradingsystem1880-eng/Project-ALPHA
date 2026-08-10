import { describe, expect, it } from 'vitest'

import { researchGateWatermark, strategyGateLock } from './researchGateModel'

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

describe('strategyGateLock', () => {
  it('locks strategy affordances only while a research-required gate is open', () => {
    const lock = strategyGateLock('open')
    expect(lock).not.toBeNull()
    expect(lock?.reason).toContain('research gate is open')
    expect(lock?.reason).toContain('advance_to_strategy')
  })

  it('never locks grandfathered, passed, or owner-overridden gates', () => {
    expect(strategyGateLock('not_required')).toBeNull()
    expect(strategyGateLock('passed')).toBeNull()
    expect(strategyGateLock('overridden')).toBeNull()
  })

  it('never locks non-research contexts (no linked project / unknown state)', () => {
    expect(strategyGateLock(null)).toBeNull()
    expect(strategyGateLock(undefined)).toBeNull()
  })
})
