import { describe, expect, it } from 'vitest'

import {
  DOCKS,
  DOCUMENT_KINDS,
  DOCUMENTS,
  REPORT_DOCUMENT,
  dockOf,
  documentOf,
  panesByArea,
} from './documents'
import { PROFILES } from './profiles'
import type { DockId, WindowId } from './profiles'

describe('document registry', () => {
  it('names every document once with a kind, a title and something to show', () => {
    const ids = DOCUMENTS.map((item) => item.id)
    expect(new Set(ids).size).toBe(ids.length)
    for (const definition of DOCUMENTS) {
      expect(DOCUMENT_KINDS).toContain(definition.kind)
      expect(definition.title.trim()).not.toBe('')
      expect(definition.panes.length).toBeGreaterThan(0)
      for (const pane of definition.panes) {
        expect(typeof pane.component).toBe('function')
        expect(pane.title.trim()).not.toBe('')
      }
      const names = definition.panes.map((pane) => pane.name)
      expect(new Set(names).size, `${definition.id} repeats a pane`).toBe(names.length)
    }
  })

  it('resolves every window either profile can show, and nothing else', () => {
    const shown = new Set<WindowId>()
    for (const manifest of Object.values(PROFILES)) {
      for (const window of manifest.windows) shown.add(window)
    }
    for (const window of shown) expect(documentOf(window).id).toBe(window)
    expect(new Set(DOCUMENTS.map((item) => item.id))).toEqual(shown)
  })

  it('opens run reports in a document with nothing beside them', () => {
    // A figure is 11 inches wide by design; sharing the document would defeat Phase 2.
    const report = documentOf(REPORT_DOCUMENT)
    expect(report.kind).toBe('report')
    expect(report.panes).toHaveLength(1)
  })

  it('keeps research primary and standalone work visibly separate from development', () => {
    expect(documentOf('research').panes[0].name).toBe('ResearchCockpit')
    const build = documentOf('build').panes
    expect(build.map((pane) => pane.title)).toContain('Standalone Sandbox')
    expect(build.map((pane) => pane.name)).not.toContain('ResearchCockpit')
  })

  it('carries no Glossary pane — it lives on the Governance document', () => {
    for (const definition of DOCUMENTS) {
      expect(definition.panes.map((pane) => pane.name)).not.toContain('Glossary')
    }
    expect(documentOf('governance').panes.map((pane) => pane.name)).toEqual(['Governance'])
  })

  it('never titles a document the same as one of its pane tabs', () => {
    // Both render as role=tab; an equal name would make the two indistinguishable.
    for (const definition of DOCUMENTS) {
      if (definition.panes.length < 2) continue
      expect(definition.panes.map((pane) => pane.title)).not.toContain(definition.title)
    }
  })

  it('keeps every document one column unless it declares side panes, always with a main pane', () => {
    for (const definition of DOCUMENTS) {
      const { main, side } = panesByArea(definition)
      expect(main.length).toBeGreaterThan(0)
      expect(main.length + side.length).toBe(definition.panes.length)
    }
    expect(panesByArea(documentOf('build')).side.map((pane) => pane.title)).toEqual([
      'Development Next Step',
      'Standalone Sandbox',
    ])
    expect(panesByArea(documentOf('report')).side).toEqual([])
  })

  it('rejects an unknown document instead of rendering an empty shell', () => {
    expect(() => documentOf('nope' as WindowId)).toThrow(/unknown document/)
  })
})

describe('dock registry', () => {
  it('places Market Watch and the Navigator left, the Data Manager right, the Toolbox below', () => {
    const ids = DOCKS.map((item) => item.id)
    expect(new Set(ids).size).toBe(ids.length)
    const side = (dockId: DockId) => dockOf(dockId).side
    expect(DOCKS.filter((item) => item.side === 'left').map((item) => item.id)).toEqual([
      'MarketWatch',
      'Navigator',
    ])
    expect(side('DataManager')).toBe('right')
    expect(side('Toolbox')).toBe('bottom')
    for (const definition of DOCKS) {
      expect(['left', 'right', 'bottom']).toContain(definition.side)
      expect(definition.title.trim()).not.toBe('')
    }
  })

  it('gives every dock the artboard tabs in order (Alerts, Favorites and Snapshots are shown disabled)', () => {
    expect(dockOf('Toolbox').tabs).toEqual(['Jobs', 'Trades', 'Backtests', 'Data pulls', 'Log', 'Alerts'])
    expect(dockOf('MarketWatch').tabs).toEqual(['Symbols', 'Details', 'Data'])
    expect(dockOf('Navigator').tabs).toEqual(['Common', 'Favorites'])
    expect(dockOf('DataManager').tabs).toEqual(['Pull', 'Snapshots', 'Quality', 'Storage'])
  })

  it('resolves every dock a profile lists', () => {
    for (const manifest of Object.values(PROFILES)) {
      for (const dockId of manifest.docks) expect(dockOf(dockId).id).toBe(dockId)
    }
  })

  it('rejects an unknown dock', () => {
    expect(() => dockOf('Alerts' as DockId)).toThrow(/unknown dock/)
  })
})
