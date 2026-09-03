import { describe, expect, it } from 'vitest'

import { EMPTY_MDI, activateDocument, closeDocument, openDocument, windowOf } from './mdiModel'

describe('mdiModel', () => {
  it('opens and activates, never duplicating an open key', () => {
    let state = openDocument(EMPTY_MDI, 'chart:BTC/USDT', 'BTC/USDT')
    expect(state.active).toBe('chart:BTC/USDT')
    state = openDocument(state, 'governance', 'Governance')
    state = openDocument(state, 'chart:BTC/USDT', 'BTC/USDT')
    expect(state.documents.map((item) => item.key)).toEqual(['chart:BTC/USDT', 'governance'])
    expect(state.active).toBe('chart:BTC/USDT')
  })

  it('keys reports by run so two reports coexist', () => {
    let state = openDocument(EMPTY_MDI, 'report:aaaaaaaa', 'Run A')
    state = openDocument(state, 'report:bbbbbbbb', 'Run B')
    expect(state.documents).toHaveLength(2)
    expect(state.documents.every((item) => item.window === 'report')).toBe(true)
    expect(windowOf('report:bbbbbbbb')).toBe('report')
  })

  it('keeps insertion order stable across activation', () => {
    let state = openDocument(EMPTY_MDI, 'chart', 'Chart')
    state = openDocument(state, 'build', 'Build')
    state = openDocument(state, 'research', 'Research Case')
    state = activateDocument(state, 'chart')
    expect(state.documents.map((item) => item.key)).toEqual(['chart', 'build', 'research'])
    expect(state.active).toBe('chart')
  })

  it('closing the active document activates the previous neighbour', () => {
    let state = openDocument(EMPTY_MDI, 'chart', 'Chart')
    state = openDocument(state, 'build', 'Build')
    state = openDocument(state, 'research', 'Research Case')
    state = closeDocument(state, 'research')
    expect(state.active).toBe('build')
    state = activateDocument(state, 'chart')
    state = closeDocument(state, 'chart')
    expect(state.active).toBe('build')
  })

  it('closing an inactive document leaves the active one alone', () => {
    let state = openDocument(EMPTY_MDI, 'chart', 'Chart')
    state = openDocument(state, 'build', 'Build')
    state = closeDocument(state, 'chart')
    expect(state).toEqual({ documents: [{ key: 'build', window: 'build', title: 'Build' }], active: 'build' })
  })

  it('closing the last document leaves nothing active and does not throw', () => {
    const state = closeDocument(openDocument(EMPTY_MDI, 'chart', 'Chart'), 'chart')
    expect(state).toEqual({ documents: [], active: null })
  })

  it('refuses to close or activate a document that is not open', () => {
    expect(() => closeDocument(EMPTY_MDI, 'nope')).toThrow(/unknown document nope/)
    expect(() => activateDocument(EMPTY_MDI, 'nope')).toThrow(/unknown document nope/)
  })

  it('is deterministic: the same actions yield a deep-equal state', () => {
    const run = () => {
      let state = openDocument(EMPTY_MDI, 'chart:BTC/USDT', 'BTC/USDT')
      state = openDocument(state, 'report:aaaaaaaa', 'Run A')
      state = activateDocument(state, 'chart:BTC/USDT')
      return closeDocument(state, 'report:aaaaaaaa')
    }
    expect(run()).toEqual(run())
  })
})
