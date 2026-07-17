// Data Explorer — the symbols in the store (click to broadcast to the linked context) and a form to
// pull new data through the CLI.

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import { setLinked } from '../context/linked'
import { JobConsole } from '../components/JobConsole'

export function DataExplorer() {
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [sym, setSym] = useState('AAPL')
  const [source, setSource] = useState('yfinance')
  const [start, setStart] = useState('2015-01-01')
  const [end, setEnd] = useState('2024-12-31')
  const [jobId, setJobId] = useState<string | null>(null)

  const load = useCallback(() => {
    api.symbols().then((s) => setSymbols(s.symbols))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function pull(): void {
    api
      .launch('data pull', `${sym} --source ${source} --start ${start} --end ${end}`)
      .then((r) => setJobId(r.job_id))
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Data Explorer</span>
        {symbols ? <span className="count">{symbols.length}</span> : null}
        <div className="spacer" />
        <button className="btn" onClick={load}>
          refresh
        </button>
      </div>
      <div className="panel-body panel-pad de">
        <div className="rd-head">Stored symbols</div>
        {symbols === null ? (
          <div className="placeholder">loading…</div>
        ) : symbols.length === 0 ? (
          <div className="muted">No symbols stored yet — pull some below.</div>
        ) : (
          <div className="sym-chips">
            {symbols.map((s) => (
              <button key={s} className="sym-chip" onClick={() => setLinked({ symbol: s })}>
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="rd-head de-pull">Pull data</div>
        <div className="lab-row">
          <label className="field-row">
            <span className="field-label">Symbol</span>
            <input className="field" value={sym} onChange={(e) => setSym(e.target.value)} />
          </label>
          <label className="field-row">
            <span className="field-label">Source</span>
            <select className="field" value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="yfinance">yfinance</option>
              <option value="ccxt">ccxt</option>
              <option value="stooq">stooq</option>
            </select>
          </label>
          <label className="field-row">
            <span className="field-label">Start</span>
            <input className="field" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="field-row">
            <span className="field-label">End</span>
            <input className="field" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
        <div className="lab-actions">
          <button className="btn primary" onClick={pull}>
            ⤓ Pull
          </button>
          <span className="muted mono">needs network</span>
        </div>
        {jobId ? <JobConsole jobId={jobId} onDone={load} /> : null}
      </div>
    </div>
  )
}
