import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react'
import type { CSSProperties } from 'react'

import { levelColor } from '../model/evidence'
import type { EvidenceLevel } from '../model/types'

/** Base style for an Atlas flow node; the selection ring is applied by styleNodes. */
export function atlasNodeStyle(
  level: EvidenceLevel,
  opts: { emphasis?: boolean; fontSize?: number; width?: number; borderRadius?: number } = {},
): CSSProperties {
  return {
    background: opts.emphasis ? '#10151f' : '#0b0f16',
    color: '#dbe4f2',
    border: `1.5px solid ${levelColor(level)}`,
    borderRadius: opts.borderRadius ?? 8,
    fontSize: opts.fontSize ?? 12,
    width: opts.width ?? 190,
  }
}

/** Apply the selection ring without invalidating the layout memo. */
export function styleNodes(nodes: Node[], selected: string | null): Node[] {
  if (selected === null) return nodes
  return nodes.map((n) =>
    n.id === selected
      ? {
          ...n,
          style: {
            ...n.style,
            boxShadow: `0 0 0 2px ${levelColor(n.data.level as EvidenceLevel)}`,
          },
        }
      : n,
  )
}

/** The one React Flow configuration every Atlas graph view shares. */
export function GraphCanvas({
  nodes,
  edges,
  onNodeClick,
  className = 'flow',
}: {
  nodes: Node[]
  edges: Edge[]
  onNodeClick: (id: string) => void
  className?: string
}) {
  return (
    <div className={className}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={(_, node) => onNodeClick(node.id)}
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
  )
}
