import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { AssetSelect } from '../components/AssetSelect'
import type { PanelSource } from './chartWorkspaceModel'
export function PanelSourceEditor({ onChange, onClose }: { onChange: (source: PanelSource) => void; onClose: () => void }) {
  const [runs, setRuns] = useState<RunListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { let live = true; api.runs('?limit=100').then(v => { if (live) setRuns(v.items) }).catch(e => { if (live) setError(String(e)) }); return () => { live = false } }, [])
  const choose = (source: PanelSource) => { onChange(source); onClose() }
  return <div className="panel-source-editor" role="dialog" aria-label="Replace panel source"><header>Pin an exact panel source<button className="btn" onClick={onClose}>Close source selector</button></header><p>Changing this panel does not change canonical research context.</p>
    <AssetSelect value="" label="Panel asset" onChange={symbol => choose({ kind: 'market', symbol, start: null, end: null, snapshotId: null })} onArchiveSelect={dataset => choose({ kind: 'archive', dataset })}/>
    <label>Recorded run<select className="field" aria-label="Panel recorded run" defaultValue="" onChange={e => e.target.value && choose({ kind: 'run', runId: e.target.value })}><option value="">Choose a recorded run…</option>{runs.map(r => <option value={r.run_id} key={r.run_id}>{r.display_name} · {r.run_id}</option>)}</select></label>{error ? <p role="alert">Run library unavailable: {error}</p> : null}
  </div>
}
