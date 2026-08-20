import type { AtlasGraph, AtlasNode } from './types'

/** Edge types along which a change propagates to whatever builds on the node. */
const PROPAGATES = new Set(['depends_on', 'calls', 'serves'])

export interface ImpactResult {
  /** Nodes reachable by reverse dependency traversal, ordered by BFS depth. */
  impacted: Array<{ node: AtlasNode; depth: number }>
  /** Test node ids validating the start node or anything impacted. */
  tests: string[]
}

/**
 * Blast radius of changing `startId`: everything that depends on / calls /
 * is served by it, transitively, plus the tests that would exercise the change.
 */
export function computeImpact(graph: AtlasGraph, startId: string): ImpactResult {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const dependents = new Map<string, string[]>()
  for (const edge of graph.edges) {
    if (PROPAGATES.has(edge.type)) {
      const list = dependents.get(edge.target) ?? []
      list.push(edge.source)
      dependents.set(edge.target, list)
    }
  }
  const depths = new Map<string, number>([[startId, 0]])
  const queue = [startId]
  while (queue.length > 0) {
    const current = queue.shift()!
    for (const dependent of (dependents.get(current) ?? []).sort()) {
      if (!depths.has(dependent)) {
        depths.set(dependent, depths.get(current)! + 1)
        queue.push(dependent)
      }
    }
  }
  const impacted = [...depths.entries()]
    .filter(([id]) => id !== startId && byId.has(id))
    .map(([id, depth]) => ({ node: byId.get(id)!, depth }))
    .sort((a, b) => a.depth - b.depth || a.node.id.localeCompare(b.node.id))
  const inScope = new Set(depths.keys())
  const tests = [
    ...new Set(
      graph.edges
        .filter((e) => e.type === 'validates' && inScope.has(e.target))
        .map((e) => e.source),
    ),
  ].sort()
  return { impacted, tests }
}
