import { describe, expect, it } from 'vitest'

import { layoutGraph } from './layout'

describe('layoutGraph', () => {
  it('positions a chain left to right', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }, { id: 'c' }]
    const edges = [
      { source: 'a', target: 'b' },
      { source: 'b', target: 'c' },
    ]
    const positioned = layoutGraph(nodes, edges)
    const byId = new Map(positioned.map((p) => [p.id, p]))
    expect(byId.get('a')!.x).toBeLessThan(byId.get('b')!.x)
    expect(byId.get('b')!.x).toBeLessThan(byId.get('c')!.x)
  })

  it('is deterministic', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }]
    const edges = [{ source: 'a', target: 'b' }]
    expect(layoutGraph(nodes, edges)).toEqual(layoutGraph(nodes, edges))
  })
})
