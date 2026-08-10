// Native terminal tear sheet. It renders only values already present in typed run projections;
// missing calendar/distribution/rolling artifacts stay explicit instead of being recomputed here.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'
import type uPlot from 'uplot'

import { api } from '../api/client'
import type {
  EquitySeries,
  NativeTearSheetProjection,
  RunDetail,
  TradeRow,
} from '../api/types'
import { EquityChart } from '../components/charts/EquityChart'
import { PanelLinkControl } from '../components/PanelLinkControl'
import { Placeholder } from '../components/Placeholder'
import { UplotChart } from '../components/UplotChart'
import { usePanelLinked } from '../context/usePanelLinked'
import type { FoldRow } from '../explain/types'
import { AXIS, CHART } from '../util/chartTheme'
import { fmtPct, shortId } from '../util/format'
import { researchGateWatermark } from './researchGateModel'
import {
  buildCalendarRows,
  matchesRunScope,
  runScopeFromParams,
  runScopeLabel,
} from './v3Models'
import { MetricGrid, Section } from './rundetail/common'
import { asObj, type Dict } from './rundetail/commonUtils'
import { TradesTab } from './rundetail/TradesTab'

function metricsFor(manifest: Dict): Dict | null {
  return asObj(manifest.oos_metrics) ?? asObj(manifest.metrics)
}

function metadataFor(manifest: Dict): Dict {
  return asObj(manifest.metadata) ?? manifest
}

function displayValue(value: unknown): string | null {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
    return value.join(', ')
  }
  return null
}

function ArtifactGap({ title, contract }: { title: string; contract: string }) {
  return (
    <div className="tear-gap">
      <div className="tear-gap-title">{title}</div>
      <div className="tear-gap-state mono">ARTIFACT NOT EMITTED</div>
      <p>
        Waiting for <code>{contract}</code>. The workstation will not derive this statistic from
        another series.
      </p>
    </div>
  )
}

function ExplicitUnavailable({ title, reason }: { title: string; reason: string | null | undefined }) {
  return (
    <div className="tear-gap">
      <div className="tear-gap-title">{title}</div>
      <div className="tear-gap-state mono">EXPLICITLY UNAVAILABLE</div>
      <p>{reason ?? 'The authoritative artifact records that this metric is not available for this run type.'}</p>
    </div>
  )
}

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

function returnCell(value: number | null): string {
  if (value === null) return 'transparent'
  const alpha = Math.min(0.72, 0.12 + Math.abs(value) * 5)
  return value >= 0 ? `rgba(46, 160, 74, ${alpha})` : `rgba(239, 83, 80, ${alpha})`
}

function CalendarReturns({ native }: { native: NativeTearSheetProjection }) {
  const rows = buildCalendarRows(native.calendar_returns)
  return (
    <div className="native-calendar-wrap">
      <div className="native-calendar" role="table" aria-label="Monthly return heatmap">
        <div className="calendar-label mono">YEAR</div>
        {MONTHS.map((month) => <div className="calendar-label mono" key={month}>{month}</div>)}
        {rows.flatMap((row) => [
          <div className="calendar-year mono" key={`${row.year}-year`}>{row.year}</div>,
          ...row.months.map((value, index) => (
            <div
              className="calendar-cell mono"
              key={`${row.year}-${index}`}
              style={{ background: returnCell(value) }}
              title={`${row.year}-${String(index + 1).padStart(2, '0')}: ${fmtPct(value, 2)}`}
            >
              {value === null ? '—' : fmtPct(value, 1)}
            </div>
          )),
        ])}
      </div>
      <div className="year-return-row">
        {native.yearly_returns.map((row) => (
          <div key={row.year}><span className="eyebrow">{row.year}</span><span className={`mono ${row.return_value < 0 ? 'neg' : 'pos'}`}>{fmtPct(row.return_value, 2)}</span></div>
        ))}
      </div>
    </div>
  )
}

function DistributionCharts({ native }: { native: NativeTearSheetProjection }) {
  const qqData = useMemo<uPlot.AlignedData>(
    () => [native.qq.map((row) => row.theoretical), native.qq.map((row) => row.sample)] as uPlot.AlignedData,
    [native.qq],
  )
  const qqOptions = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(
    () => ({
      scales: { x: {}, y: {} },
      axes: [{ ...AXIS, label: 'NORMAL QUANTILE' }, { ...AXIS, scale: 'y', label: 'SAMPLE RETURN' }],
      series: [{}, { label: 'Q-Q', stroke: CHART.accent, width: 1, points: { show: true, size: 3 } }],
      legend: { show: false },
      cursor: { points: { show: false } },
    }),
    [],
  )
  const maxCount = Math.max(1, ...native.histogram.map((row) => row.count))
  return (
    <div className="native-dual-chart">
      <div>
        <div className="chart-subhead">Return distribution · x return / y count</div>
        <svg className="native-histogram" viewBox="0 0 500 175" role="img" aria-label="Histogram of Python-authored periodic returns">
          <line x1="38" x2="490" y1="150" y2="150" stroke={CHART.line} />
          {native.histogram.map((row, index) => {
            const width = 452 / Math.max(1, native.histogram.length)
            const height = (row.count / maxCount) * 130
            return <rect key={row.left} x={38 + index * width + 0.5} y={150 - height} width={Math.max(1, width - 1)} height={height} fill={CHART.accent} opacity="0.65"><title>{`${row.count} observations in [${fmtPct(row.left, 2)}, ${fmtPct(row.right, 2)})`}</title></rect>
          })}
          <text x="38" y="168" className="svg-num">{fmtPct(native.histogram[0]?.left, 1)}</text>
          <text x="490" y="168" textAnchor="end" className="svg-num">{fmtPct(native.histogram.at(-1)?.right, 1)}</text>
          <text x="264" y="168" textAnchor="middle" className="svg-num">RETURN</text>
        </svg>
      </div>
      <div><div className="chart-subhead">Normal Q-Q</div><UplotChart data={qqData} options={qqOptions} height={175} /></div>
      <details className="native-data-table">
        <summary>distribution / Q-Q table alternative</summary>
        <table className="blotter compact"><thead><tr><th>bin</th><th className="r">left</th><th className="r">right</th><th className="r">count</th></tr></thead><tbody>{native.histogram.map((row, index) => <tr key={row.left}><td className="mono">{index + 1}</td><td className="num">{row.left}</td><td className="num">{row.right}</td><td className="num">{row.count}</td></tr>)}</tbody></table>
      </details>
    </div>
  )
}

function RollingChart({ native }: { native: NativeTearSheetProjection }) {
  const data = useMemo<uPlot.AlignedData>(() => [
    native.rolling.map((row) => row.ts),
    native.rolling.map((row) => row.return_value),
    native.rolling.map((row) => row.volatility),
    native.rolling.map((row) => row.sharpe),
  ] as uPlot.AlignedData, [native.rolling])
  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(() => ({
    scales: { x: { time: true }, pct: {}, sharpe: {} },
    axes: [
      { ...AXIS, label: 'UTC' },
      { ...AXIS, scale: 'pct', label: 'RETURN / VOL', values: (_u, ticks) => ticks.map((value) => fmtPct(value, 0)) },
      { ...AXIS, scale: 'sharpe', side: 1, label: 'SHARPE' },
    ],
    series: [
      {},
      { label: 'Rolling return', scale: 'pct', stroke: CHART.accent, width: 1.5, points: { show: false } },
      { label: 'Rolling volatility', scale: 'pct', stroke: CHART.gold, width: 1, points: { show: false } },
      { label: 'Rolling Sharpe', scale: 'sharpe', stroke: CHART.ink, width: 1, points: { show: false } },
    ],
    legend: { show: true },
    cursor: { points: { show: false } },
  }), [])
  return (
    <div>
      <UplotChart data={data} options={options} height={230} />
      <details className="native-data-table"><summary>rolling table alternative</summary><table className="blotter compact"><thead><tr><th>UTC</th><th className="r">return</th><th className="r">volatility</th><th className="r">Sharpe</th></tr></thead><tbody>{native.rolling.map((row) => <tr key={row.ts}><td className="mono">{new Date(row.ts * 1_000).toISOString()}</td><td className="num">{fmtPct(row.return_value, 2)}</td><td className="num">{fmtPct(row.volatility, 2)}</td><td className="num">{row.sharpe?.toFixed(3) ?? '—'}</td></tr>)}</tbody></table></details>
    </div>
  )
}

function ExposureTurnoverChart({ native }: { native: NativeTearSheetProjection }) {
  const data = useMemo<uPlot.AlignedData>(() => [
    native.exposure_turnover.map((row) => row.end_ts),
    native.exposure_turnover.map((row) => row.gross_exposure),
    native.exposure_turnover.map((row) => row.net_exposure),
    native.exposure_turnover.map((row) => row.turnover),
  ] as uPlot.AlignedData, [native.exposure_turnover])
  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(() => ({
    scales: { x: { time: true }, exposure: {}, turnover: {} },
    axes: [
      { ...AXIS, label: 'UTC' },
      { ...AXIS, scale: 'exposure', label: 'EXPOSURE', values: (_u, ticks) => ticks.map((value) => fmtPct(value, 0)) },
      { ...AXIS, scale: 'turnover', side: 1, label: 'TURNOVER', values: (_u, ticks) => ticks.map((value) => fmtPct(value, 0)) },
    ],
    series: [
      {},
      { label: 'Gross exposure', scale: 'exposure', stroke: CHART.accent, width: 1.5, points: { show: false } },
      { label: 'Net exposure', scale: 'exposure', stroke: CHART.ink, width: 1, points: { show: false } },
      { label: 'Turnover', scale: 'turnover', stroke: CHART.gold, width: 1, points: { show: false } },
    ],
    legend: { show: true },
    cursor: { points: { show: false } },
  }), [])
  return (
    <div>
      <UplotChart data={data} options={options} height={210} />
      <details className="native-data-table"><summary>exposure / turnover table alternative</summary><table className="blotter compact"><thead><tr><th>interval end UTC</th><th className="r">gross</th><th className="r">net</th><th className="r">turnover</th></tr></thead><tbody>{native.exposure_turnover.map((row) => <tr key={row.end_ts}><td className="mono">{new Date(row.end_ts * 1_000).toISOString()}</td><td className="num">{fmtPct(row.gross_exposure, 2)}</td><td className="num">{fmtPct(row.net_exposure, 2)}</td><td className="num">{fmtPct(row.turnover, 2)}</td></tr>)}</tbody></table></details>
    </div>
  )
}

function BenchmarkChart({ native }: { native: NativeTearSheetProjection }) {
  const data = useMemo<uPlot.AlignedData>(() => [
    native.benchmark.map((row) => row.ts),
    native.benchmark.map((row) => row.strategy_equity),
    native.benchmark.map((row) => row.benchmark_equity),
  ] as uPlot.AlignedData, [native.benchmark])
  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(() => ({
    scales: { x: { time: true }, equity: {} },
    axes: [{ ...AXIS, label: 'UTC' }, { ...AXIS, scale: 'equity', label: 'NORMALIZED EQUITY' }],
    series: [
      {},
      { label: 'Strategy', scale: 'equity', stroke: CHART.accent, width: 1.5, points: { show: false } },
      { label: 'Benchmark', scale: 'equity', stroke: CHART.ink, width: 1, points: { show: false } },
    ],
    legend: { show: true },
    cursor: { points: { show: false } },
  }), [])
  return (
    <div>
      <UplotChart data={data} options={options} height={210} />
      <details className="native-data-table"><summary>benchmark comparison table alternative</summary><table className="blotter compact"><thead><tr><th>UTC</th><th className="r">strategy</th><th className="r">benchmark</th><th className="r">excess return</th></tr></thead><tbody>{native.benchmark.map((row) => <tr key={row.ts}><td className="mono">{new Date(row.ts * 1_000).toISOString()}</td><td className="num">{row.strategy_equity.toFixed(4)}</td><td className="num">{row.benchmark_equity?.toFixed(4) ?? '—'}</td><td className="num">{fmtPct(row.excess_return, 2)}</td></tr>)}</tbody></table></details>
    </div>
  )
}

function TradeStatistics({ native }: { native: NativeTearSheetProjection }) {
  function format(value: number | null, unit: string): string {
    if (value === null) return '—'
    if (unit === 'ratio') return fmtPct(value, 2)
    if (unit === 'seconds') return `${(value / 86_400).toFixed(1)}d`
    if (unit === 'count') return value.toFixed(0)
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  return (
    <table className="blotter compact" aria-label="Python-authored closed trade statistics">
      <thead><tr><th>metric</th><th className="r">value</th><th>unit</th><th>status</th></tr></thead>
      <tbody>{native.trade_statistics.map((row) => <tr key={row.metric}><td>{row.metric.replaceAll('_', ' ')}</td><td className="num">{format(row.value, row.unit)}</td><td className="mono muted">{row.unit}</td><td><span className={`chip ${row.available ? 'pass' : ''}`}>{row.available ? 'AVAILABLE' : row.unavailable_reason ?? 'UNAVAILABLE'}</span></td></tr>)}</tbody>
    </table>
  )
}

export function NativeTearSheetBody({
  detail,
  equity,
  trades,
}: {
  detail: RunDetail
  equity: EquitySeries | null
  trades: TradeRow[]
}) {
  const [native, setNative] = useState<NativeTearSheetProjection | null>(null)
  const [nativeError, setNativeError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setNative(null)
    setNativeError(null)
    api.nativeTearsheet(detail.run_id)
      .then((value) => live && setNative(value))
      .catch((reason: unknown) => live && setNativeError(String(reason)))
    return () => { live = false }
  }, [detail.run_id])

  const manifest = detail.manifest as Dict
  const metadata = metadataFor(manifest)
  const metrics = metricsFor(manifest)
  // spec §15 / ADR-0026: the permanent EXPLORATORY marker on override-launched runs
  const gateWatermark = researchGateWatermark(detail)
  const folds = Array.isArray(manifest.folds) ? (manifest.folds as FoldRow[]) : []
  const provenance = [
    ['symbol', metadata.symbol ?? manifest.symbol ?? manifest.symbols],
    ['strategy', metadata.strategy_name],
    ['snapshot', metadata.snapshot_id],
    ['window', metadata.first_ts && metadata.last_ts ? `${String(metadata.first_ts)} → ${String(metadata.last_ts)}` : null],
    ['seed', metadata.seed],
    ['schema', manifest.schema_version],
  ]
    .map(([label, value]) => [label, displayValue(value)] as const)
    .filter((entry): entry is readonly [string, string] => entry[1] !== null)

  if (native?.available === false && !metrics && !equity && !detail.has_trades) {
    return (
      <div className="native-tear">
        {gateWatermark ? <div className="leak rg-watermark-banner">▲ {gateWatermark}</div> : null}
        <div className="tear-provenance">
          {provenance.map(([label, value]) => <div key={label}><span className="eyebrow">{label}</span><span className="mono">{value}</span></div>)}
        </div>
        <Placeholder big="NATIVE ANALYTICS UNAVAILABLE">This legacy run predates the v3 analytics contract. Rerun the immutable specification to generate the dark tear-sheet artifacts; ALPHA will not reconstruct them in the browser.</Placeholder>
      </div>
    )
  }

  return (
    <div className="native-tear">
      {gateWatermark ? <div className="leak rg-watermark-banner">▲ {gateWatermark}</div> : null}
      <div className="tear-provenance">
        {provenance.map(([label, value]) => (
          <div key={label}>
            <span className="eyebrow">{label}</span>
            <span className="mono">{value}</span>
          </div>
        ))}
      </div>

      {metrics ? (
        <Section title="Authoritative run metrics" right={<span className="muted">manifest values · no browser calculation</span>}>
          <MetricGrid metrics={metrics} />
        </Section>
      ) : (
        <ArtifactGap title="Authoritative run metrics" contract="tearsheet_metrics.json" />
      )}

      {equity && equity.ts.length ? (
        <Section title="Equity & drawdown" right={<span className="muted">equity_curve.parquet · UTC</span>}>
          <EquityChart eq={equity} folds={folds} trades={trades} height={230} />
        </Section>
      ) : (
        <ArtifactGap title="Equity & drawdown" contract="equity_curve.parquet" />
      )}

      {native?.available ? (
        <>
          <Section title="Monthly & yearly returns" right={<span className="muted">calendar_returns.parquet · return units</span>}>
            <CalendarReturns native={native} />
          </Section>
          <Section title="Distribution & Q-Q" right={<span className="muted">return_distribution.parquet · Python-authored</span>}>
            <DistributionCharts native={native} />
          </Section>
          <Section title="Rolling statistics" right={<span className="muted">rolling_metrics.parquet · UTC · window {native.rolling[0]?.window ?? '—'}</span>}>
            <RollingChart native={native} />
          </Section>
          {native.benchmark_available ? (
            <Section title="Benchmark comparison" right={<span className="muted">benchmark_comparison.parquet · {native.benchmark[0]?.benchmark_kind ?? 'declared benchmark'}</span>}>
              <BenchmarkChart native={native} />
            </Section>
          ) : <ExplicitUnavailable title="Benchmark comparison" reason={native.benchmark[0]?.unavailable_reason} />}
          {native.exposure_available || native.turnover_available ? (
            <Section title="Exposure & turnover" right={<span className="muted">exposure_turnover.parquet · canonical post-fill state</span>}>
              <ExposureTurnoverChart native={native} />
            </Section>
          ) : <ExplicitUnavailable title="Exposure & turnover" reason={native.exposure_turnover[0]?.exposure_unavailable_reason ?? native.exposure_turnover[0]?.turnover_unavailable_reason} />}
          {native.trade_statistics_available ? (
            <Section title="Closed trade statistics" right={<span className="muted">trade_statistics.parquet · canonical closed trades</span>}>
              <TradeStatistics native={native} />
            </Section>
          ) : <ExplicitUnavailable title="Closed trade statistics" reason={native.trade_statistics.find((row) => row.unavailable_reason)?.unavailable_reason} />}
          <div className="native-source-line mono">
            SOURCE {Object.keys(native.provenance.artifact_sha256).join(' · ')} · NAMESPACE {native.provenance.metric_namespace} · TZ UTC · CONTRACT V{native.provenance.artifact_contract_version ?? '—'}
            {native.bounds.qq.truncated ? ` · Q-Q ${native.bounds.qq.returned}/${native.bounds.qq.original}` : ''}
            {native.bounds.rolling.truncated ? ` · ROLLING ${native.bounds.rolling.returned}/${native.bounds.rolling.original}` : ''}
            {native.bounds.exposure_turnover.truncated ? ` · EXPOSURE ${native.bounds.exposure_turnover.returned}/${native.bounds.exposure_turnover.original}` : ''}
            {native.bounds.benchmark.truncated ? ` · BENCHMARK ${native.bounds.benchmark.returned}/${native.bounds.benchmark.original}` : ''}
          </div>
        </>
      ) : native === null && nativeError === null ? (
        <div className="skeleton" style={{ height: 180 }} aria-label="Loading native analytics" />
      ) : (
        <div className="workbench-notice">
          <strong>NATIVE ANALYTICS UNAVAILABLE</strong>
          <span>{nativeError ?? 'This run does not contain the v3 calendar, distribution, and rolling artifacts. Rerun its immutable specification to generate them.'}</span>
        </div>
      )}

      {detail.has_trades ? (
        <TradesTab trades={trades} runId={detail.run_id} />
      ) : native?.available ? (
        <ArtifactGap title="Trade analysis" contract="trades.parquet" />
      ) : null}

      {detail.has_tearsheet ? (
        <div className="tear-audit-row">
          <span className="muted">QuantStats-Lumi remains the audit/export report.</span>
          <a className="tear-audit" href={api.tearsheetUrl(detail.run_id)} target="_blank" rel="noreferrer">
            open audit report
          </a>
        </div>
      ) : null}
    </div>
  )
}

export function NativeTearSheet(props: IDockviewPanelProps) {
  const panelLink = usePanelLinked(props)
  const runId = panelLink.linked.runId
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [equity, setEquity] = useState<EquitySeries | null>(null)
  const [trades, setTrades] = useState<TradeRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const runScope = runScopeFromParams(props.params)

  useEffect(() => {
    if (!runId) {
      setDetail(null)
      setEquity(null)
      setTrades([])
      setError(null)
      return
    }
    let live = true
    setDetail(null)
    setEquity(null)
    setTrades([])
    setError(null)
    api
      .run(runId)
      .then(async (next) => {
        if (!matchesRunScope(next, runScope)) {
          if (live) setDetail(next)
          return
        }
        const [nextEquity, nextTrades] = await Promise.all([
          next.has_equity ? api.equity(runId) : Promise.resolve(null),
          next.has_trades ? api.trades(runId) : Promise.resolve([]),
        ])
        if (!live) return
        setDetail(next)
        setEquity(nextEquity)
        setTrades(nextTrades)
      })
      .catch((reason: unknown) => live && setError(String(reason)))
    return () => {
      live = false
    }
  }, [runId, runScope])

  const title = useMemo(() => (runId ? shortId(runId) : 'NO RUN'), [runId])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Quant Tear Sheet</span>
        <PanelLinkControl controller={panelLink} />
        <span className="id mono">{title}</span>
        {detail ? <span className="chip kind">{detail.kind}</span> : null}
        <span className="spacer" />
        <span className="muted mono">ARTIFACT ONLY</span>
      </div>
      <div className="panel-body panel-pad">
        {!runId ? (
          <Placeholder big="NO RUN">Select a stored run to inspect its canonical metrics and artifacts.</Placeholder>
        ) : error ? (
          <Placeholder big="ERROR">{error}</Placeholder>
        ) : detail && !matchesRunScope(detail, runScope) ? (
          <Placeholder big="INCOMPATIBLE RUN">Select a {runScopeLabel(runScope)} run for this workspace. Canonical evidence from other run types is not relabeled.</Placeholder>
        ) : detail ? (
          <NativeTearSheetBody detail={detail} equity={equity} trades={trades} />
        ) : (
          <div className="skeleton" style={{ height: 260 }} />
        )}
      </div>
    </div>
  )
}
