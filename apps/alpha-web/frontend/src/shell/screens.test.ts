import { describe, expect, it } from 'vitest'

import { areasOf, RESULTS_SCREEN, SCREENS, screen, type ScreenId } from './screens'

describe('screen definitions', () => {
  it('covers every screen the shell can navigate to', () => {
    const ids = SCREENS.map((item) => item.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids).toContain(RESULTS_SCREEN)
  })

  it('gives every screen a purpose a reader can act on', () => {
    for (const definition of SCREENS) {
      expect(definition.purpose.trim().length).toBeGreaterThan(20)
      expect(definition.label.trim()).not.toBe('')
    }
  })

  it('declares a layout class for every screen', () => {
    for (const definition of SCREENS) {
      expect(definition.layout).toMatch(/^screen--[a-z]+$/)
    }
  })

  it('never leaves a screen with nothing to show', () => {
    for (const definition of SCREENS) {
      expect(definition.panes.length).toBeGreaterThan(0)
    }
  })

  it('gives every pane a unique name within its screen', () => {
    for (const definition of SCREENS) {
      const names = definition.panes.map((pane) => pane.name)
      expect(new Set(names).size, `${definition.id} repeats a pane`).toBe(names.length)
    }
  })

  it('only uses areas the layout CSS defines', () => {
    // A pane assigned to an area the grid does not name would silently vanish.
    const allowed = new Set(['main', 'side', 'foot'])
    for (const definition of SCREENS) {
      for (const pane of definition.panes) {
        expect(allowed.has(pane.area), `${definition.id}/${pane.name} -> ${pane.area}`).toBe(true)
      }
    }
  })

  it('puts the run report on a screen with nothing beside it', () => {
    // A figure is 11 inches wide by design; sharing the row would defeat the whole change.
    const results = screen(RESULTS_SCREEN)
    expect(results.panes).toHaveLength(1)
    expect(results.panes[0].area).toBe('main')
  })

  it('groups panes by area in declaration order', () => {
    const explore = areasOf(screen('explore'))
    const [firstArea, firstPanes] = explore[0]
    expect(firstArea).toBe('main')
    expect(firstPanes.map((pane) => pane.name)).toEqual([
      'ResearchCockpit',
      'EvidenceHub',
      'PriceChart',
    ])
    const side = explore.find(([area]) => area === 'side')
    expect(side?.[1].map((pane) => pane.name)).toEqual([
      'ResearchBacklog',
      'Literature',
      'DataManager',
      'CodexBench',
    ])
  })

  it('keeps research primary and standalone work visibly separate from development', () => {
    expect(screen('explore').label).toBe('Research')
    expect(screen('build').panes.map((pane) => pane.title)).toContain('Standalone Sandbox')
    expect(screen('build').panes.map((pane) => pane.name)).not.toContain('ResearchCockpit')
  })

  it('rejects an unknown screen instead of rendering an empty shell', () => {
    expect(() => screen('nope' as ScreenId)).toThrow(/unknown screen/)
  })
})
