import { describe, expect, it } from 'vitest'

import { statusChip } from './statusModel'

describe('statusChip', () => {
  it('says Paper only by default — no live-capital routing exists', () => {
    expect(statusChip({ watermark: null, gateLock: null })).toEqual({
      text: 'Paper only',
      tone: 'kind',
      title: 'No live-capital routing exists; every session is paper. Open Governance for authority and gates.',
    })
  })

  it('relays the selected run watermark verbatim ahead of anything else', () => {
    const chip = statusChip({
      watermark: 'EXPLORATORY / RESEARCH GATE NOT COMPLETED',
      gateLock: { reason: 'gate reason' },
    })
    expect(chip.text).toBe('EXPLORATORY / RESEARCH GATE NOT COMPLETED')
    expect(chip.tone).toBe('fail')
    expect(chip.title).toContain('launched under an owner research-gate override')
  })

  it('names an open research gate on the linked project with its reason as the title', () => {
    expect(statusChip({ watermark: null, gateLock: { reason: 'gate reason' } })).toEqual({
      text: 'Research gate open',
      tone: 'warn',
      title: 'gate reason',
    })
  })
})
