// Strategy Lab — a dynamic launch form built from /api/commands + /api/strategies. Pick a
// run-producing command, its symbol(s), a strategy + its tunable params, tweak options (only
// changed values are emitted), and launch; the run streams live and links to its Run Detail.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { CommandDef, StrategyDef } from '../api/types'
import { JobConsole } from '../components/JobConsole'
import { openRunDetail } from './actions'

const SKIP_OPTS = new Set(['param', 'grid', 'json', 'strategy'])

export function StrategyLab(props: IDockviewPanelProps) {
  const [commands, setCommands] = useState<CommandDef[]>([])
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [cmdId, setCmdId] = useState('backtest run')
  const [symbols, setSymbols] = useState('SPY')
  const [strategy, setStrategy] = useState('ts_momentum')
  const [params, setParams] = useState<Record<string, string>>({})
  const [opts, setOpts] = useState<Record<string, string>>({})
  const [grid, setGrid] = useState('lookback=126,252 vol_window=21,63')
  const [extra, setExtra] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.commands().then((c) => setCommands(c.filter((x) => x.run_type)))
    api.strategies().then(setStrategies)
  }, [])

  const cmd = useMemo(() => commands.find((c) => c.id === cmdId), [commands, cmdId])
  const stratDef = useMemo(
    () => strategies.find((s) => s.name === strategy),
    [strategies, strategy],
  )
  const hasStrategy = Boolean(cmd?.options.some((o) => o.name === 'strategy'))
  const hasGrid = Boolean(cmd?.options.some((o) => o.name === 'grid'))
  const symbolArg = cmd?.args.find((a) => a.name === 'symbol' || a.name === 'symbols')
  const variadic = symbolArg?.nargs === -1

  useEffect(() => {
    if (!cmd) return
    const d: Record<string, string> = {}
    for (const o of cmd.options)
      if (!SKIP_OPTS.has(o.name)) d[o.name] = o.default == null ? '' : String(o.default)
    setOpts(d)
  }, [cmd])

  useEffect(() => {
    if (!stratDef) return
    const d: Record<string, string> = {}
    for (const p of stratDef.params) d[p.name] = String(p.default)
    setParams(d)
  }, [stratDef])

  function launch(): void {
    if (!cmd) return
    const parts: string[] = []
    if (symbols.trim()) parts.push(symbols.trim())
    if (hasStrategy) parts.push('--strategy', strategy)
    if (hasStrategy && stratDef)
      for (const p of stratDef.params) {
        const v = params[p.name]
        if (v !== undefined && v !== '') parts.push('--param', `${p.name}=${v}`)
      }
    if (hasGrid && grid.trim())
      for (const axis of grid.trim().split(/\s+/)) parts.push('--grid', axis)
    for (const o of cmd.options) {
      if (SKIP_OPTS.has(o.name) || !o.flag) continue
      const v = opts[o.name]
      const def = o.default == null ? '' : String(o.default)
      if (v === undefined || v === '' || v === def) continue
      if (o.type === 'bool') parts.push(v === 'true' ? o.flag : o.flag.replace('--', '--no-'))
      else parts.push(o.flag, v)
    }
    if (extra.trim()) parts.push(extra.trim())
    setError(null)
    api
      .launch(cmd.id, parts.join(' '))
      .then((r) => setJobId(r.job_id))
      .catch((e: unknown) => setError(String(e)))
  }

  function openRun(runId: string): void {
    openRunDetail(props.containerApi, runId)
  }

  const shownOpts = cmd?.options.filter((o) => !SKIP_OPTS.has(o.name)) ?? []

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Strategy Lab</span>
      </div>
      <div className="panel-body panel-pad lab">
        <div className="lab-row">
          <label className="field-row">
            <span className="field-label">Command</span>
            <select className="field" value={cmdId} onChange={(e) => setCmdId(e.target.value)}>
              {commands.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id}
                </option>
              ))}
            </select>
          </label>
          <label className="field-row">
            <span className="field-label">{variadic ? 'Symbols (space-sep)' : 'Symbol'}</span>
            <input
              className="field"
              value={symbols}
              onChange={(e) => setSymbols(e.target.value)}
              placeholder={variadic ? 'SPY QQQ GLD' : 'SPY'}
            />
          </label>
        </div>

        {hasStrategy ? (
          <div className="lab-row">
            <label className="field-row">
              <span className="field-label">Strategy</span>
              <select
                className="field"
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
              >
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            {stratDef?.params.map((p) => (
              <label className="field-row" key={p.name} title={p.help}>
                <span className="field-label">{p.name}</span>
                <input
                  className="field"
                  value={params[p.name] ?? ''}
                  onChange={(e) => setParams((s) => ({ ...s, [p.name]: e.target.value }))}
                />
              </label>
            ))}
          </div>
        ) : null}

        {hasGrid ? (
          <label className="field-row">
            <span className="field-label">Grid axes (name=v1,v2 …)</span>
            <input className="field" value={grid} onChange={(e) => setGrid(e.target.value)} />
          </label>
        ) : null}

        <details className="lab-advanced">
          <summary>Options ({shownOpts.length})</summary>
          <div className="lab-grid">
            {shownOpts.map((o) => (
              <label className="field-row" key={o.name} title={o.help}>
                <span className="field-label">{o.name}</span>
                {o.type === 'bool' ? (
                  <select
                    className="field"
                    value={opts[o.name] ?? ''}
                    onChange={(e) => setOpts((s) => ({ ...s, [o.name]: e.target.value }))}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                ) : o.choices ? (
                  <select
                    className="field"
                    value={opts[o.name] ?? ''}
                    onChange={(e) => setOpts((s) => ({ ...s, [o.name]: e.target.value }))}
                  >
                    {o.choices.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="field"
                    value={opts[o.name] ?? ''}
                    onChange={(e) => setOpts((s) => ({ ...s, [o.name]: e.target.value }))}
                  />
                )}
              </label>
            ))}
          </div>
        </details>

        <label className="field-row">
          <span className="field-label">Additional flags</span>
          <input
            className="field"
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
            placeholder="--null-model garch"
          />
        </label>

        <div className="lab-actions">
          <button className="btn primary" onClick={launch}>
            ▶ Launch {cmdId}
          </button>
          <span className="mono muted">alpha {cmdId} {symbols} …</span>
        </div>
        {error ? <div className="leak">⚠ {error}</div> : null}
        {jobId ? <JobConsole jobId={jobId} onRun={openRun} /> : null}
      </div>
    </div>
  )
}
