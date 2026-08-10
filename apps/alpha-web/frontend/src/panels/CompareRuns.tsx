/**
 * Runs side by side.
 *
 * The comparison endpoint has existed since v3 and nothing has ever called it, so the only
 * way to compare two runs was to open both and read them alternately. This puts their
 * metrics in one table and their figures in one column, with the values that differ picked
 * out — the point of a comparison is the difference, not the numbers.
 */

import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { PanelHandleProps } from '../context/panelHandle'
import type { RunComparison, RunListItem } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { FigureCard } from '../components/FigureCard'
import type { FigureCatalogueItem } from '../api/types'
import { useActivityField } from '../state/activity'
import { fmtNum, shortId } from '../util/format'

const MAX_RUNS = 8

function useRunIndex(): RunListItem[] {
  const version = useActivityField('runsVersion')
  const [runs, setRuns] = useState<RunListItem[]>([])
  useEffect(() => {
    let live = true
    void api
      .runs('?limit=500')
      .then((list) => live && setRuns(list.items))
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [version])
  return runs
}

export function CompareRuns(_props: PanelHandleProps) {
  const runs = useRunIndex()
  const [selected, setSelected] = useState<string[]>([])
  const [comparison, setComparison] = useState<RunComparison | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [figureId, setFigureId] = useState('equity_underwater')

  useEffect(() => {
    if (selected.length < 2) {
      setComparison(null)
      return
    }
    let live = true
    setError(null)
    api
      .compareRuns(selected)
      .then((value) => live && setComparison(value))
      .catch((cause: unknown) => live && setError(String(cause)))
    return () => {
      live = false
    }
  }, [selected])

  const metricNames = useMemo(() => {
    if (!comparison) return []
    const names = new Set<string>()
    for (const row of comparison.rows) for (const metric of row.metrics) names.add(metric.name)
    return [...names].sort()
  }, [comparison])

  const toggle = (runId: string) =>
    setSelected((current) =>
      current.includes(runId)
        ? current.filter((item) => item !== runId)
        : current.length >= MAX_RUNS
          ? current
          : [...current, runId],
    )

  return (
    <div className="panel compare">
      <div className="panel-toolbar">
        <span className="title">Compare</span>
        <span className="muted">
          {selected.length ? `${selected.length} of ${MAX_RUNS} selected` : 'pick two or more runs'}
        </span>
        <span className="spacer" />
        {selected.length ? (
          <button className="btn ghost" onClick={() => setSelected([])}>
            Clear
          </button>
        ) : null}
      </div>

      <div className="compare-body">
        <div className="compare-picker">
          <p className="eyebrow">Runs</p>
          <div className="compare-picker-list">
            {runs.map((item) => (
              <label key={item.run_id} className="compare-pick">
                <input
                  type="checkbox"
                  checked={selected.includes(item.run_id)}
                  onChange={() => toggle(item.run_id)}
                />
                <span className="mono">{shortId(item.run_id)}</span>
                <span className="library-row-sub">{item.label ?? item.command ?? item.kind}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="compare-main">
          {error ? <Placeholder big="Comparison failed">{error}</Placeholder> : null}
          {!error && selected.length < 2 ? (
            <Placeholder big="Select at least two runs">
              Their metrics and figures will line up here.
            </Placeholder>
          ) : null}

          {comparison ? (
            <>
              {!comparison.same_snapshot_hash ? (
                <p className="compare-warning">
                  These runs used different data snapshots, so differences may come from the data
                  rather than the strategies.
                </p>
              ) : null}

              <table className="blotter compare-table">
                <caption className="sr-only">Metric comparison</caption>
                <thead>
                  <tr>
                    <th scope="col">Metric</th>
                    {comparison.rows.map((row) => (
                      <th key={row.run_id} scope="col" className="mono">
                        {shortId(row.run_id)}
                        <span className="library-row-sub">{row.symbol ?? row.command}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {metricNames.map((name) => {
                    const values = comparison.rows.map(
                      (row) => row.metrics.find((metric) => metric.name === name)?.value ?? null,
                    )
                    const numeric = values.filter((value): value is number => value !== null)
                    const best = numeric.length ? Math.max(...numeric) : null
                    return (
                      <tr key={name}>
                        <th scope="row">{name}</th>
                        {values.map((value, index) => (
                          <td
                            key={comparison.rows[index].run_id}
                            className={`num${value !== null && value === best && numeric.length > 1 ? ' best' : ''}`}
                          >
                            {value === null ? '—' : fmtNum(value, 4)}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              <div className="compare-figures">
                <label className="compare-figure-pick">
                  <span className="eyebrow">Figure</span>
                  <select
                    className="field"
                    value={figureId}
                    onChange={(event) => setFigureId(event.target.value)}
                  >
                    <option value="equity_underwater">Equity and drawdown</option>
                    <option value="equity_vs_passive">Strategy versus passive</option>
                    <option value="rolling_risk">Rolling risk</option>
                    <option value="monthly_heatmap">Monthly returns</option>
                    <option value="return_distribution">Return distribution</option>
                  </select>
                </label>
                {comparison.rows.map((row) => (
                  <FigureCard
                    key={`${row.run_id}-${figureId}`}
                    runId={row.run_id}
                    item={
                      {
                        figure_id: figureId,
                        title: `${shortId(row.run_id)} · ${row.symbol ?? row.command}`,
                        summary: 'Comparison figure.',
                        section: 'performance',
                        panel_count: 2,
                        available: true,
                        unavailable_reason: null,
                      } satisfies FigureCatalogueItem
                    }
                  />
                ))}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
