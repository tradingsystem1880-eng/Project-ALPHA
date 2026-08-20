import { ReactFlow, Background, Controls, type Edge, type Node } from '@xyflow/react'
import { useMemo, useState } from 'react'

import { NodePanel } from '../components/NodePanel'
import { levelColor } from '../model/evidence'
import { layoutGraph } from '../model/layout'
import { selectSystemMap } from '../model/systemMap'
import type { AtlasGraph } from '../model/types'

export function SystemMap({ graph }: { graph: AtlasGraph }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const { nodes, edges } = useMemo(() => {
    const selection = selectSystemMap(graph, expanded)
    const layoutEdges = [
      ...selection.componentEdges.map((e) => ({ source: e.source, target: e.target })),
      ...selection.moduleEdges.map((e) => ({ source: e.source, target: e.target })),
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
      const isComponent = n.kind === 'component'
      const unknownCount = isComponent ? (selection.unknowns.get(n.id) ?? 0) : 0
      return {
        id: n.id,
        position: { x: pos.x, y: pos.y },
        data: { label: unknownCount > 0 ? `${n.label} — ${unknownCount} unknown` : n.label },
        style: {
          background: isComponent ? '#10151f' : '#0b0f16',
          color: '#dbe4f2',
          border: `1.5px solid ${color}`,
          borderRadius: 8,
          fontSize: isComponent ? 12 : 10.5,
          width: isComponent ? 190 : 210,
          boxShadow: n.id === selected ? `0 0 0 2px ${color}` : undefined,
        },
      }
    })
    const flowEdges: Edge[] = [
      ...selection.componentEdges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        style: { stroke: '#4f8dff' },
      })),
      ...selection.moduleEdges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        style: { stroke: '#8a93a6', strokeDasharray: '2 4' },
      })),
    ]
    return { nodes: flowNodes, edges: flowEdges }
  }, [graph, expanded, selected])

  return (
    <>
      <div className="flow">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodeClick={(_, node) => {
            setSelected(node.id)
            if (node.id.startsWith('component:')) {
              setExpanded((current) => (current === node.id ? null : node.id))
            }
          }}
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
          <NodePanel nodeId={selected} />
        ) : (
          <div className="placeholder">
            Components with aggregated import arrows. Click a component to expand its
            modules (one at a time); click again to collapse. Unknown-count badges are
            the review queue.
          </div>
        )}
      </aside>
    </>
  )
}
