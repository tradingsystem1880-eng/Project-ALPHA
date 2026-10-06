import { describe, expect, it } from 'vitest'
import { duplicatePanel, restoreWorkspace, setLayout, closePanel } from './chartWorkspaceModel'
describe('analytical workspace', () => {
  it('defaults and migrates to scientific plots while preserving explicit market mode', () => {
    expect(restoreWorkspace(null).panels[0].renderer).toBe('scientific')
    const state = restoreWorkspace(null)
    state.panels[0].renderer = 'market'
    expect(restoreWorkspace(state).panels[0].renderer).toBe('market')
    expect(duplicatePanel(state, 'primary').panels[1].renderer).toBe('market')
  })
  it('migrates comparisons into independent pinned sources', () => {
    const state = restoreWorkspace(null, ['ETH/USDT', 'BTC/USD'])
    expect(state.panels.map(p => p.source.kind)).toEqual(['primary', 'market', 'market'])
    expect(state.panels[1].source).toEqual({ kind: 'market', symbol: 'ETH/USDT', start: null, end: null, snapshotId: null })
  })
  it('duplicates independently, caps at four and validates restored identity', () => {
    let state = duplicatePanel(restoreWorkspace(null), 'primary')
    expect(state.panels[1].id).not.toBe('primary')
    expect(state.panels[1].controls).not.toBe(state.panels[0].controls)
    state = duplicatePanel(duplicatePanel(state, 'primary'), 'primary')
    expect(duplicatePanel(state, 'primary').panels).toHaveLength(4)
    expect(restoreWorkspace({ ...state, ratios: [NaN, 3], active: 'missing', maximized: 'missing' }).ratios).toEqual([0.5, 0.5])
  })
  it('keeps surviving settings on layout change and close', () => {
    const state = duplicatePanel(restoreWorkspace(null), 'primary')
    expect(setLayout(state, 'stacked').panels).toBe(state.panels)
    expect(closePanel({ ...state, active: state.panels[1].id, maximized: state.panels[1].id }, state.panels[1].id).active).toBe('primary')
    expect(closePanel(state, 'primary').panels).toHaveLength(2)
  })
  it('restores a protected primary even when saved panels omit it', () => {
    const restored = restoreWorkspace({ panels: [{ id: 'pinned', kind: 'price', source: { kind: 'market', symbol: 'BTC/USD' } }] })
    expect(restored.panels.map(p => p.id)).toEqual(['primary', 'pinned'])
    expect(closePanel(restored, 'primary').panels).toHaveLength(2)
  })
  it('rejects invalid stored sources', () => {
    expect(restoreWorkspace({ panels: [{ id: 'x', kind: 'price', source: { kind: 'run', runId: '../../x' } }] }).panels[0].id).toBe('primary')
  })
})
