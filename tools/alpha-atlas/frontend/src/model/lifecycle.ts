import type { AtlasEdge, AtlasGraph, AtlasNode } from './types'

export interface LifecycleSelection {
  nodes: AtlasNode[]
  /** Synthesized presentation edges Idea -> ... -> Promotion (from meta.order). */
  spine: Array<{ id: string; source: string; target: string }>
  /** Real graph edges whose endpoints are both inside the selection. */
  edges: AtlasEdge[]
}

export const ENTITY_KINDS = new Set([
  'research_case',
  'hypothesis',
  'dataset',
  'experiment',
  'decision',
  'strategy_version',
])

function orderOf(node: AtlasNode): number {
  const raw = node.meta?.['order']
  return typeof raw === 'number' ? raw : Number.POSITIVE_INFINITY
}

export function selectLifecycle(graph: AtlasGraph): LifecycleSelection {
  const workflow = graph.nodes
    .filter((n) => n.kind === 'workflow_node')
    .sort((a, b) => orderOf(a) - orderOf(b))
  const entities = graph.nodes.filter((n) => ENTITY_KINDS.has(n.kind))
  const selectedIds = new Set([...workflow, ...entities].map((n) => n.id))
  const artifactIds = new Set(
    graph.edges
      .filter((e) => e.type === 'produces' && selectedIds.has(e.source))
      .map((e) => e.target),
  )
  const artifacts = graph.nodes.filter((n) => n.kind === 'artifact' && artifactIds.has(n.id))
  const nodes = [...workflow, ...entities, ...artifacts]
  const ids = new Set(nodes.map((n) => n.id))
  const spine = workflow.slice(0, -1).map((node, index) => ({
    id: `spine:${node.id}`,
    source: node.id,
    target: workflow[index + 1].id,
  }))
  const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target))
  return { nodes, spine, edges }
}
