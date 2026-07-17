// Run Detail — the full story of one stored run: A–F verdict, OOS metrics, an equity+drawdown
// chart, the gauntlet gate outcomes + fold/null/CI/DSR/CPCV tables, trades, forecast, and the
// embedded quantstats tear sheet. Everything is read from the manifest + parquet JSON projections.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'
import type uPlot from 'uplot'

import { api } from '../api/client'
import type { EquitySeries, ForecastSeries, RunDetail as RunDetailData, TradeRow } from '../api/types'
import { CHART } from '../util/chartTheme'
import { fmtNum } from '../util/format'
import { UplotChart } from '../components/UplotChart'

// ---- safe manifest accessors ------------------------------------------------------------------

type Dict = Record<string, unknown>
const asObj = (v: unknown): Dict | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Dict) : null
const asArr = (v: unknown): Dict[] => (Array.isArray(v) ? (v as Dict[]) : [])
const asNum = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null
const asStr = (v: unknown): string | null => (typeof v === 'string' ? v : null)

const METRIC_LABEL: Record<string, string> = {
  sharpe: 'Sharpe',
  cagr: 'CAGR',
  annualized_vol: 'Ann. Vol',
  max_drawdown: 'Max DD',
  total_return: 'Total Return',
  value_at_risk: 'VaR',
  expected_shortfall: 'ES',
  risk_of_ruin: 'Risk of Ruin',
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rd-section">
      <div className="rd-head">{title}</div>
      {children}
    </section>
  )
}

function MetricGrid({ metrics }: { metrics: Dict }) {
  const entries = Object.entries(metrics).filter(([, v]) => asNum(v) !== null)
  if (entries.length === 0) return null
  return (
    <div className="metric-grid">
      {entries.map(([k, v]) => (
        <div className="metric" key={k}>
          <span className="eyebrow">{METRIC_LABEL[k] ?? k}</span>
          <span className="metric-val num">{fmtNum(v, k === 'sharpe' ? 2 : 4)}</span>
        </div>
      ))}
    </div>
  )
}

// ---- charts -----------------------------------------------------------------------------------

const AXIS = {
  stroke: CHART.muted,
  font: CHART.font,
  grid: { stroke: CHART.grid, width: 1 },
  ticks: { stroke: CHART.grid, width: 1 },
}

function equityOptions(): Omit<uPlot.Options, 'width' | 'height'> {
  return {
    scales: { x: { time: true }, y: {}, dd: {} },
    axes: [
      { ...AXIS },
      { ...AXIS, scale: 'y' },
      {
        ...AXIS,
        scale: 'dd',
        side: 1,
        grid: { show: false },
        values: (_u, vals) => vals.map((v) => `${(v * 100).toFixed(0)}%`),
      },
    ],
    series: [
      {},
      { label: 'Equity', scale: 'y', stroke: CHART.accent, width: 1.5, points: { show: false } },
      {
        label: 'Drawdown',
        scale: 'dd',
        stroke: CHART.down,
        width: 1,
        fill: 'rgba(239, 83, 80, 0.12)',
        points: { show: false },
      },
    ],
    legend: { show: false },
    cursor: { points: { show: false } },
  }
}

function EquityPanel({ runId }: { runId: string }) {
  const [eq, setEq] = useState<EquitySeries | null>(null)
  useEffect(() => {
    let live = true
    api.equity(runId).then((e) => live && setEq(e))
    return () => {
      live = false
    }
  }, [runId])
  const data = useMemo<uPlot.AlignedData | null>(
    () => (eq && eq.ts.length ? [eq.ts, eq.equity, eq.drawdown] : null),
    [eq],
  )
  const options = useMemo(equityOptions, [])
  if (!data) return null
  return (
    <Section title="Equity & drawdown">
      <UplotChart data={data} options={options} height={240} />
    </Section>
  )
}

function forecastOptions(): Omit<uPlot.Options, 'width' | 'height'> {
  return {
    scales: { x: { time: true }, y: {} },
    axes: [{ ...AXIS }, { ...AXIS, scale: 'y' }],
    series: [
      {},
      { label: 'History', stroke: CHART.ink, width: 1.5, points: { show: false } },
      {
        label: 'Forecast',
        stroke: CHART.accent,
        width: 1.5,
        dash: [4, 3],
        points: { show: false },
      },
      { stroke: 'transparent', points: { show: false } },
      { stroke: 'transparent', points: { show: false } },
    ],
    bands: [{ series: [4, 3], fill: CHART.band }],
    legend: { show: false },
    cursor: { points: { show: false } },
  }
}

function ForecastPanel({ runId }: { runId: string }) {
  const [fc, setFc] = useState<ForecastSeries | null>(null)
  useEffect(() => {
    let live = true
    api.forecast(runId).then((f) => live && setFc(f))
    return () => {
      live = false
    }
  }, [runId])
  const data = useMemo<uPlot.AlignedData | null>(() => {
    if (!fc) return null
    const x = [...fc.history_ts, ...fc.forecast_ts]
    const nH = fc.history.length
    const hist = [...fc.history, ...fc.forecast.map(() => null)]
    const fcst = [
      ...fc.history.map((v, i) => (i === nH - 1 ? v : null)),
      ...fc.forecast,
    ]
    const pad = fc.history.map(() => null)
    const p90 = fc.p90 ? [...pad, ...fc.p90] : x.map(() => null)
    const p10 = fc.p10 ? [...pad, ...fc.p10] : x.map(() => null)
    return [x, hist, fcst, p90, p10] as uPlot.AlignedData
  }, [fc])
  const options = useMemo(forecastOptions, [])
  if (!data) return null
  return (
    <Section title="Forecast">
      <UplotChart data={data} options={options} height={240} />
    </Section>
  )
}

// ---- gauntlet + trades tables -----------------------------------------------------------------

function Outcomes({ outcomes }: { outcomes: Dict[] }) {
  if (!outcomes.length) return null
  return (
    <Section title="Gate outcomes">
      <div className="gates">
        {outcomes.map((o, i) => {
          const passed = o.passed === true
          return (
            <div className="gate" key={i}>
              <span className={`chip ${passed ? 'pass' : 'fail'}`}>{passed ? 'PASS' : 'FAIL'}</span>
              <span className="gate-name mono">{asStr(o.name) ?? '—'}</span>
              <span className="gate-detail muted">{asStr(o.detail) ?? ''}</span>
            </div>
          )
        })}
      </div>
    </Section>
  )
}

function FoldsTable({ folds }: { folds: Dict[] }) {
  if (!folds.length) return null
  return (
    <Section title="Walk-forward folds">
      <table className="blotter">
        <thead>
          <tr>
            <th>#</th>
            <th className="r">Test start</th>
            <th className="r">Test end</th>
            <th className="r">N</th>
            <th className="r">OOS Sharpe</th>
            <th className="r">OOS CAGR</th>
          </tr>
        </thead>
        <tbody>
          {folds.map((f, i) => (
            <tr key={i}>
              <td className="num">{asNum(f.index) ?? i}</td>
              <td className="num">{asStr(f.test_start) ?? '—'}</td>
              <td className="num">{asStr(f.test_end) ?? '—'}</td>
              <td className="num">{asNum(f.n_test) ?? '—'}</td>
              <td className="num">{fmtNum(f.oos_sharpe, 2)}</td>
              <td className="num">{fmtNum(f.oos_cagr, 3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}

function TradesTable({ runId }: { runId: string }) {
  const [rows, setRows] = useState<TradeRow[] | null>(null)
  useEffect(() => {
    let live = true
    api.trades(runId).then((t) => live && setRows(t))
    return () => {
      live = false
    }
  }, [runId])
  if (!rows || rows.length === 0) return null
  const cols = ['instrument_id', 'side', 'quantity', 'entry_price', 'exit_price', 'realized_return']
  return (
    <Section title={`Trades · ${rows.length}`}>
      <table className="blotter">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c} className={c === 'instrument_id' || c === 'side' ? '' : 'r'}>
                {c.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 500).map((r, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const v = r[c]
                const numeric = typeof v === 'number'
                return (
                  <td key={c} className={numeric ? 'num' : 'mono'}>
                    {numeric ? fmtNum(v, c === 'realized_return' ? 4 : 2) : String(v ?? '—')}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}

// ---- the panel --------------------------------------------------------------------------------

export function RunDetail(props: IDockviewPanelProps) {
  const runId = String((props.params as { runId?: string }).runId ?? '')
  const [detail, setDetail] = useState<RunDetailData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    let live = true
    setDetail(null)
    setError(null)
    api
      .run(runId)
      .then((d) => live && setDetail(d))
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [runId])

  if (!runId) return <div className="placeholder">no run selected</div>
  if (error) return <div className="placeholder"><div className="big">error</div>{error}</div>
  if (!detail) return <div className="placeholder">loading…</div>

  const m = detail.manifest
  const verdict = asObj(m.verdict)
  const oos = asObj(m.oos_metrics) ?? asObj(m.metrics)
  const outcomes = asArr(m.outcomes)
  const folds = asArr(m.folds)
  const dsr = asObj(m.dsr)
  const cpcv = asObj(m.cpcv)
  const command = asStr(m.command) ?? (detail.kind === 'runs' ? 'gauntlet' : detail.kind)
  const leak = asStr(m.leakage_warning)

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Run Detail</span>
        <span className="id mono">{runId}</span>
        <span className="chip kind">{command}</span>
      </div>
      <div className="panel-body panel-pad rd">
        {leak ? <div className="leak">⚠ {leak}</div> : null}

        {verdict ? (
          <div className="verdict-row">
            <span className={`verdict big g-${asStr(verdict.overall) ?? ''}`}>
              {asStr(verdict.overall) ?? '—'}
            </span>
            <div className="dims">
              {(['edge', 'robustness', 'risk', 'sample'] as const).map((d) => (
                <div className="dim" key={d}>
                  <span className="eyebrow">{d}</span>
                  <span className={`verdict g-${asStr(verdict[d]) ?? ''}`}>
                    {asStr(verdict[d]) ?? '—'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {oos ? (
          <Section title="Out-of-sample metrics">
            <MetricGrid metrics={oos} />
          </Section>
        ) : null}

        {detail.has_equity ? <EquityPanel runId={runId} /> : null}
        {detail.has_forecast ? <ForecastPanel runId={runId} /> : null}
        <Outcomes outcomes={outcomes} />
        <FoldsTable folds={folds} />

        {dsr || cpcv ? (
          <Section title="Deflated Sharpe · CPCV">
            <div className="metric-grid">
              {dsr ? (
                <>
                  <div className="metric">
                    <span className="eyebrow">PSR</span>
                    <span className="metric-val num">{fmtNum(dsr.psr, 3)}</span>
                  </div>
                  <div className="metric">
                    <span className="eyebrow">DSR</span>
                    <span className="metric-val num">{fmtNum(dsr.dsr, 3)}</span>
                  </div>
                </>
              ) : null}
              {cpcv ? (
                <>
                  <div className="metric">
                    <span className="eyebrow">CPCV mean</span>
                    <span className="metric-val num">{fmtNum(cpcv.mean_sharpe, 2)}</span>
                  </div>
                  <div className="metric">
                    <span className="eyebrow">Frac +</span>
                    <span className="metric-val num">{fmtNum(cpcv.frac_positive, 2)}</span>
                  </div>
                </>
              ) : null}
            </div>
          </Section>
        ) : null}

        {detail.has_trades ? <TradesTable runId={runId} /> : null}

        {detail.has_tearsheet ? (
          <Section title="Tear sheet">
            <iframe className="tearsheet" src={api.tearsheetUrl(runId)} title="Tear sheet" />
          </Section>
        ) : null}
      </div>
    </div>
  )
}
