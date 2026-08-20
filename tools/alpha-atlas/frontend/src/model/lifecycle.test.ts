import { describe, expect, it } from 'vitest'

import { selectLifecycle } from './lifecycle'
import type { AtlasGraph, AtlasNode } from './types'

const prov = [{ extractor: 't', source: 's', detail: 'd' }]

function node(id: string, kind: string, order?: number): AtlasNode {
  return {
    id,
    kind,
    label: id,
    evidence: { level: 'implemented', provenance: prov },
    meta: order === undefined ? {} : { order },
  }
}

const graph: AtlasGraph = {
  schema_version: 1,
  inputs_hash: 'x',
  nodes: [
    node('wf:r.b', 'workflow_node', 2),
    node('wf:r.a', 'workflow_node', 1),
    node('wf:r.c', 'workflow_node', 3),
    node('research_case', 'research_case'),
    node('artifact:m', 'artifact'),
    node('artifact:orphan', 'artifact'),
    node('module:x', 'module'),
  ],
  edges: [
    {
      id: 'e1',
      type: 'produces',
      source: 'wf:r.a',
      target: 'artifact:m',
      evidence: { level: 'declared', provenance: prov },
    },
    {
      id: 'e2',
      type: 'validates',
      source: 'module:x',
      target: 'wf:r.a',
      evidence: { level: 'implemented', provenance: prov },
    },
  ],
  stats: {},
}

describe('selectLifecycle', () => {
  it('orders workflow nodes by meta.order and synthesizes the spine', () => {
    const selection = selectLifecycle(graph)
    const wf = selection.nodes.filter((n) => n.kind === 'workflow_node').map((n) => n.id)
    expect(wf).toEqual(['wf:r.a', 'wf:r.b', 'wf:r.c'])
    expect(selection.spine).toEqual([
      { id: 'spine:wf:r.a', source: 'wf:r.a', target: 'wf:r.b' },
      { id: 'spine:wf:r.b', source: 'wf:r.b', target: 'wf:r.c' },
    ])
  })

  it('includes entities and produced artifacts, excludes orphans and modules', () => {
    const ids = selectLifecycle(graph).nodes.map((n) => n.id)
    expect(ids).toContain('research_case')
    expect(ids).toContain('artifact:m')
    expect(ids).not.toContain('artifact:orphan')
    expect(ids).not.toContain('module:x')
  })

  it('keeps only edges internal to the selection', () => {
    const edges = selectLifecycle(graph).edges.map((e) => e.id)
    expect(edges).toEqual(['e1'])
  })
})
