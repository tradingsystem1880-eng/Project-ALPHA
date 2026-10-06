import { describe, expect, it } from 'vitest'
import type { ProjectPage, ResearchCasePage } from '../api/types'
import { applyLinkedPatch, DEFAULT_LINKED } from '../context/linked'
import { inventoryPages, projectChoices, projectSelectionPatch } from './projectContextModel'

describe('project-free browsing', () => {
  it('clears frozen project evidence while preserving the viewed market and dates', () => {
    const current = { ...DEFAULT_LINKED, projectId: 'old', symbol: 'ETH/USDT', start: '2020-01-01', end: '2021-01-01', versionId: 'v1', runId: '0123456789abcdef', snapshotId: 'frozen' }
    expect(applyLinkedPatch(current, projectSelectionPatch(current, null))).toMatchObject({ projectId: null, symbol: 'ETH/USDT', start: current.start, end: current.end, versionId: null, runId: null, snapshotId: null })
    expect(applyLinkedPatch(current, projectSelectionPatch(current, 'new'))).toMatchObject({ projectId: 'new', symbol: null, runId: null, snapshotId: null, versionId: null })
  })
  it('merges canonical IDs, preserves unknown-market research and excludes known other markets', () => {
    const projects = [{ project_id: 'crypto', name: 'Crypto case', market: 'crypto' }, { project_id: 'equity', name: 'Equity case', market: 'equities' }] as ProjectPage['items']
    const cases = [{ case_id: 'crypto', title: 'Duplicate' }, { case_id: 'equity', title: 'Wrong market' }, { case_id: 'early', title: 'Early research' }] as ResearchCasePage['items']
    expect(projectChoices(projects, cases, 'crypto')).toEqual([{ id: 'crypto', label: 'Crypto case' }, { id: 'early', label: 'Early research' }])
  })
  it('follows every page and relays failures', async () => {
    const offsets: number[] = []
    expect(await inventoryPages(async offset => { offsets.push(offset); return { items: [offset], offset, limit: 2, has_more: offset < 4 } })).toEqual([0, 2, 4])
    expect(offsets).toEqual([0, 2, 4])
    await expect(inventoryPages(async () => { throw new Error('API unavailable') })).rejects.toThrow('API unavailable')
    await expect(inventoryPages(async offset => ({ items: [], offset, limit: 2, has_more: true }))).rejects.toThrow('nonadvancing')
    await expect(inventoryPages(async () => ({ items: [1], offset: 2, limit: 2, has_more: true }))).rejects.toThrow('nonadvancing')
  })
})
