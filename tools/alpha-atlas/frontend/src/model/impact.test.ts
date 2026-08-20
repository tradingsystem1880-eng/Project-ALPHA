import { describe, expect, it } from 'vitest'

import { computeImpact } from './impact'
import type { AtlasEdge, AtlasGraph, AtlasNode } from './types'

function node(id: string, kind = 'module'): AtlasNode {
  return {
    id,
    kind,
    label: id,
    evidence: { level: 'implemented', provenance: [] },
    meta: {},
  } as AtlasNode
}

function edge(id: string, type: string, source: string, target: string): AtlasEdge {
  return { id, type, source, target, evidence: { level: 'declared', provenance: [] } } as AtlasEdge
}

// cli -> calls -> b -> depends_on -> a; unrelated c; tests on b and cli.
const graph: AtlasGraph = {
  schema_version: 1,
  inputs_hash: 'x',
  nodes: [
    node('module:a'),
    node('module:b'),
    node('module:c'),
    node('cli:alpha x', 'cli_command'),
    node('test:tests/unit/test_b.py', 'test'),
  ],
  edges: [
    edge('e1', 'depends_on', 'module:b', 'module:a'),
    edge('e2', 'calls', 'cli:alpha x', 'module:b'),
    edge('e3', 'depends_on', 'module:c', 'module:b'),
    edge('e4', 'validates', 'test:tests/unit/test_b.py', 'module:b'),
  ],
  stats: {},
}

describe('computeImpact', () => {
  it('walks reverse dependencies breadth-first with depths', () => {
    const result = computeImpact(graph, 'module:a')
    expect(result.impacted.map((i) => [i.node.id, i.depth])).toEqual([
      ['module:b', 1],
      ['cli:alpha x', 2],
      ['module:c', 2],
    ])
  })

  it('collects the tests exercising anything in scope', () => {
    expect(computeImpact(graph, 'module:a').tests).toEqual(['test:tests/unit/test_b.py'])
  })

  it('an isolated node has an empty blast radius', () => {
    const result = computeImpact(graph, 'module:c')
    expect(result.impacted).toEqual([])
    expect(result.tests).toEqual([])
  })
})
