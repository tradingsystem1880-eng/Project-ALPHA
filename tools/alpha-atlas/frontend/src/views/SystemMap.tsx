import type { Edge, Node } from '@xyflow/react'
import { useMemo, useState } from 'react'

import { atlasNodeStyle, GraphCanvas, styleNodes } from '../components/GraphCanvas'
import { NodePanel } from '../components/NodePanel'
import { layoutGraph } from '../model/layout'
import { selectSystemMap } from '../model/systemMap'
import type { AtlasGraph } from '../model/types'

export function SystemMap({ graph }: { graph: AtlasGraph }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const { baseNodes, edges } = useMemo(() => {
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
      const isComponent = n.kind === 'component'
      const unknownCount = isComponent ? (selection.unknowns.get(n.id) ?? 0) : 0
      return {
        id: n.id,
        position: { x: pos.x, y: pos.y },
        data: {
          label: unknownCount > 0 ? `${n.label} — ${unknownCount} unknown` : n.label,
          level: n.evidence.level,
        },
        style: atlasNodeStyle(n.evidence.level, {
          emphasis: isComponent,
          fontSize: isComponent ? 12 : 10.5,
          width: isComponent ? 190 : 210,
        }),
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
    return { baseNodes: flowNodes, edges: flowEdges }
  }, [graph, expanded])
  const nodes = useMemo(() => styleNodes(baseNodes, selected), [baseNodes, selected])

  return (
    <>
      <GraphCanvas
        nodes={nodes}
        edges={edges}
        onNodeClick={(id) => {
          setSelected(id)
          if (id.startsWith('component:')) {
            setExpanded((current) => (current === id ? null : id))
          }
        }}
      />
      <aside className="panel">
        {selected ? (
          <NodePanel nodeId={selected} />
        ) : (
          <div className="placeholder">
            Each box is a package, app, or worker; arrows summarize which imports which.
            Click a box to swap in its modules (one component at a time — click again to
            collapse). A <strong>“n unknown”</strong> badge means that many things inside
            it have no documentation, test, or cross-layer link yet — the review queue.
          </div>
        )}
      </aside>
    </>
  )
}
