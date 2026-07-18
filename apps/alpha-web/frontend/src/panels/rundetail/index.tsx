// Run Detail v2 — the run story. One fetch of the manifest + parquet projections, then a
// tabbed, kind-aware layout: validate runs get the full gauntlet story (Overview | Gates |
// Walk-forward | Risk | Trades | Artifacts); optim / portfolio / propfirm / forecast runs get
// their own layouts. Explanations render in the active voice (narrative/terse toggle).

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type {
  EquitySeries,
  ForecastSeries,
  RunDetail as RunDetailData,
  TradeRow,
} from '../../api/types'
import type {
  ForecastManifest,
  OptimManifest,
  PortfolioManifest,
  PropfirmManifest,
  ValidateManifest,
} from '../../explain/types'
import { setSettings, useSettings } from '../../state/settings'
import { Placeholder } from '../../components/Placeholder'
import { openStrategyLab } from '../actions'
import { asStr } from './commonUtils'
import { Artifacts } from './Artifacts'
import { ForecastDetail } from './ForecastDetail'
import { ForecastEvalDetail } from './ForecastEvalDetail'
import { Gates } from './Gates'
import { OptimDetail } from './OptimDetail'
import { Overview } from './Overview'
import { PortfolioDetail } from './PortfolioDetail'
import { PropfirmDetail } from './PropfirmDetail'
import { Risk } from './Risk'
import { TradesTab } from './TradesTab'
import { WalkForward } from './WalkForward'

type TabId = 'overview' | 'gates' | 'walkforward' | 'risk' | 'trades' | 'artifacts'

const VALIDATE_TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'gates', label: 'Gates' },
  { id: 'walkforward', label: 'Walk-forward' },
  { id: 'risk', label: 'Risk' },
  { id: 'trades', label: 'Trades' },
  { id: 'artifacts', label: 'Artifacts' },
]

export function RunDetail(props: IDockviewPanelProps) {
  const runId = String((props.params as { runId?: string }).runId ?? '')
  const [detail, setDetail] = useState<RunDetailData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [eq, setEq] = useState<EquitySeries | null>(null)
  const [trades, setTrades] = useState<TradeRow[]>([])
  const [fc, setFc] = useState<ForecastSeries | null>(null)
  const [tab, setTab] = useState<TabId>('overview')
  const { explain } = useSettings()

  useEffect(() => {
    if (!runId) return
    let live = true
    setDetail(null)
    setError(null)
    setEq(null)
    setTrades([])
    setFc(null)
    api
      .run(runId)
      .then((d) => {
        if (!live) return
        setDetail(d)
        if (d.has_equity) api.equity(runId).then((e) => live && setEq(e)).catch(() => {})
        if (d.has_trades) api.trades(runId).then((t) => live && setTrades(t)).catch(() => {})
        if (d.has_forecast) api.forecast(runId).then((f) => live && setFc(f)).catch(() => {})
      })
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [runId])

  const onLaunch = useMemo(
    () => (command: string, args: string) => openStrategyLab(props.containerApi!, { command, args }),
    [props.containerApi],
  )

  if (!runId) return <Placeholder>no run selected</Placeholder>
  if (error) return <Placeholder big="error">{error}</Placeholder>
  if (!detail)
    return (
      <div className="panel-pad">
        <div className="skeleton" style={{ height: 60, marginBottom: 8 }} />
        <div className="skeleton" style={{ height: 200 }} />
      </div>
    )

  const m = detail.manifest
  const command = asStr(m.command)
  const isValidate = detail.kind === 'runs' && m.verdict !== undefined
  const kindLabel = command ?? (detail.kind === 'runs' ? (isValidate ? 'validate' : 'backtest') : detail.kind)
  const leak = asStr(m.leakage_warning)

  const body = (() => {
    switch (detail.kind) {
      case 'optim':
        return (
          <OptimDetail
            manifest={m as OptimManifest}
            runId={runId}
            hasTrials={detail.has_trials ?? false}
            onLaunch={onLaunch}
          />
        )
      case 'portfolio':
      case 'cross_sectional':
        return <PortfolioDetail manifest={m as PortfolioManifest} eq={eq} onLaunch={onLaunch} />
      case 'propfirm':
        return (
          <PropfirmDetail
            manifest={m as PropfirmManifest}
            runId={runId}
            hasPaths={detail.has_propfirm_paths ?? false}
            onLaunch={onLaunch}
          />
        )
      case 'forecast':
        return command === 'forecast_eval' ? (
          <ForecastEvalDetail
            manifest={m as ForecastManifest}
            runId={runId}
            hasOrigins={detail.has_origins ?? false}
            onLaunch={onLaunch}
          />
        ) : (
          <ForecastDetail
            manifest={m as ForecastManifest}
            fc={fc}
            runId={runId}
            hasPaths={detail.has_forecast_paths ?? false}
            onLaunch={onLaunch}
          />
        )
      default: {
        const vm = m as ValidateManifest
        switch (tab) {
          case 'gates':
            return <Gates manifest={vm} runId={runId} hasNulls={detail.has_nulls ?? false} />
          case 'walkforward':
            return <WalkForward manifest={vm} />
          case 'risk':
            return <Risk manifest={vm} runId={runId} />
          case 'trades':
            return <TradesTab trades={trades} />
          case 'artifacts':
            return (
              <Artifacts manifest={vm} kind={detail.kind} runId={runId} hasTearsheet={detail.has_tearsheet} />
            )
          default:
            return <Overview manifest={vm} eq={eq} trades={trades} onLaunch={onLaunch} />
        }
      }
    }
  })()

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Run</span>
        <span className="id mono">{runId}</span>
        <span className="chip kind">{kindLabel}</span>
        {detail.kind === 'runs' && isValidate ? (
          <nav className="rd-tabs">
            {VALIDATE_TABS.map((t) => (
              <button
                key={t.id}
                className={`rd-tab${tab === t.id ? ' active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>
        ) : null}
        <span className="spacer" />
        <button
          className="btn ghost"
          title="Toggle narrative vs terse explanations"
          onClick={() => setSettings({ explain: explain === 'narrative' ? 'terse' : 'narrative' })}
        >
          {explain === 'narrative' ? '¶ narrative' : '# terse'}
        </button>
      </div>
      <div className="panel-body panel-pad rd">
        {leak ? <div className="leak">⚠ {leak}</div> : null}
        {body}
      </div>
    </div>
  )
}
