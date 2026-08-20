import { describe, expect, it } from 'vitest'

import { selectComponentModules, selectSystemMap } from './systemMap'
import type { AtlasGraph, AtlasNode } from './types'

function node(id: string, kind: string, component?: string, level = 'implemented'): AtlasNode {
  return {
    id,
    kind,
    label: id,
    component,
    evidence: { level, provenance: [] },
    meta: {},
  } as AtlasNode
}

const graph: AtlasGraph = {
  schema_version: 1,
  inputs_hash: 'x',
  nodes: [
    node('component:a', 'component'),
    node('component:b', 'component'),
    node('module:a.one', 'module', 'a'),
    node('module:a.two', 'module', 'a', 'unknown'),
    node('module:b.one', 'module', 'b'),
    node('test:tests/unit/test_one.py', 'test'),
  ],
  edges: [
    {
      id: 'e1',
      type: 'depends_on',
      source: 'module:a.one',
      target: 'module:b.one',
      evidence: { level: 'declared', provenance: [] },
    },
    {
      id: 'e2',
      type: 'depends_on',
      source: 'module:a.one',
      target: 'module:a.two',
      evidence: { level: 'declared', provenance: [] },
    },
    {
      id: 'e3',
      type: 'validates',
      source: 'test:tests/unit/test_one.py',
      target: 'module:a.one',
      evidence: { level: 'declared', provenance: [] },
    },
  ],
  stats: {},
}

describe('selectSystemMap', () => {
  it('collapsed: components only, with aggregated edges and unknown badges', () => {
    const selection = selectSystemMap(graph, null)
    expect(selection.nodes.map((n) => n.id)).toEqual(['component:a', 'component:b'])
    expect(selection.componentEdges).toEqual([
      { id: 'agg:component:a>component:b', source: 'component:a', target: 'component:b' },
    ])
    expect(selection.unknowns.get('component:a')).toBe(1)
    expect(selection.moduleEdges).toEqual([])
  })

  it('expanding one component swaps in its modules and intra edges', () => {
    const selection = selectSystemMap(graph, 'component:a')
    const ids = selection.nodes.map((n) => n.id)
    expect(ids).toContain('module:a.one')
    expect(ids).toContain('component:b')
    expect(ids).not.toContain('component:a')
    expect(selection.moduleEdges.map((e) => e.id)).toEqual(['e2'])
  })
})

describe('selectComponentModules', () => {
  it('returns modules with test badges, intra edges, and external fan-out', () => {
    const selection = selectComponentModules(graph, 'component:a')
    expect(selection.modules.map((m) => [m.node.id, m.testCount])).toEqual([
      ['module:a.one', 1],
      ['module:a.two', 0],
    ])
    expect(selection.edges.map((e) => e.id)).toEqual(['e2'])
    expect(selection.external.get('component:b')).toBe(1)
  })
})
