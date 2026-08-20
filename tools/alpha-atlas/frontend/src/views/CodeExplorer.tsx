import type { Edge, Node } from '@xyflow/react'
import { useMemo, useState } from 'react'

import { atlasNodeStyle, GraphCanvas, styleNodes } from '../components/GraphCanvas'
import { NodePanel } from '../components/NodePanel'
import { layoutGraph } from '../model/layout'
import { selectComponentModules } from '../model/systemMap'
import type { AtlasGraph } from '../model/types'

export function CodeExplorer({ graph }: { graph: AtlasGraph }) {
  const components = useMemo(
    () =>
      graph.nodes
        .filter((n) => n.kind === 'component')
        .map((n) => n.id)
        .sort(),
    [graph],
  )
  const [chosen, setChosen] = useState<string | null>(null)
  const componentId = chosen ?? components[0] ?? ''
  const [selected, setSelected] = useState<string | null>(null)

  const { baseNodes, edges, external } = useMemo(() => {
    const selection = selectComponentModules(graph, componentId)
    const positions = new Map(
      layoutGraph(
        selection.modules.map((m) => ({ id: m.node.id })),
        selection.edges.map((e) => ({ source: e.source, target: e.target })),
        'TB',
      ).map((p) => [p.id, p]),
    )
    const flowNodes: Node[] = selection.modules.map(({ node: n, testCount }) => {
      const pos = positions.get(n.id)!
      const short = n.label.split('.').slice(1).join('.') || n.label
      return {
        id: n.id,
        position: { x: pos.x, y: pos.y },
        data: {
          label: testCount > 0 ? `${short} ✓${testCount}` : short,
          level: n.evidence.level,
        },
        style: atlasNodeStyle(n.evidence.level, { fontSize: 10.5, width: 200 }),
      }
    })
    const flowEdges: Edge[] = selection.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      style: { stroke: '#8a93a6', strokeDasharray: '2 4' },
    }))
    return { baseNodes: flowNodes, edges: flowEdges, external: selection.external }
  }, [graph, componentId])
  const nodes = useMemo(() => styleNodes(baseNodes, selected), [baseNodes, selected])

  return (
    <>
      <div className="flow">
        <div className="explorer-bar">
          <select value={componentId} onChange={(e) => setChosen(e.target.value)}>
            {components.map((id) => (
              <option key={id} value={id}>
                {id.replace('component:', '')}
              </option>
            ))}
          </select>
          <span className="hint">
            {nodes.length} modules · ✓n = validating test files · imports out:{' '}
            {[...external.entries()]
              .sort()
              .map(([id, count]) => `${id.replace('component:', '')} (${count})`)
              .join(', ') || 'none'}
          </span>
        </div>
        <GraphCanvas
          nodes={nodes}
          edges={edges}
          onNodeClick={setSelected}
          className="flow-canvas"
        />
      </div>
      <aside className="panel">
        {selected ? (
          <NodePanel nodeId={selected} />
        ) : (
          <div className="placeholder">
            Pick a component in the dropdown above to see its modules and how they import
            each other. <strong>✓n</strong> on a module = n test files exercise it; the
            bar also lists how many imports leave this component. Click any module for
            its evidence, tests, and AI-context prompt.
          </div>
        )}
      </aside>
    </>
  )
}
