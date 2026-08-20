import { useMemo, useState } from 'react'

import { NodePanel } from '../components/NodePanel'
import { levelColor } from '../model/evidence'
import { computeImpact } from '../model/impact'
import type { AtlasGraph } from '../model/types'

const PICKABLE = new Set(['module', 'component', 'cli_command', 'mcp_tool', 'api_route', 'panel'])

export function ChangeImpact({ graph }: { graph: AtlasGraph }) {
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<string | null>(null)

  const candidates = useMemo(
    () =>
      graph.nodes
        .filter((n) => PICKABLE.has(n.kind))
        .map((n) => n.id)
        .sort(),
    [graph],
  )
  const valid = picked !== null && candidates.includes(picked)
  const impact = useMemo(
    () => (valid ? computeImpact(graph, picked) : null),
    [graph, picked, valid],
  )

  return (
    <>
      <div className="flow">
        <div className="explorer-bar">
          <input
            list="impact-nodes"
            placeholder="Pick a node (module:…, cli:…, mcp:…, route:…)"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              if (candidates.includes(e.target.value)) setPicked(e.target.value)
            }}
          />
          <datalist id="impact-nodes">
            {candidates.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
          {impact && (
            <span className="hint">
              {impact.impacted.length} nodes in the blast radius · {impact.tests.length} test
              file(s) exercise it
            </span>
          )}
        </div>
        <div className="impact-body">
          {!impact && (
            <div className="placeholder">
              “If I change this, what breaks?” — type or pick a node id above (try{' '}
              <strong>module:alpha_data.pit</strong>) to list everything that transitively
              builds on it, nearest first, plus the test files that would exercise the
              change.
            </div>
          )}
          {impact && (
            <>
              <h3>Blast radius (by distance)</h3>
              <ul>
                {impact.impacted.slice(0, 200).map(({ node, depth }) => (
                  <li key={node.id} className="prov">
                    <span className="badge" style={{ background: levelColor(node.evidence.level) }}>
                      {depth}
                    </span>{' '}
                    {node.id}
                  </li>
                ))}
                {impact.impacted.length > 200 && (
                  <li>… and {impact.impacted.length - 200} more</li>
                )}
              </ul>
              <h3>Affected tests</h3>
              <ul>
                {impact.tests.slice(0, 60).map((id) => (
                  <li key={id} className="prov">
                    {id.replace('test:', '')}
                  </li>
                ))}
                {impact.tests.length > 60 && <li>… and {impact.tests.length - 60} more</li>}
                {impact.tests.length === 0 && <li>none recorded</li>}
              </ul>
            </>
          )}
        </div>
      </div>
      <aside className="panel">
        {valid ? (
          <NodePanel nodeId={picked} />
        ) : (
          <div className="placeholder">The picked node&apos;s explanation appears here.</div>
        )}
      </aside>
    </>
  )
}
