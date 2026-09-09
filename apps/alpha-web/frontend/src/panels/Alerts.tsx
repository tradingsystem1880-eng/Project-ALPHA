// Toolbox › Alerts (spec 2026-09-01 §4.2 Phase 5 S5): the scan alert log, newest first. Every row
// is a signal that *changed* at an `alpha scan check`; the live desk's `alerts` area re-reads the
// log when the CLI appends to it, and mounting or a `bars` change (a finished pull) checks every
// saved scan so the owner never has to remember to. Display only, authority none.

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ScanAlert } from '../api/types'
import { setLinked } from '../context/linked'
import type { PanelHandleProps } from '../context/panelHandle'
import { useAreaVersion } from '../state/activity'
import { alertTransition, newestFirst, signalTone } from './scannerModel'

export function Alerts(_props: PanelHandleProps) {
  const [alerts, setAlerts] = useState<ScanAlert[]>([])
  const [checkedAt, setCheckedAt] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const alertsVersion = useAreaVersion('alerts')
  const barsVersion = useAreaVersion('bars')

  const load = useCallback(() => {
    api
      .alerts(200)
      .then((result) => setAlerts(newestFirst(result.alerts)))
      .catch((cause: unknown) => setError(String(cause)))
  }, [])
  useEffect(load, [load, alertsVersion])

  const checkAll = useCallback(() => {
    setBusy(true)
    setError(null)
    api
      .scanCheckAll()
      .then((result) => {
        setCheckedAt(result.checks.at(-1)?.checked_at ?? new Date().toISOString())
        load()
      })
      .catch((cause: unknown) => setError(String(cause)))
      .finally(() => setBusy(false))
  }, [load])

  // On mount and after every store change (a pull landed) check every saved scan once, so the
  // owner never has to remember to.
  useEffect(checkAll, [checkAll, barsVersion])

  return (
    <div className="dock-panel alerts-panel">
      <div className="dock-toolbar">
        <span className="muted">
          {alerts.length} alert{alerts.length === 1 ? '' : 's'}
          {checkedAt ? ` · last check ${checkedAt.slice(0, 16).replace('T', ' ')} UTC` : ''}
        </span>
        <span className="spacer" />
        <button type="button" className="btn" disabled={busy} onClick={checkAll} title="alpha scan check — every saved scan; only changed signals are new alerts">
          {busy ? 'Checking…' : 'Check all scans'}
        </button>
      </div>
      {error ? <p className="builder-error" role="alert">{error}</p> : null}
      {alerts.length === 0 ? (
        <p className="muted alerts-empty">No alerts yet. Save a scan in the Scanner document; a check after each data pull appends a row here when a symbol's signal changes.</p>
      ) : (
        <table className="blotter alerts-table" aria-label="Scan alerts">
          <thead>
            <tr>
              <th>Time (UTC)</th>
              <th>Scan</th>
              <th>Symbol</th>
              <th>Change</th>
              <th>Bar</th>
              <th className="num">Close</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert, index) => (
              <tr key={`${alert.ts}:${alert.scan}:${alert.symbol}:${index}`} className={`tone-${signalTone(alert.signal)}`}>
                <td className="mono">{alert.ts.slice(0, 19).replace('T', ' ')}</td>
                <td className="mono">{alert.scan}</td>
                <td>
                  <button type="button" className="watch-select" onClick={() => setLinked({ symbol: alert.symbol })} title="Chart this symbol">
                    {alert.symbol}
                  </button>
                </td>
                <td className={`scan-signal scan-signal--${signalTone(alert.signal)}`}>{alertTransition(alert)}</td>
                <td className="mono">{alert.bar_date}</td>
                <td className="num mono">{alert.close}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
