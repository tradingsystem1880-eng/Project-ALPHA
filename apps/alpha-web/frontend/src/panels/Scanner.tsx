// Scanner document (spec 2026-09-01 §4.2 Phase 5 S5): save a scan (a saved rule set over every
// stored symbol or an explicit list), run it on point-in-time bars, read the signal on each
// symbol's last bar with the operand values the rule compared, and check it so changed signals
// become alerts in the Toolbox. Everything shown is `alpha scan` output; a scan is a screen of the
// current state, never evidence of an edge (authority: none).

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RuleSummary, ScanRunResult, ScanSummary } from '../api/types'
import { setLinked } from '../context/linked'
import type { PanelHandleProps } from '../context/panelHandle'
import { useAreaVersion } from '../state/activity'
import {
  SCAN_ID_PATTERN,
  formatValue,
  orderRows,
  parseUniverse,
  signalLabel,
  signalTone,
  universeText,
  valueColumns,
} from './scannerModel'

export function Scanner(_props: PanelHandleProps) {
  const [scans, setScans] = useState<ScanSummary[]>([])
  const [rules, setRules] = useState<RuleSummary[]>([])
  const [name, setName] = useState('')
  const [rule, setRule] = useState('')
  const [universe, setUniverse] = useState('')
  const [asOf, setAsOf] = useState('')
  const [result, setResult] = useState<ScanRunResult | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const barsVersion = useAreaVersion('bars')

  const refresh = useCallback(() => {
    api.scans().then((list) => setScans(list.scans)).catch((cause: unknown) => setError(String(cause)))
    api.rules().then((list) => setRules(list.rules.filter((row) => !row.error))).catch((cause: unknown) => setError(String(cause)))
  }, [])
  useEffect(refresh, [refresh, barsVersion])
  useEffect(() => {
    if (!rule && rules.length) setRule(rules[0].name)
  }, [rule, rules])

  const idOk = SCAN_ID_PATTERN.test(name.trim())
  const save = () => {
    if (!idOk || !rule) return
    setError(null)
    api
      .scanSave(name.trim(), rule, parseUniverse(universe))
      .then(() => {
        setNotice(`saved scan ${name.trim()}`)
        refresh()
      })
      .catch((cause: unknown) => setError(String(cause)))
  }

  const run = (scan: string) => {
    setBusy(scan)
    setError(null)
    setNotice(null)
    api
      .scanRun(scan, asOf.trim() || null)
      .then(setResult)
      .catch((cause: unknown) => setError(String(cause)))
      .finally(() => setBusy(null))
  }

  const check = (scan: string) => {
    setBusy(scan)
    setError(null)
    api
      .scanCheck(scan)
      .then((outcome) => {
        setNotice(`${scan}: ${outcome.alerts.length} new alert${outcome.alerts.length === 1 ? '' : 's'} (checked ${outcome.checks[0]?.checked_at ?? 'now'})`)
        refresh()
      })
      .catch((cause: unknown) => setError(String(cause)))
      .finally(() => setBusy(null))
  }

  const remove = (scan: string) => {
    setError(null)
    api
      .scanDelete(scan)
      .then(() => {
        if (result?.scan === scan) setResult(null)
        refresh()
      })
      .catch((cause: unknown) => setError(String(cause)))
  }

  const rows = result ? orderRows(result.rows) : []
  const columns = valueColumns(rows)
  return (
    <div className="panel scanner">
      <div className="panel-toolbar">
        <span className="title">Scanner</span>
        <span className="muted">rule sets over stored symbols · point-in-time · a screen, not evidence</span>
      </div>
      <div className="panel-body panel-pad scanner-layout">
        <section className="scanner-side" aria-label="Saved scans">
          <form
            className="scanner-new"
            aria-label="New scan"
            onSubmit={(event) => {
              event.preventDefault()
              save()
            }}
          >
            <label className="field-row">
              <span className="field-label">Scan name</span>
              <input className="field mono" value={name} onChange={(event) => setName(event.target.value)} placeholder="trend-crypto" spellCheck={false} />
            </label>
            <label className="field-row">
              <span className="field-label">Rule set</span>
              <select className="field" value={rule} onChange={(event) => setRule(event.target.value)}>
                {rules.length === 0 ? <option value="">save one in the Strategy Builder</option> : null}
                {rules.map((row) => (
                  <option key={row.name} value={row.name}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-row" title="Blank scans every stored symbol">
              <span className="field-label">Symbols (blank = all stored)</span>
              <input className="field mono" value={universe} onChange={(event) => setUniverse(event.target.value)} placeholder="BTC/USDT ETH/USDT" spellCheck={false} />
            </label>
            <button type="submit" className="btn primary" disabled={!idOk || !rule} title="alpha scan save">
              Save scan
            </button>
          </form>
          <h3>Saved scans</h3>
          {scans.length === 0 ? <p className="muted">none yet</p> : null}
          <ul className="scanner-list">
            {scans.map((scan) => (
              <li key={scan.name} className={result?.scan === scan.name ? 'active' : ''}>
                <div className="scanner-item">
                  <span className="mono">{scan.name}</span>
                  <span className="muted">
                    {scan.error ?? `${scan.rules} · ${universeText(scan)}`}
                    {scan.checked_at ? ` · checked ${scan.checked_at.slice(0, 16).replace('T', ' ')}` : ' · never checked'}
                  </span>
                </div>
                <div className="scanner-item-actions">
                  <button type="button" className="btn" disabled={busy !== null || Boolean(scan.error)} onClick={() => run(scan.name)} title="alpha scan run">
                    Run
                  </button>
                  <button type="button" className="btn" disabled={busy !== null || Boolean(scan.error)} onClick={() => check(scan.name)} title="alpha scan check — changed signals become alerts">
                    Check
                  </button>
                  <button type="button" className="btn" aria-label={`Delete scan ${scan.name}`} onClick={() => remove(scan.name)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <label className="field-row" title="Evaluate as of a past date: bars after it are excluded">
            <span className="field-label">As of (optional)</span>
            <input className="field mono" value={asOf} onChange={(event) => setAsOf(event.target.value)} placeholder="YYYY-MM-DD" spellCheck={false} />
          </label>
        </section>
        <section className="scanner-results" aria-label="Scan results">
          {notice ? <p className="muted" role="status">{notice}</p> : null}
          {error ? <p className="builder-error" role="alert">{error}</p> : null}
          {busy ? <p className="muted">running {busy}…</p> : null}
          {result ? (
            <>
              <p className="muted scanner-meta">
                <span className="mono">{result.scan}</span> · rules <span className="mono">{result.rules}</span> ({result.rules_sha256.slice(0, 12)}) ·{' '}
                {result.as_of ? `as of ${result.as_of}` : 'latest stored bars'} · universe listed {result.universe_as_of.slice(0, 16).replace('T', ' ')} ·{' '}
                {result.rows.length} evaluated, {result.skipped.length} skipped
              </p>
              <table className="blotter scanner-table" aria-label="Scan results">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Signal</th>
                    <th>Bar</th>
                    <th className="num">Close</th>
                    {columns.map((column) => (
                      <th key={column} className="num mono">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.symbol} className={`tone-${signalTone(row.signal)}`}>
                      <td>
                        <button type="button" className="watch-select" onClick={() => setLinked({ symbol: row.symbol })} title="Chart this symbol">
                          {row.symbol}
                        </button>
                      </td>
                      <td className={`scan-signal scan-signal--${signalTone(row.signal)}`}>{signalLabel(row.signal)}</td>
                      <td className="mono">{row.bar_date}</td>
                      <td className="num mono">{formatValue(row.close)}</td>
                      {columns.map((column) => (
                        <td key={column} className="num mono">
                          {formatValue(row.values[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.skipped.length ? (
                <details className="scanner-skipped">
                  <summary>{result.skipped.length} skipped</summary>
                  <ul>
                    {result.skipped.map((item) => (
                      <li key={item.symbol}>
                        <span className="mono">{item.symbol}</span> · {item.reason}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </>
          ) : (
            <p className="muted">Run a saved scan to see each symbol's signal on its last bar. Check appends changed signals to the Toolbox › Alerts log.</p>
          )}
        </section>
      </div>
    </div>
  )
}
