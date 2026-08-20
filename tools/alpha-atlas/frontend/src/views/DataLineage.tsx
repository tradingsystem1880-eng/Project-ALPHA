import { ReactFlow, Background, Controls, type Edge, type Node } from '@xyflow/react'
import { useMemo, useState } from 'react'

import { NodePanel } from '../components/NodePanel'
import { levelColor } from '../model/evidence'
import { layoutGraph } from '../model/layout'
import type { AtlasGraph } from '../model/types'

const ENTITY_KINDS = new Set([
  'research_case',
  'hypothesis',
  'dataset',
  'experiment',
  'decision',
  'strategy_version',
])

export function DataLineage({ graph }: { graph: AtlasGraph }) {
  const [selected, setSelected] = useState<string | null>(null)

  const { nodes, edges } = useMemo(() => {
    const entities = graph.nodes.filter((n) => ENTITY_KINDS.has(n.kind))
    const artifacts = graph.nodes.filter((n) => n.kind === 'artifact')
    const ids = new Set([...entities, ...artifacts].map((n) => n.id))
    const selectionEdges = graph.edges.filter(
      (e) =>
        (e.type === 'depends_on' || e.type === 'produces') &&
        ids.has(e.source) &&
        ids.has(e.target),
    )
    const positions = new Map(
      layoutGraph(
        [...entities, ...artifacts].map((n) => ({ id: n.id })),
        selectionEdges.map((e) => ({ source: e.source, target: e.target })),
      ).map((p) => [p.id, p]),
    )
    const flowNodes: Node[] = [...entities, ...artifacts].map((n) => {
      const pos = positions.get(n.id)!
      const color = levelColor(n.evidence.level)
      const isEntity = ENTITY_KINDS.has(n.kind)
      return {
        id: n.id,
        position: { x: pos.x, y: pos.y },
        data: { label: n.label },
        style: {
          background: isEntity ? '#10151f' : '#0b0f16',
          color: '#dbe4f2',
          border: `1.5px solid ${color}`,
          borderRadius: isEntity ? 8 : 14,
          fontSize: 11.5,
          width: 180,
          boxShadow: n.id === selected ? `0 0 0 2px ${color}` : undefined,
        },
      }
    })
    const flowEdges: Edge[] = selectionEdges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.type === 'produces' ? 'produces' : undefined,
      labelStyle: { fill: '#8a93a6', fontSize: 9 },
      labelBgStyle: { fill: '#090c12' },
      style: {
        stroke: e.type === 'produces' ? '#8a93a6' : '#4f8dff',
        strokeDasharray: e.type === 'produces' ? '6 4' : undefined,
      },
    }))
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
          <NodePanel nodeId={selected} />
        ) : (
          <div className="placeholder">
            The research-entity chain (spec §13): Research Case → Hypothesis → Dataset →
            Experiment → Decision → Strategy Version, with the artifacts each step
            produces. Type-level in v1 — instance browsing is live state, not
            repository truth.
          </div>
        )}
      </aside>
    </>
  )
}
