import dagre from '@dagrejs/dagre'

export interface LayoutInputNode {
  id: string
  width?: number
  height?: number
}

export interface LayoutInputEdge {
  source: string
  target: string
}

export interface Positioned {
  id: string
  x: number
  y: number
}

const NODE_WIDTH = 190
const NODE_HEIGHT = 56

/** Deterministic left-to-right layered layout; swappable for elkjs later. */
export function layoutGraph(
  nodes: LayoutInputNode[],
  edges: LayoutInputEdge[],
  direction: 'LR' | 'TB' = 'LR',
): Positioned[] {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: direction, nodesep: 28, ranksep: 64 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const node of nodes) {
    g.setNode(node.id, { width: node.width ?? NODE_WIDTH, height: node.height ?? NODE_HEIGHT })
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target)
  }
  dagre.layout(g)
  return nodes.map((node) => {
    const pos = g.node(node.id)
    return { id: node.id, x: pos.x, y: pos.y }
  })
}
