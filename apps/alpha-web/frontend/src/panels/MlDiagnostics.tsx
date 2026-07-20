import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'
import type uPlot from 'uplot'

import { api } from '../api/client'
import type { MlExperimentPage } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { UplotChart } from '../components/UplotChart'
import { setLinked, useLinked } from '../context/linked'
import { AXIS, CHART, withAlpha } from '../util/chartTheme'
import { fmtNum, fmtPct, shortId } from '../util/format'
import {
  buildFoldTimeline,
  buildScorePlot,
  buildTrainingHistory,
  isoToEpochSeconds,
  type MlExperimentSummaryProjection,
  type MlFoldDiagnosticProjection,
  type MlTearSheetProjection,
} from './mlTearsheetModel'
import { Section } from './rundetail/common'

const TRAINING_COLORS = [CHART.accent, CHART.gold, CHART.ink, CHART.muted]

function tableTimestamp(value: string): string {
  return new Date(value).toISOString()
}

function signedClass(value: number | null): string {
  if (value === null || value === 0) return ''
  return value < 0 ? 'neg' : 'pos'
}

function ScoreDistribution({ sheet }: { sheet: MlTearSheetProjection }) {
  const score = sheet.score_distribution
  const model = useMemo(() => (score ? buildScorePlot(score) : null), [score])
  if (!score || !model) return <ArtifactUnavailable label="SCORE DISTRIBUTION NOT EMITTED" />
  const x = (position: number): number => 50 + position * 6
  return (
    <div className="ml-score-block">
      <svg viewBox="0 0 700 112" role="img" aria-label="Model score quantile distribution">
        <line x1="50" x2="650" y1="57" y2="57" stroke={CHART.line} />
        <line x1={x(model.positions.q05)} x2={x(model.positions.q95)} y1="57" y2="57" stroke={CHART.dim} strokeWidth="2" />
        <line x1={x(model.positions.q05)} x2={x(model.positions.q05)} y1="48" y2="66" stroke={CHART.dim} />
        <line x1={x(model.positions.q95)} x2={x(model.positions.q95)} y1="48" y2="66" stroke={CHART.dim} />
        <rect
          x={x(model.positions.q25)}
          y="39"
          width={Math.max(1, x(model.positions.q75) - x(model.positions.q25))}
          height="36"
          fill={withAlpha(CHART.accent, 0.18)}
          stroke={CHART.accent}
        />
        <line x1={x(model.positions.q50)} x2={x(model.positions.q50)} y1="37" y2="77" stroke={CHART.ink} strokeWidth="2" />
        <circle cx={x(model.positions.mean)} cy="29" r="4" fill={CHART.gold} />
        <text x="50" y="99" className="svg-num">{fmtNum(model.min, 4)}</text>
        <text x="650" y="99" textAnchor="end" className="svg-num">{fmtNum(model.max, 4)}</text>
        <text x="350" y="108" textAnchor="middle" className="svg-axis-label">MODEL SCORE</text>
        <text x={x(model.positions.mean)} y="18" textAnchor="middle" className="svg-num">MEAN {fmtNum(score.mean, 4)}</text>
      </svg>
      <div className="ml-score-stats mono" role="table" aria-label="Model score distribution values">
        {(['min', 'q05', 'q25', 'q50', 'q75', 'q95', 'max', 'mean', 'std'] as const).map((key) => (
          <div role="row" key={key}><span role="cell">{key.toUpperCase()}</span><b role="cell">{fmtNum(score[key], 5)}</b></div>
        ))}
      </div>
    </div>
  )
}

function IcTimeline({ sheet }: { sheet: MlTearSheetProjection }) {
  const rows = sheet.ic?.by_target
  const data = useMemo<uPlot.AlignedData>(() => {
    const values = rows ?? []
    return [
      isoToEpochSeconds(values.map((row) => row.target_ts)),
      values.map((row) => row.ic),
      values.map((row) => row.rank_ic),
    ] as uPlot.AlignedData
  }, [rows])
  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(() => ({
    scales: { x: { time: true }, coefficient: {} },
    axes: [
      { ...AXIS, label: 'TARGET SESSION · UTC' },
      { ...AXIS, scale: 'coefficient', label: 'IC / RANKIC' },
    ],
    series: [
      {},
      { label: 'IC', scale: 'coefficient', stroke: CHART.accent, width: 1.4, points: { show: false } },
      { label: 'RankIC', scale: 'coefficient', stroke: CHART.gold, width: 1.2, points: { show: false } },
    ],
    legend: { show: true },
    cursor: { points: { show: false } },
  }), [])
  if (!sheet.ic || !rows || rows.length === 0) return <ArtifactUnavailable label="IC TIMELINE NOT EMITTED" />
  return (
    <div>
      <div className="ml-inline-stats mono">
        <span>MEAN IC <b>{fmtNum(sheet.ic.mean, 4)}</b></span>
        <span>MEAN RANKIC <b>{fmtNum(sheet.ic.rank_mean, 4)}</b></span>
        <span>TARGETS <b>{sheet.timeline_total}</b></span>
      </div>
      <UplotChart data={data} options={options} height={210} />
      <details className="native-data-table">
        <summary>IC / RankIC table alternative</summary>
        <table className="blotter compact"><thead><tr><th>target UTC</th><th className="r">IC</th><th className="r">RankIC</th><th className="r">n</th></tr></thead><tbody>
          {rows.map((row) => <tr key={row.target_ts}><td className="mono">{tableTimestamp(row.target_ts)}</td><td className="num">{fmtNum(row.ic, 5)}</td><td className="num">{fmtNum(row.rank_ic, 5)}</td><td className="num">{row.sample_count}</td></tr>)}
        </tbody></table>
      </details>
    </div>
  )
}

function QuantileReturns({ sheet }: { sheet: MlTearSheetProjection }) {
  const rows = sheet.quantile_returns
  if (rows.length === 0) return <ArtifactUnavailable label="QUANTILE RETURNS NOT EMITTED" />
  const values = rows.map((row) => row.mean_return)
  const maxAbs = Math.max(0.000001, ...values.map((value) => Math.abs(value ?? 0)))
  const baseline = 75
  return (
    <div>
      <svg className="ml-quantile-chart" viewBox="0 0 700 130" role="img" aria-label="Mean OOS return by model score quantile">
        <line x1="48" x2="678" y1={baseline} y2={baseline} stroke={CHART.line} />
        {rows.map((row, index) => {
          const value = row.mean_return
          const height = value === null ? 0 : (Math.abs(value) / maxAbs) * 50
          const width = 82
          const x = 72 + index * 122
          const y = value !== null && value >= 0 ? baseline - height : baseline
          return (
            <g key={row.quantile}>
              <rect x={x} y={y} width={width} height={height} fill={value !== null && value < 0 ? CHART.down : CHART.up} opacity="0.72" />
              <text x={x + width / 2} y="116" textAnchor="middle" className="svg-num">Q{row.quantile}</text>
              <text x={x + width / 2} y={value !== null && value >= 0 ? Math.max(12, y - 5) : Math.min(112, baseline + height + 12)} textAnchor="middle" className="svg-num">{fmtPct(value, 3)}</text>
            </g>
          )
        })}
        <text x="12" y="20" className="svg-axis-label">MEAN RETURN</text>
        <text x="362" y="129" textAnchor="middle" className="svg-axis-label">MODEL SCORE QUANTILE</text>
      </svg>
      <table className="blotter compact" aria-label="Quantile return table"><thead><tr><th>quantile</th><th className="r">mean OOS return</th><th className="r">observations</th></tr></thead><tbody>
        {rows.map((row) => <tr key={row.quantile}><td className="mono">Q{row.quantile}</td><td className={`num ${signedClass(row.mean_return)}`}>{fmtPct(row.mean_return, 4)}</td><td className="num">{row.observations}</td></tr>)}
      </tbody></table>
    </div>
  )
}

function PortfolioDiagnostics({ sheet }: { sheet: MlTearSheetProjection }) {
  const portfolio = sheet.portfolio
  const rows = portfolio?.timeline
  const timestamps = useMemo(
    () => isoToEpochSeconds((rows ?? []).map((row) => row.target_ts)),
    [rows],
  )
  const equityData = useMemo<uPlot.AlignedData>(() => {
    const values = rows ?? []
    return [
      timestamps,
      values.map((row) => row.gross_equity),
      values.map((row) => row.costed_equity),
      values.map((row) => row.benchmark_equity),
    ] as uPlot.AlignedData
  }, [rows, timestamps])
  const returnData = useMemo<uPlot.AlignedData>(() => {
    const values = rows ?? []
    return [
      timestamps,
      values.map((row) => row.gross_return),
      values.map((row) => row.costed_return),
      values.map((row) => row.benchmark_return),
      values.map((row) => row.excess_return),
      values.map((row) => row.turnover),
    ] as uPlot.AlignedData
  }, [rows, timestamps])
  const equityOptions = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(() => ({
    scales: { x: { time: true }, equity: {} },
    axes: [{ ...AXIS, label: 'TARGET SESSION · UTC' }, { ...AXIS, scale: 'equity', label: 'NORMALIZED EQUITY' }],
    series: [
      {},
      { label: 'Gross', scale: 'equity', stroke: CHART.accent, width: 1.4, points: { show: false } },
      { label: 'Costed', scale: 'equity', stroke: CHART.gold, width: 1.4, points: { show: false } },
      { label: 'Benchmark', scale: 'equity', stroke: CHART.ink, width: 1, points: { show: false } },
    ],
    legend: { show: true },
    cursor: { points: { show: false } },
  }), [])
  const returnOptions = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(() => ({
    scales: { x: { time: true }, returns: {}, turnover: {} },
    axes: [
      { ...AXIS, label: 'TARGET SESSION · UTC' },
      { ...AXIS, scale: 'returns', label: 'PERIOD RETURN', values: (_u, values) => values.map((value) => fmtPct(value, 1)) },
      { ...AXIS, scale: 'turnover', side: 1, label: 'TURNOVER', values: (_u, values) => values.map((value) => fmtPct(value, 0)) },
    ],
    series: [
      {},
      { label: 'Gross return', scale: 'returns', stroke: CHART.accent, width: 1, points: { show: false } },
      { label: 'Costed return', scale: 'returns', stroke: CHART.gold, width: 1.3, points: { show: false } },
      { label: 'Benchmark return', scale: 'returns', stroke: CHART.ink, width: 1, points: { show: false } },
      { label: 'Excess return', scale: 'returns', stroke: CHART.muted, width: 1, points: { show: false } },
      { label: 'Turnover', scale: 'turnover', stroke: CHART.dim, width: 1, dash: [4, 3], points: { show: false } },
    ],
    legend: { show: true },
    cursor: { points: { show: false } },
  }), [])
  if (!portfolio) return <ArtifactUnavailable label="DIAGNOSTIC PORTFOLIO NOT EMITTED" />
  return (
    <div>
      <div className="ml-portfolio-summary">
        <div><span>GROSS TOTAL</span><b className={signedClass(portfolio.gross_total_return)}>{fmtPct(portfolio.gross_total_return, 2)}</b></div>
        <div><span>COSTED TOTAL</span><b className={signedClass(portfolio.costed_total_return)}>{fmtPct(portfolio.costed_total_return, 2)}</b></div>
        <div><span>BENCHMARK</span><b className={signedClass(portfolio.benchmark_total_return)}>{fmtPct(portfolio.benchmark_total_return, 2)}</b></div>
        <div><span>COSTED EXCESS</span><b className={signedClass(portfolio.costed_excess_total_return)}>{fmtPct(portfolio.costed_excess_total_return, 2)}</b></div>
        <div><span>MEAN TURNOVER</span><b>{fmtPct(portfolio.mean_turnover, 2)}</b></div>
        <div><span>DECLARED COSTS</span><b>FEE {fmtNum(portfolio.declared_costs.fee_bps, 2)} · SLIP {fmtNum(portfolio.declared_costs.slippage_bps, 2)} bps</b></div>
      </div>
      {rows?.length ? <div className="ml-portfolio-charts"><div><div className="chart-subhead">Gross / costed / benchmark equity</div><UplotChart data={equityData} options={equityOptions} height={205} /></div><div><div className="chart-subhead">Returns / excess / turnover</div><UplotChart data={returnData} options={returnOptions} height={205} /></div></div> : <ArtifactUnavailable label="PORTFOLIO TIMELINE NOT EMITTED" />}
      {rows?.length ? <details className="native-data-table"><summary>portfolio timeline table alternative</summary><table className="blotter compact"><thead><tr><th>target UTC</th><th className="r">gross</th><th className="r">costed</th><th className="r">benchmark</th><th className="r">excess</th><th className="r">turnover</th></tr></thead><tbody>
        {rows.map((row) => <tr key={row.target_ts}><td className="mono">{tableTimestamp(row.target_ts)}</td><td className="num">{fmtPct(row.gross_return, 3)}</td><td className="num">{fmtPct(row.costed_return, 3)}</td><td className="num">{fmtPct(row.benchmark_return, 3)}</td><td className="num">{fmtPct(row.excess_return, 3)}</td><td className="num">{fmtPct(row.turnover, 2)}</td></tr>)}
      </tbody></table></details> : null}
    </div>
  )
}

function FeatureImportance({ sheet }: { sheet: MlTearSheetProjection }) {
  if (sheet.feature_importance.length === 0) return <ArtifactUnavailable label="FEATURE IMPORTANCE NOT EMITTED" />
  const maxGain = Math.max(0.000001, ...sheet.feature_importance.map((row) => row.mean_gain))
  return (
    <div>
      <table className="blotter compact ml-feature-table" aria-label="Qlib feature importance"><thead><tr><th>rank</th><th>feature</th><th>relative gain</th><th className="r">mean gain</th><th className="r">mean splits</th></tr></thead><tbody>
        {sheet.feature_importance.map((row, index) => <tr key={row.feature}><td className="mono">{index + 1}</td><td className="mono">{row.feature}</td><td><span className="ml-feature-track"><i style={{ width: `${Math.max(0, row.mean_gain / maxGain) * 100}%` }} /></span></td><td className="num">{fmtNum(row.mean_gain, 5)}</td><td className="num">{fmtNum(row.mean_split_count, 2)}</td></tr>)}
      </tbody></table>
      {sheet.feature_importance_truncated ? <div className="ml-bounded-note mono">BOUNDED PROJECTION · ADDITIONAL FEATURES OMITTED BY feature_limit</div> : null}
    </div>
  )
}

function FoldBoundaries({ folds }: { folds: MlFoldDiagnosticProjection[] }) {
  const model = useMemo(() => buildFoldTimeline(folds), [folds])
  if (!model) return <ArtifactUnavailable label="FOLD DIAGNOSTICS NOT EMITTED" />
  const span = Math.max(1, model.end - model.start)
  const x = (timestamp: number): number => 80 + ((timestamp - model.start) / span) * 790
  const height = 38 + model.segments.length * 28
  return (
    <div>
      <svg className="ml-fold-timeline" viewBox={`0 0 900 ${height}`} role="img" aria-label="Train validation and test boundaries by fold">
        {model.segments.map((segment, index) => {
          const y = 18 + index * 28
          return <g key={segment.fold}><text x="8" y={y + 10} className="svg-num">F{segment.fold}</text><rect x={x(segment.train[0])} y={y} width={Math.max(1, x(segment.train[1]) - x(segment.train[0]))} height="12" fill={withAlpha(CHART.muted, 0.48)} /><rect x={x(segment.validation[0])} y={y} width={Math.max(1, x(segment.validation[1]) - x(segment.validation[0]))} height="12" fill={withAlpha(CHART.gold, 0.7)} /><rect x={x(segment.test[0])} y={y} width={Math.max(1, x(segment.test[1]) - x(segment.test[0]))} height="12" fill={withAlpha(CHART.accent, 0.78)} /></g>
        })}
        <text x="80" y={height - 3} className="svg-num">{new Date(model.start * 1_000).toISOString().slice(0, 10)}</text>
        <text x="870" y={height - 3} textAnchor="end" className="svg-num">{new Date(model.end * 1_000).toISOString().slice(0, 10)}</text>
      </svg>
      <div className="ml-fold-legend mono"><span><i className="train" />TRAIN</span><span><i className="validation" />VALIDATION</span><span><i className="test" />TEST</span><span>UTC SESSION BOUNDARIES</span></div>
      <table className="blotter compact" aria-label="ML fold boundary and fit details"><thead><tr><th>fold</th><th>train</th><th>validation</th><th>test</th><th className="r">rows T/V/T</th><th className="r">best iter</th><th>model / normalization</th></tr></thead><tbody>
        {folds.map((fold) => <tr key={fold.fold}><td className="mono">F{fold.fold}</td><td className="mono">{fold.boundaries.train_start.slice(0, 10)} → {fold.boundaries.train_end.slice(0, 10)}</td><td className="mono">{fold.boundaries.validation_start.slice(0, 10)} → {fold.boundaries.validation_end.slice(0, 10)}</td><td className="mono">{fold.boundaries.test_start.slice(0, 10)} → {fold.boundaries.test_end.slice(0, 10)}</td><td className="num">{fold.train_rows.toLocaleString()} / {fold.validation_rows.toLocaleString()} / {fold.test_rows.toLocaleString()}</td><td className="num">{fold.best_iteration}</td><td className="mono ml-hash-cell" title={`${fold.model_hash} · ${fold.normalization.statistics_hash}`}>{shortId(fold.model_hash)} · {shortId(fold.normalization.statistics_hash)} · FIT {fold.fit_count}</td></tr>)}
      </tbody></table>
    </div>
  )
}

function TrainingHistoryChart({ fold }: { fold: MlFoldDiagnosticProjection }) {
  const model = useMemo(() => buildTrainingHistory(fold), [fold])
  const data = useMemo<uPlot.AlignedData>(() => [
    model.iterations,
    ...model.curves.map((curve) => curve.values),
  ] as uPlot.AlignedData, [model])
  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(() => ({
    scales: { x: {}, objective: {} },
    axes: [{ ...AXIS, label: 'BOOSTING ITERATION' }, { ...AXIS, scale: 'objective', label: 'OBJECTIVE VALUE' }],
    series: [
      {},
      ...model.curves.map((curve, index) => ({
        label: curve.label,
        scale: 'objective',
        stroke: TRAINING_COLORS[index % TRAINING_COLORS.length],
        width: 1.2,
        points: { show: false },
      })),
    ],
    legend: { show: true },
    cursor: { points: { show: false } },
  }), [model.curves])
  return (
    <div className="ml-training-fold">
      <div className="ml-training-head mono"><span>FOLD {fold.fold}</span><span>BEST ITER {fold.best_iteration}</span><span>{model.iterations.length} HISTORY POINTS</span></div>
      {model.curves.length ? <UplotChart data={data} options={options} height={175} /> : <ArtifactUnavailable label="TRAINING HISTORY EMPTY" />}
      <details className="native-data-table"><summary>fold {fold.fold} training-history table alternative</summary><table className="blotter compact"><thead><tr><th>series</th><th>artifact values by iteration</th></tr></thead><tbody>
        {model.curves.map((curve) => <tr key={curve.label}><td className="mono">{curve.label}</td><td className="mono ml-history-values">{curve.values.map((value) => value === null ? '—' : fmtNum(value, 6)).join(' · ')}</td></tr>)}
      </tbody></table></details>
    </div>
  )
}

function ArtifactUnavailable({ label }: { label: string }) {
  return <div className="ml-artifact-gap mono">{label} · NO BROWSER RECONSTRUCTION</div>
}

function Provenance({ sheet, summary }: { sheet: MlTearSheetProjection; summary: MlExperimentSummaryProjection | null }) {
  return (
    <div className="ml-provenance-grid">
      <div><span>EXCHANGE</span><code>{sheet.exchange_id}</code></div>
      <div><span>CONFIG HASH</span><code>{summary?.config_hash ?? 'NOT PROJECTED'}</code></div>
      <div><span>SNAPSHOT HASH</span><code>{summary?.snapshot_hash ?? 'NOT PROJECTED'}</code></div>
      <div><span>WORKER</span><code>{sheet.versions?.worker ?? '—'}</code></div>
      <div><span>PYQLIB</span><code>{sheet.versions?.pyqlib ?? '—'}</code></div>
      <div><span>LIGHTGBM</span><code>{sheet.versions?.lightgbm ?? '—'}</code></div>
      <div><span>AUTHORITY</span><code>{sheet.authority}</code></div>
      <div><span>FEATURE RECIPE</span><code>{sheet.feature_recipe?.name ?? summary?.feature_recipe ?? '—'} · {sheet.feature_recipe?.feature_count ?? '—'} features</code></div>
      <div><span>MODEL / STATUS</span><code>{summary?.model ?? 'LightGBM'} · {summary?.status ?? '—'}</code></div>
    </div>
  )
}

export function MlDiagnosticsBody({
  sheet,
  summary,
  onPrevious,
  onNext,
}: {
  sheet: MlTearSheetProjection
  summary: MlExperimentSummaryProjection | null
  onPrevious?: () => void
  onNext?: () => void
}) {
  if (!sheet.available) {
    return <div className="ml-diagnostics"><div className="ml-diagnostic-banner"><strong>QLIB DIAGNOSTIC ONLY</strong><span>{sheet.label}</span></div><ArtifactUnavailable label="VALIDATED WORKER DIAGNOSTICS UNAVAILABLE" /></div>
  }
  const returnedTimelineRows = Math.max(
    sheet.ic?.by_target.length ?? 0,
    sheet.portfolio?.timeline.length ?? 0,
  )
  const windowStart = sheet.timeline_total === 0 ? 0 : sheet.timeline_offset + 1
  const windowEnd = Math.min(sheet.timeline_total, sheet.timeline_offset + returnedTimelineRows)
  return (
    <div className="ml-diagnostics">
      <div className="ml-diagnostic-banner" role="note">
        <strong>QLIB DIAGNOSTIC ONLY · {sheet.counterfactual_refit ? 'COUNTERFACTUAL REFIT REPORTED' : 'MODEL NOT RECOMPUTED UNDER COUNTERFACTUAL'}</strong>
        <span>{sheet.label}</span>
        <span>Canonical ALPHA replay and the Native Tear Sheet remain performance authority.</span>
      </div>
      <Provenance sheet={sheet} summary={summary} />
      <Section title="Score distribution" right={<span className="muted">worker diagnostics · model-score units</span>}><ScoreDistribution sheet={sheet} /></Section>
      <div className="ml-diagnostic-two-up">
        <Section title="IC / RankIC timeline" right={<span className="muted">aligned OOS targets · UTC</span>}><IcTimeline sheet={sheet} /></Section>
        <Section title="Quantile returns" right={<span className="muted">worker signal analysis · association only</span>}><QuantileReturns sheet={sheet} /></Section>
      </div>
      <Section title="Gross, costed, benchmark, excess & turnover" right={<span className="muted">diagnostic portfolio · declared costs</span>}><PortfolioDiagnostics sheet={sheet} /></Section>
      <div className="ml-diagnostic-two-up lower">
        <Section title="Feature importance" right={<span className="muted">mean LightGBM gain / split count</span>}><FeatureImportance sheet={sheet} /></Section>
        <Section title="Fold boundaries" right={<span className="muted">one fit per fold · train-only normalization</span>}><FoldBoundaries folds={sheet.folds} /></Section>
      </div>
      <Section title="Training history" right={<span className="muted">bounded worker history · no interpolation</span>}><div className="ml-training-grid">{sheet.folds.map((fold) => <TrainingHistoryChart key={fold.fold} fold={fold} />)}</div></Section>
      <Section title="Recipe & availability contract" right={<span className="muted">close t decision · open t+1 entry</span>}>
        <div className="ml-recipe-grid">
          <div><span>LABEL</span><code>{sheet.label_recipe?.name ?? '—'}</code></div>
          <div><span>DEFINITION</span><code>{sheet.label_recipe?.definition ?? '—'}</code></div>
          <div><span>DECISION / ENTRY</span><code>{sheet.label_recipe?.decision ?? '—'} / {sheet.label_recipe?.entry ?? '—'}</code></div>
          <div><span>VWAP SOURCE</span><code>{sheet.feature_recipe?.vwap_source ?? '—'}</code></div>
        </div>
        {sheet.feature_recipe?.names.length ? <details className="native-data-table"><summary>Alpha158 feature names</summary><div className="ml-feature-names mono">{sheet.feature_recipe.names.join(' · ')}</div></details> : null}
      </Section>
      <div className="ml-page-controls mono">
        <button className="btn" disabled={sheet.timeline_offset === 0} onClick={onPrevious}>Previous timeline window</button>
        <span>{windowStart}–{windowEnd} / {sheet.timeline_total} TARGETS · LIMIT {sheet.timeline_limit}</span>
        <button className="btn" disabled={!sheet.timeline_has_more} onClick={onNext}>Next timeline window</button>
      </div>
    </div>
  )
}

export function MlDiagnostics(_props: IDockviewPanelProps) {
  const linked = useLinked()
  const [experiments, setExperiments] = useState<MlExperimentPage | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sheet, setSheet] = useState<MlTearSheetProjection | null>(null)
  const [timelineOffset, setTimelineOffset] = useState(0)
  const [refreshToken, setRefreshToken] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setSelectedId(null)
    setTimelineOffset(0)
  }, [linked.projectId])

  useEffect(() => {
    let live = true
    setExperiments(null)
    setError(null)
    api.mlExperiments(linked.projectId).then((next) => {
      if (!live) return
      setExperiments(next)
      setSelectedId((current) =>
        current && next.items.some((item) => item.experiment_id === current)
          ? current
          : (next.items[0]?.experiment_id ?? null),
      )
    }).catch((reason: unknown) => {
      if (live) setError(String(reason))
    })
    return () => { live = false }
  }, [linked.projectId, refreshToken])

  useEffect(() => {
    if (!selectedId) {
      setSheet(null)
      return
    }
    let live = true
    setSheet(null)
    setError(null)
    api.mlTearsheet(selectedId, timelineOffset).then((next) => {
      if (live) setSheet(next)
    }).catch((reason: unknown) => {
      if (live) setError(String(reason))
    })
    return () => { live = false }
  }, [refreshToken, selectedId, timelineOffset])

  const summary = useMemo(
    () => experiments?.items.find((item) => item.experiment_id === selectedId) ?? null,
    [experiments, selectedId],
  )
  const step = sheet?.timeline_limit ?? 500

  function selectExperiment(next: string) {
    setSelectedId(next || null)
    setTimelineOffset(0)
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">ML Signal Tear Sheet</span>
        <span className="chip kind">QLIB DIAGNOSTIC</span>
        <label className="ml-experiment-selector">
          <span>EXPERIMENT</span>
          <select
            className="field mono"
            aria-label="ML diagnostic experiment"
            value={selectedId ?? ''}
            onChange={(event) => selectExperiment(event.target.value)}
            disabled={!experiments?.items.length}
          >
            {!experiments?.items.length ? <option value="">NO VALIDATED EXPERIMENT</option> : null}
            {experiments?.items.map((experiment) => (
              <option key={experiment.experiment_id} value={experiment.experiment_id}>
                {shortId(experiment.experiment_id)} · {experiment.status} · {experiment.universe_size} symbols
              </option>
            ))}
          </select>
        </label>
        <span className="spacer" />
        {summary?.replay_run_id ? (
          <button className="btn" onClick={() => setLinked({ runId: summary.replay_run_id })}>
            Open canonical replay
          </button>
        ) : null}
        <button className="btn" onClick={() => setRefreshToken((value) => value + 1)}>Refresh</button>
      </div>
      <div className="panel-body panel-pad">
        {error ? (
          <Placeholder big="ML PROJECTION ERROR">{error}</Placeholder>
        ) : !experiments || (selectedId && !sheet) ? (
          <div className="skeleton" style={{ height: 320 }} />
        ) : !selectedId ? (
          <Placeholder big="NO VALIDATED ML EXPERIMENT">
            Generate and train an isolated Qlib experiment to inspect typed diagnostic artifacts.
          </Placeholder>
        ) : sheet ? (
          <MlDiagnosticsBody
            sheet={sheet}
            summary={summary}
            onPrevious={() => setTimelineOffset((value) => Math.max(0, value - step))}
            onNext={() => setTimelineOffset((value) => value + step)}
          />
        ) : null}
      </div>
    </div>
  )
}
