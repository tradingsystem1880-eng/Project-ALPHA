import type { Edge, Node } from '@xyflow/react'
import { useMemo, useState } from 'react'

import { atlasNodeStyle, GraphCanvas, styleNodes } from '../components/GraphCanvas'
import { NodePanel } from '../components/NodePanel'
import { layoutGraph } from '../model/layout'
import { selectLifecycle } from '../model/lifecycle'
import type { AtlasGraph } from '../model/types'

const EDGE_STYLE: Record<string, { stroke: string; dash?: string }> = {
  spine: { stroke: '#4f8dff' },
  produces: { stroke: '#8a93a6', dash: '6 4' },
  depends_on: { stroke: '#8a93a6', dash: '2 4' },
  defines: { stroke: '#6f7ff2', dash: '1 5' },
  validates: { stroke: '#4cc38a', dash: '1 5' },
}

export function ResearchLifecycle({ graph }: { graph: AtlasGraph }) {
  const [selected, setSelected] = useState<string | null>(null)

  const { baseNodes, edges, steps } = useMemo(() => {
    const selection = selectLifecycle(graph)
    const steps = selection.nodes
      .filter((n) => n.kind === 'workflow_node')
      .map((n) => ({ id: n.id, label: n.label }))
    const layoutEdges = [
      ...selection.spine.map((e) => ({ source: e.source, target: e.target })),
      ...selection.edges
        .filter((e) => e.type !== 'validates' && e.type !== 'defines')
        .map((e) => ({ source: e.source, target: e.target })),
    ]
    const positions = new Map(
      layoutGraph(
        selection.nodes.map((n) => ({ id: n.id })),
        layoutEdges,
      ).map((p) => [p.id, p]),
    )
    const flowNodes: Node[] = selection.nodes.map((n) => {
      const pos = positions.get(n.id)!
      const isWorkflow = n.kind === 'workflow_node'
      const order = n.meta?.['order']
      return {
        id: n.id,
        position: { x: pos.x, y: pos.y },
        data: {
          label: isWorkflow && typeof order === 'number' ? `${order}. ${n.label}` : n.label,
          level: n.evidence.level,
        },
        style: atlasNodeStyle(n.evidence.level, { emphasis: isWorkflow }),
      }
    })
    const flowEdges: Edge[] = [
      ...selection.spine.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        style: { stroke: EDGE_STYLE.spine.stroke, strokeWidth: 2 },
      })),
      ...selection.edges.map((e) => {
        const style = EDGE_STYLE[e.type] ?? { stroke: '#8a93a6' }
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.type,
          labelStyle: { fill: '#8a93a6', fontSize: 9 },
          labelBgStyle: { fill: '#090c12' },
          style: { stroke: style.stroke, strokeDasharray: style.dash },
        }
      }),
    ]
    return { baseNodes: flowNodes, edges: flowEdges, steps }
  }, [graph])
  const nodes = useMemo(() => styleNodes(baseNodes, selected), [baseNodes, selected])

  return (
    <>
      <GraphCanvas nodes={nodes} edges={edges} onNodeClick={setSelected} />
      <aside className="panel">
        {selected ? (
          <NodePanel nodeId={selected} nav={{ steps, onSelect: setSelected }} />
        ) : (
          <div className="placeholder">
            Start at <strong>1. Idea Capture</strong> and walk the numbered steps to{' '}
            <strong>10. Strategy Promotion</strong>. Clicking a step shows what it is, the
            files that implement it (with excerpts), the ADRs that define it, the tests
            that verify it — and a Generate AI Context button for a ready-to-paste prompt.
          </div>
        )}
      </aside>
    </>
  )
}
