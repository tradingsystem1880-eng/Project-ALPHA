import type { AtlasEdge, AtlasGraph, AtlasNode } from './types'

export interface SystemMapSelection {
  nodes: AtlasNode[]
  /** Synthesized component-level dependency edges aggregated from module imports. */
  componentEdges: Array<{ id: string; source: string; target: string }>
  /** Real module-level edges shown only inside the expanded component. */
  moduleEdges: AtlasEdge[]
  /** component id -> count of unknown-level nodes inside it (review-queue badge). */
  unknowns: Map<string, number>
}

function componentIdOf(node: AtlasNode): string | null {
  return node.component ? `component:${node.component}` : null
}

/**
 * Components with aggregated dependency arrows; expanding one component swaps
 * in its modules (one at a time — the full module graph is never rendered).
 */
export function selectSystemMap(graph: AtlasGraph, expanded: string | null): SystemMapSelection {
  const components = graph.nodes.filter((n) => n.kind === 'component')
  const modulesById = new Map(
    graph.nodes.filter((n) => n.kind === 'module').map((n) => [n.id, n]),
  )
  const pairs = new Set<string>()
  for (const edge of graph.edges) {
    if (edge.type !== 'depends_on') continue
    const source = modulesById.get(edge.source)
    const target = modulesById.get(edge.target)
    if (!source || !target) continue
    const sourceComponent = componentIdOf(source)
    const targetComponent = componentIdOf(target)
    if (sourceComponent && targetComponent && sourceComponent !== targetComponent) {
      pairs.add(`${sourceComponent}>${targetComponent}`)
    }
  }
  const componentEdges = [...pairs].sort().map((pair) => {
    const [source, target] = pair.split('>')
    return { id: `agg:${pair}`, source, target }
  })
  const unknowns = new Map<string, number>()
  for (const node of graph.nodes) {
    const owner = componentIdOf(node)
    if (owner && node.evidence.level === 'unknown') {
      unknowns.set(owner, (unknowns.get(owner) ?? 0) + 1)
    }
  }
  let nodes = [...components]
  let moduleEdges: AtlasEdge[] = []
  if (expanded) {
    const inside = [...modulesById.values()].filter((m) => componentIdOf(m) === expanded)
    const insideIds = new Set(inside.map((m) => m.id))
    nodes = [...components.filter((c) => c.id !== expanded), ...inside]
    moduleEdges = graph.edges.filter(
      (e) => e.type === 'depends_on' && insideIds.has(e.source) && insideIds.has(e.target),
    )
  }
  return { nodes, componentEdges, moduleEdges, unknowns }
}

export interface ModuleBadge {
  node: AtlasNode
  testCount: number
}

export interface CodeExplorerSelection {
  modules: ModuleBadge[]
  edges: AtlasEdge[]
  /** other component id -> number of imports from this component into it. */
  external: Map<string, number>
}

/** One component's module/import graph with per-module validating-test counts. */
export function selectComponentModules(
  graph: AtlasGraph,
  componentId: string,
): CodeExplorerSelection {
  const inside = graph.nodes.filter(
    (n) => n.kind === 'module' && componentIdOf(n) === componentId,
  )
  const insideIds = new Set(inside.map((n) => n.id))
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const testCounts = new Map<string, number>()
  const external = new Map<string, number>()
  const edges: AtlasEdge[] = []
  for (const edge of graph.edges) {
    if (edge.type === 'validates' && insideIds.has(edge.target)) {
      testCounts.set(edge.target, (testCounts.get(edge.target) ?? 0) + 1)
    }
    if (edge.type !== 'depends_on' || !insideIds.has(edge.source)) continue
    if (insideIds.has(edge.target)) {
      edges.push(edge)
    } else {
      const target = byId.get(edge.target)
      const owner = target ? componentIdOf(target) : null
      if (owner) external.set(owner, (external.get(owner) ?? 0) + 1)
    }
  }
  const modules = inside
    .map((node) => ({ node, testCount: testCounts.get(node.id) ?? 0 }))
    .sort((a, b) => a.node.id.localeCompare(b.node.id))
  return { modules, edges, external }
}
