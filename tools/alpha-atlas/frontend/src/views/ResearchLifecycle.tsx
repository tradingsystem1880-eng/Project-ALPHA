import { ReactFlow, Background, Controls, type Edge, type Node } from '@xyflow/react'
import { useMemo, useState } from 'react'

import { NodePanel } from '../components/NodePanel'
import { levelColor } from '../model/evidence'
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

  const steps = useMemo(
    () =>
      selectLifecycle(graph)
        .nodes.filter((n) => n.kind === 'workflow_node')
        .map((n) => ({ id: n.id, label: n.label })),
    [graph],
  )

  const { nodes, edges } = useMemo(() => {
    const selection = selectLifecycle(graph)
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
      const color = levelColor(n.evidence.level)
      const isWorkflow = n.kind === 'workflow_node'
      const order = n.meta?.['order']
      return {
        id: n.id,
        position: { x: pos.x, y: pos.y },
        data: { label: isWorkflow && typeof order === 'number' ? `${order}. ${n.label}` : n.label },
        style: {
          background: isWorkflow ? '#10151f' : '#0b0f16',
          color: '#dbe4f2',
          border: `1.5px solid ${color}`,
          borderRadius: 8,
          fontSize: 12,
          width: 190,
          boxShadow: n.id === selected ? `0 0 0 2px ${color}` : undefined,
        },
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
    return { nodes: flowNodes, edges: flowEdges }
  }, [graph, selected])

  return (
    <>
      <div className="flow">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodeClick={(_, node) => setSelected(node.id)}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
          colorMode="dark"
        >
          <Background color="#1e2635" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
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
