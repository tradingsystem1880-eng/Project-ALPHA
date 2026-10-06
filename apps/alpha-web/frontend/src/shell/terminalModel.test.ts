import { expect, it } from 'vitest'
import { functionEntries, resolveFunction, restoreDesk } from './terminalModel'
import { workflowPages } from './workflowModel'

it('maps every profile-visible task and rejects unavailable or executable commands', () => {
  for (const profile of ['crypto', 'equities'] as const) {
    const entries = functionEntries(profile)
    expect(entries.length).toBe(workflowPages(profile).flatMap(page => page.panes).length)
    expect(new Set(entries.map(entry => entry.code)).size).toBe(entries.length)
    for (const entry of entries) expect(resolveFunction(entry.code.toLowerCase(), profile)).toEqual(entry)
  }
  expect(resolveFunction(' chart ', 'crypto')?.pane).toBe('PriceChart')
  expect(resolveFunction('Literature', 'crypto')?.pane).toBe('Literature')
  expect(resolveFunction('FUNDING', 'equities')).toBeNull()
  expect(resolveFunction('alpha research approve', 'crypto')).toBeNull()
})

it('recovers malformed desk preferences and bounds widths without coercing strings', () => {
  expect(restoreDesk(null)).toEqual({ watch: true, data: false, maximized: false, width: 285 })
  expect(restoreDesk({ watch: 'false', width: '900' })).toEqual(restoreDesk(null))
  expect(restoreDesk({ watch: false, data: true, maximized: true, width: 900 })).toEqual({ watch: false, data: true, maximized: true, width: 420 })
  expect(restoreDesk({ width: Number.NaN }).width).toBe(285)
})
