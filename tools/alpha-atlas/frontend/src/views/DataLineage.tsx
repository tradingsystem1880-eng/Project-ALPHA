import type { Edge, Node } from '@xyflow/react'
import { useMemo, useState } from 'react'

import { atlasNodeStyle, GraphCanvas, styleNodes } from '../components/GraphCanvas'
import { NodePanel } from '../components/NodePanel'
import { layoutGraph } from '../model/layout'
import { ENTITY_KINDS } from '../model/lifecycle'
import type { AtlasGraph } from '../model/types'

export function DataLineage({ graph }: { graph: AtlasGraph }) {
  const [selected, setSelected] = useState<string | null>(null)

  const { baseNodes, edges } = useMemo(() => {
    const lineageNodes = graph.nodes.filter(
      (n) => ENTITY_KINDS.has(n.kind) || n.kind === 'artifact',
    )
    const ids = new Set(lineageNodes.map((n) => n.id))
    const selectionEdges = graph.edges.filter(
      (e) =>
        (e.type === 'depends_on' || e.type === 'produces') &&
        ids.has(e.source) &&
        ids.has(e.target),
    )
    const positions = new Map(
      layoutGraph(
        lineageNodes.map((n) => ({ id: n.id })),
        selectionEdges.map((e) => ({ source: e.source, target: e.target })),
      ).map((p) => [p.id, p]),
    )
    const flowNodes: Node[] = lineageNodes.map((n) => {
      const pos = positions.get(n.id)!
      const isEntity = ENTITY_KINDS.has(n.kind)
      return {
        id: n.id,
        position: { x: pos.x, y: pos.y },
        data: { label: n.label, level: n.evidence.level },
        style: atlasNodeStyle(n.evidence.level, {
          emphasis: isEntity,
          borderRadius: isEntity ? 8 : 14,
          fontSize: 11.5,
          width: 180,
        }),
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
    return { baseNodes: flowNodes, edges: flowEdges }
  }, [graph])
  const nodes = useMemo(() => styleNodes(baseNodes, selected), [baseNodes, selected])

  return (
    <>
      <GraphCanvas nodes={nodes} edges={edges} onNodeClick={setSelected} />
      <aside className="panel">
        {selected ? (
          <NodePanel nodeId={selected} />
        ) : (
          <div className="placeholder">
            How research knowledge flows (spec §13): a <strong>Research Case</strong>{' '}
            becomes a Hypothesis, meets a Dataset in an Experiment, reaches an Owner
            Decision, and only then a Strategy Version. Rounded boxes are the artifacts
            each step produces. Click anything for its definition and anchors. (Types,
            not live cases — instance browsing is runtime state, not repository truth.)
          </div>
        )}
      </aside>
    </>
  )
}
