import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type {
  Candle,
  ForecastOrigins,
  ForecastPaths,
  ForecastSeries,
  ProjectDetail,
  RunDetail,
} from '../api/types'
import { FigureCard } from '../components/FigureCard'
import { KronosKlineCanvas } from '../components/KronosKlineCanvas'
import { Placeholder } from '../components/Placeholder'
import { usePanelLinked } from '../context/usePanelLinked'
import { asStr, fmtNum, fmtPct, shortId } from '../util/format'
import { asObj, type Dict } from './rundetail/commonUtils'
import { terminalReturns } from './v3Models'
import type { FigureCatalogueItem } from '../api/types'
import type { PanelHandleProps } from '../context/panelHandle'

function object(value: unknown): Dict {
  return asObj(value) ?? {}
}

function commandOf(detail: RunDetail): string | null {
  return asStr((detail.manifest as Dict).command)
}

async function resolveKronosLineage(
  active: RunDetail,
  projectId: string | null,
): Promise<{ scenario: RunDetail | null; evaluation: RunDetail | null }> {
  const collected = new Map<string, RunDetail>([[active.run_id, active]])
  if (projectId) {
    const project: ProjectDetail = await api.project(projectId, 200)
    const activeLink = project.stage_run_links.find(
      (link) => link.stage === 'kronos' && link.run_id === active.run_id,
    )
    if (activeLink) {
      const candidateIds = project.stage_run_links
        .filter(
          (link) =>
            link.stage === 'kronos' &&
            link.experiment_id === activeLink.experiment_id &&
            (link.state === 'pass' || link.state === 'warning'),
        )
        .sort((left, right) => right.linked_at.localeCompare(left.linked_at))
        .map((link) => link.run_id)
        .filter((runId, index, values) => values.indexOf(runId) === index)
        .slice(0, 12)
      const details = await Promise.all(
        candidateIds.filter((runId) => runId !== active.run_id).map((runId) => api.run(runId)),
      )
      for (const detail of details) collected.set(detail.run_id, detail)
    }
  }
  const values = [...collected.values()]
  return {
    scenario: values.find((candidate) => commandOf(candidate) === 'forecast_run') ?? null,
    evaluation: values.find((candidate) => commandOf(candidate) === 'forecast_eval') ?? null,
  }
}

function terminalBars(values: Array<{ sample: number; value: number }>) {
  if (!values.length) return []
  const low = Math.min(...values.map((row) => row.value))
  const high = Math.max(...values.map((row) => row.value))
  const span = high - low || 1
  const bins = Array.from({ length: Math.min(12, Math.max(4, values.length)) }, (_, index) => ({
    left: low + (span * index) / Math.min(12, Math.max(4, values.length)),
    count: 0,
  }))
  for (const row of values) {
    const index = Math.min(bins.length - 1, Math.floor(((row.value - low) / span) * bins.length))
    bins[index].count += 1
  }
  return bins
}

function TerminalDistribution({ paths, originClose }: { paths: ForecastPaths; originClose: number }) {
  const values = useMemo(() => terminalReturns(paths, originClose), [originClose, paths])
  const bars = useMemo(() => terminalBars(values), [values])
  const maxCount = Math.max(1, ...bars.map((bar) => bar.count))
  return (
    <div className="terminal-dist">
      <div className="terminal-bars" aria-label="Terminal return distribution for visible model samples">
        {bars.map((bar) => (
          <div className="terminal-bin" key={bar.left}>
            <div className="terminal-column" style={{ height: `${(bar.count / maxCount) * 100}%` }} />
            <span className="mono">{fmtPct(bar.left, 0)}</span>
          </div>
        ))}
      </div>
      <details>
        <summary>table alternative · {values.length} visible samples</summary>
        <table className="blotter compact">
          <thead><tr><th>sample</th><th className="r">terminal return</th></tr></thead>
          <tbody>
            {values.map((row) => <tr key={row.sample}><td className="mono">{row.sample}</td><td className={`num ${row.value < 0 ? 'neg' : 'pos'}`}>{fmtPct(row.value, 2)}</td></tr>)}
          </tbody>
        </table>
      </details>
    </div>
  )
}

function Inspector({ manifest, visibleSamples }: { manifest: Dict; visibleSamples: number }) {
  const summary = object(manifest.summary)
  const params = object(manifest.params)
  const origin = object(manifest.origin)
  const model = object(manifest.model)
  const pretrain = object(manifest.pretrain)
  const p05 = typeof summary.p05_end_return === 'number' ? summary.p05_end_return : null
  const p95 = typeof summary.p95_end_return === 'number' ? summary.p95_end_return : null
  const rows: Array<[string, string]> = [
    ['P(end > origin)', fmtPct(summary.prob_up)],
    ['terminal median', fmtPct(summary.median_end_return)],
    ['terminal q05', fmtPct(summary.p05_end_return)],
    ['terminal q95', fmtPct(summary.p95_end_return)],
    ['terminal 90% width', p05 === null || p95 === null ? '—' : fmtPct(p95 - p05)],
    ['context / horizon', `${params.context ?? '—'} / ${params.horizon ?? '—'}`],
    ['samples visible / run', `${visibleSamples} / ${params.samples ?? '—'}`],
    ['sampling', `T ${params.temperature ?? '—'} · p ${params.top_p ?? '—'} · k ${params.top_k ?? '—'}`],
    ['seed', String(params.sampling_seed ?? params.seed ?? '—')],
    ['model', `${model.model_id ?? '—'}@${model.model_revision ?? '—'}`],
    ['tokenizer', `${model.tokenizer_id ?? '—'}@${model.tokenizer_revision ?? '—'}`],
    ['device / determinism', `${model.device ?? '—'} / ${model.determinism ?? '—'}`],
    ['origin UTC', String(origin.origin_ts ?? origin.last_ts ?? '—')],
    ['pretrain cutoff', `${pretrain.cutoff ?? '—'} · overlap ${pretrain.overlap === true ? 'YES' : 'NO'}`],
  ]
  return <div className="kronos-inspector">{rows.map(([label, value]) => <div key={label}><span className="eyebrow">{label}</span><span className="mono">{value}</span></div>)}</div>
}

function EvaluationMode({ detail }: { detail: RunDetail }) {
  const [origins, setOrigins] = useState<ForecastOrigins | null>(null)
  useEffect(() => {
    let live = true
    api.origins(detail.run_id).then((value) => live && setOrigins(value)).catch(() => live && setOrigins(null))
    return () => { live = false }
  }, [detail.run_id])
  const manifest = detail.manifest as Dict
  const post = object(manifest.summary_post_cutoff)
  return (
    <div className="kronos-eval-mode">
      <div className="kronos-scorecard">
        <div><span className="eyebrow">post-cutoff origins</span><span className="metric-val mono">{fmtNum(manifest.n_origins_post, 0)}</span></div>
        <div><span className="eyebrow">CRPS</span><span className="metric-val mono">{fmtNum(post.crps_mean, 4)}</span></div>
        <div><span className="eyebrow">skill vs RW</span><span className="metric-val mono">{fmtPct(post.skill_vs_rw)}</span></div>
        <div><span className="eyebrow">skill vs bootstrap</span><span className="metric-val mono">{fmtPct(post.skill_vs_bootstrap)}</span></div>
        <div><span className="eyebrow">coverage 50 / 80 / 90</span><span className="metric-val mono">{fmtPct(post.coverage50)} / {fmtPct(post.coverage80)} / {fmtPct(post.coverage90)}</span></div>
        <div><span className="eyebrow">direction hit rate</span><span className="metric-val mono">{fmtPct(post.hit_rate)}</span></div>
      </div>
      {origins ? (
        <FigureCard runId={detail.run_id} item={figureItem('forecast_skill', 'Forecast skill')} />
      ) : (
        <Placeholder>rolling-evaluation artifact unavailable</Placeholder>
      )}
      <div className="kronos-warning"><strong>REPLAY VALIDATION</strong><span>Rolling skill is evidence, not authorization. Signal promotion still requires a linked project decision packet and canonical replay.</span></div>
    </div>
  )
}

/** The two Kronos surfaces that are run artifacts are drawn by the figure renderer. */
function figureItem(figureId: string, title: string): FigureCatalogueItem {
  return {
    figure_id: figureId,
    title,
    summary: title,
    section: 'forecast',
    panel_count: 2,
    available: true,
    unavailable_reason: null,
  }
}

export function KronosStudio(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const linked = panelLink.linked
  const runId = linked.runId
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [scenarioDetail, setScenarioDetail] = useState<RunDetail | null>(null)
  const [evaluationDetail, setEvaluationDetail] = useState<RunDetail | null>(null)
  const [forecast, setForecast] = useState<ForecastSeries | null>(null)
  const [paths, setPaths] = useState<ForecastPaths | null>(null)
  const [history, setHistory] = useState<Candle[]>([])
  const [sampleId, setSampleId] = useState(0)
  const [pathLimit, setPathLimit] = useState(20)
  const [error, setError] = useState<string | null>(null)
  const [signalPrepared, setSignalPrepared] = useState(false)

  useEffect(() => {
    if (!runId) {
      setDetail(null); setScenarioDetail(null); setEvaluationDetail(null); setForecast(null); setPaths(null); setHistory([]); setError(null); setSignalPrepared(false)
      return
    }
    let live = true
    setDetail(null); setScenarioDetail(null); setEvaluationDetail(null); setForecast(null); setPaths(null); setHistory([]); setError(null); setSignalPrepared(false)
    api.run(runId).then(async (next) => {
      if (!live) return
      setDetail(next)
      const lineage = await resolveKronosLineage(next, linked.projectId)
      if (!live) return
      setScenarioDetail(lineage.scenario)
      setEvaluationDetail(lineage.evaluation)
      if (!lineage.scenario) return
      const [nextForecast, nextPaths] = await Promise.all([
        api.forecast(lineage.scenario.run_id),
        api.forecastPaths(lineage.scenario.run_id, pathLimit),
      ])
      if (!live) return
      setForecast(nextForecast)
      setPaths(nextPaths)
      setHistory(nextForecast.history_bars)
      setSampleId(nextPaths.samples[0]?.sample ?? 0)
    }).catch((reason: unknown) => live && setError(String(reason)))
    return () => { live = false }
  }, [linked.projectId, pathLimit, runId])

  const manifest = (scenarioDetail?.manifest ?? detail?.manifest ?? {}) as Dict
  const command = detail ? commandOf(detail) : null
  const sample = paths?.samples.find((candidate) => candidate.sample === sampleId) ?? paths?.samples[0]
  const originClose = forecast?.history.at(-1) ?? null
  const originTs = forecast?.history_ts.at(-1) ?? null
  const calibrated = evaluationDetail !== null

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Kronos Forecast Studio</span>
        <span className="chip kind">{command ?? 'NO RUN'}</span>
        {runId ? <span className="id mono">{shortId(runId)}</span> : null}
        <span className="spacer" />
        {paths ? <label className="kronos-sample-control"><span className="eyebrow">visible paths</span><select value={pathLimit} onChange={(event) => setPathLimit(Number(event.target.value))}><option value={20}>20</option><option value={40}>40 MAX</option></select></label> : null}
      </div>
      <div className="panel-body panel-pad kronos-studio">
        {!runId ? <Placeholder big="NO FORECAST RUN">Select a stored Kronos forecast or rolling-evaluation run.</Placeholder> : error ? <Placeholder big="ERROR">{error}</Placeholder> : !detail ? <div className="skeleton" style={{ height: 380 }} /> : command !== 'forecast_run' && command !== 'forecast_eval' ? <Placeholder big="NOT A KRONOS RUN">This workspace renders forecast_run and forecast_eval artifacts only.</Placeholder> : !scenarioDetail && evaluationDetail ? <EvaluationMode detail={evaluationDetail} /> : forecast && paths && sample && originClose !== null && originTs !== null ? (
          <>
            <div className="kronos-main-grid">
              <div className="kronos-chart-column">
                <div className="kronos-chart-head"><span>HISTORICAL ACTUAL + MODEL SAMPLE K-LINE</span><label><span className="eyebrow">complete path</span><select value={sample.sample} onChange={(event) => setSampleId(Number(event.target.value))}>{paths.samples.map((path) => <option key={path.sample} value={path.sample}>MODEL SAMPLE {path.sample}</option>)}</select></label></div>
                {forecast.history_ohlcv_available ? <KronosKlineCanvas history={history} sample={sample} forecastTs={paths.ts} originTs={originTs} /> : <Placeholder big="OHLCV TRACE UNAVAILABLE">This legacy forecast stored close-only history. Rerun it to freeze the complete observed candles; ALPHA will not reconstruct them from the current store.</Placeholder>}
                <div className="chart-foot mono"><span>PRICE · native quote units</span><span>TIME · UTC</span><span>AS OF {new Date(originTs * 1_000).toISOString()}</span></div>
              </div>
              <Inspector manifest={manifest} visibleSamples={paths.samples.length} />
            </div>
            <div className="kronos-analysis-grid">
              <section><FigureCard runId={runId} item={figureItem('forecast_fan', 'Outcome cone')} /></section>
              <section><div className="rd-head">Terminal return distribution · visible complete samples</div><TerminalDistribution paths={paths} originClose={originClose} /></section>
            </div>
            <details className="kronos-path-table">
              <summary>Forecast cone · quantile table alternative</summary>
              <div className="paper-blotter-scroll">
                <table className="blotter compact">
                  <thead><tr><th>UTC</th><th className="r">q05</th><th className="r">q25</th><th className="r">median</th><th className="r">q75</th><th className="r">q95</th><th className="r">mean</th></tr></thead>
                  <tbody>{forecast.forecast_ts.map((ts, index) => <tr key={ts}><td className="mono">{new Date(ts * 1_000).toISOString()}</td><td className="num">{forecast.p10[index].toFixed(4)}</td><td className="num">{forecast.q25[index].toFixed(4)}</td><td className="num">{forecast.forecast[index].toFixed(4)}</td><td className="num">{forecast.q75[index].toFixed(4)}</td><td className="num">{forecast.p90[index].toFixed(4)}</td><td className="num">{forecast.mean[index].toFixed(4)}</td></tr>)}</tbody>
                </table>
              </div>
            </details>
            <details className="kronos-path-table">
              <summary>Historical actual + MODEL SAMPLE {sample.sample} · OHLCV table alternative</summary>
              <div className="paper-blotter-scroll">
                <table className="blotter compact">
                  <thead><tr><th>segment</th><th>UTC</th><th className="r">open</th><th className="r">high</th><th className="r">low</th><th className="r">close</th><th className="r">volume</th></tr></thead>
                  <tbody>
                    {history.map((bar) => <tr key={`actual-${bar.t}`}><td>ACTUAL</td><td className="mono">{new Date(bar.t * 1_000).toISOString()}</td><td className="num">{bar.o.toFixed(4)}</td><td className="num">{bar.h.toFixed(4)}</td><td className="num">{bar.l.toFixed(4)}</td><td className="num">{bar.c.toFixed(4)}</td><td className="num">{bar.v.toFixed(2)}</td></tr>)}
                    {paths.ts.map((ts, index) => <tr key={`sample-${ts}`}><td>MODEL SAMPLE {sample.sample}</td><td className="mono">{new Date(ts * 1_000).toISOString()}</td><td className="num">{sample.opens[index].toFixed(4)}</td><td className="num">{sample.highs[index].toFixed(4)}</td><td className="num">{sample.lows[index].toFixed(4)}</td><td className="num">{sample.closes[index].toFixed(4)}</td><td className="num">{sample.volumes[index].toFixed(2)}</td></tr>)}
                  </tbody>
                </table>
              </div>
            </details>
            <div className="kronos-warning"><strong>PRETRAINING OVERLAP POLICY</strong><span>Cutoff {String(object(manifest.pretrain).cutoff ?? '—')} · overlap {object(manifest.pretrain).overlap === true ? 'YES — results may be memorized' : 'NO in this context window'}. Zero-shot output is not live-trading proof.</span></div>
            {evaluationDetail ? (
              <section className="kronos-linked-evaluation">
                <div className="rd-head">Linked rolling evaluation · {shortId(evaluationDetail.run_id)}</div>
                <EvaluationMode detail={evaluationDetail} />
              </section>
            ) : null}
            <div className="kronos-warning"><strong>{calibrated ? 'ROLLING EVALUATION LINKED' : 'ROLLING EVALUATION NOT LINKED'}</strong><span>{calibrated ? 'The cone and calibration are cited to the same project experiment. Preparing it as a signal candidate does not bypass canonical replay, holdout, or the sandbox-only decision packet.' : 'This scenario run has no cited forecast_eval lineage. Replay validation and “Use as signal” remain unavailable.'}</span><button className="btn" disabled={!calibrated || !linked.projectId || signalPrepared} title={calibrated ? 'Prepare a governed signal candidate; this places no order' : 'Requires linked rolling evaluation and project governance'} onClick={() => setSignalPrepared(true)}>{signalPrepared ? 'Candidate prepared · sandbox' : 'Use as signal'}</button></div>
          </>
        ) : <Placeholder>loading forecast artifacts…</Placeholder>}
      </div>
    </div>
  )
}
