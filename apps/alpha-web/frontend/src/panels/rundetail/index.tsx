// Run Detail — the run story. One fetch of the manifest + parquet projections, then a
// kind-aware layout.
//
// Report is the default surface for EVERY run kind. It is the server-rendered figure pack,
// each figure carrying the question it answers and what this run's numbers say. The older
// kind-specific views remain behind tabs for the manifest detail figures do not cover
// (gate text, fold tables, artifact provenance) — but a plain backtest no longer falls
// through to one flat unstructured page, which is what made results feel opaque.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type {
  EquitySeries,
  ForecastSeries,
  PortfolioAnalyticsProjection,
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
import { PanelLinkControl } from '../../components/PanelLinkControl'
import { Placeholder } from '../../components/Placeholder'
import { FigureReport } from '../FigureReport'
import { usePanelLinked } from '../../context/usePanelLinked'
import { openStrategyLab } from '../actions'
import { NativeTearSheetBody } from '../NativeTearSheet'
import { matchesRunScope, runScopeFromParams, runScopeLabel } from '../v3Models'
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

type TabId =
  | 'report'
  | 'overview'
  | 'gates'
  | 'walkforward'
  | 'risk'
  | 'trades'
  | 'tearsheet'
  | 'artifacts'

const REPORT_TAB: { id: TabId; label: string } = { id: 'report', label: 'Report' }

const VALIDATE_TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'gates', label: 'Gates' },
  { id: 'walkforward', label: 'Walk-forward' },
  { id: 'risk', label: 'Risk' },
  { id: 'trades', label: 'Trades' },
  { id: 'tearsheet', label: 'Tear Sheet' },
  { id: 'artifacts', label: 'Artifacts' },
]

/** Every run kind gets Report; validate additionally keeps its manifest-detail tabs. */
function tabsFor(kind: string, isValidate: boolean): { id: TabId; label: string }[] {
  if (kind === 'runs' && isValidate) return [REPORT_TAB, ...VALIDATE_TABS]
  return [REPORT_TAB, { id: 'artifacts', label: 'Artifacts' }]
}

export function RunDetail(props: IDockviewPanelProps) {
  const panelLink = usePanelLinked(props)
  const runId = panelLink.linked.runId ?? ''
  const [detail, setDetail] = useState<RunDetailData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [eq, setEq] = useState<EquitySeries | null>(null)
  const [trades, setTrades] = useState<TradeRow[]>([])
  const [fc, setFc] = useState<ForecastSeries | null>(null)
  const [portfolioAnalytics, setPortfolioAnalytics] = useState<PortfolioAnalyticsProjection | null>(null)
  const [portfolioAnalyticsError, setPortfolioAnalyticsError] = useState<string | null>(null)
  const [portfolioAnalyticsLoading, setPortfolioAnalyticsLoading] = useState(false)
  const [tab, setTab] = useState<TabId>('report')
  const { explain } = useSettings()
  const runScope = runScopeFromParams(props.params)

  useEffect(() => {
    if (!runId) return
    let live = true
    setDetail(null)
    setError(null)
    setEq(null)
    setTrades([])
    setFc(null)
    setPortfolioAnalytics(null)
    setPortfolioAnalyticsError(null)
    setPortfolioAnalyticsLoading(false)
    api
      .run(runId)
      .then((d) => {
        if (!live) return
        setDetail(d)
        if (!matchesRunScope(d, runScope)) return
        if (d.has_equity) api.equity(runId).then((e) => live && setEq(e)).catch(() => {})
        if (d.has_trades) api.trades(runId).then((t) => live && setTrades(t)).catch(() => {})
        if (d.has_forecast) api.forecast(runId).then((f) => live && setFc(f)).catch(() => {})
        if (d.has_portfolio_analytics) {
          setPortfolioAnalyticsLoading(true)
          api
            .portfolioAnalytics(runId)
            .then((value) => {
              if (live) setPortfolioAnalytics(value)
            })
            .catch((reason: unknown) => {
              if (live) setPortfolioAnalyticsError(String(reason))
            })
            .finally(() => {
              if (live) setPortfolioAnalyticsLoading(false)
            })
        }
      })
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [runId, runScope])

  const onLaunch = useMemo(
    () => (command: string, args: string) => openStrategyLab(props.containerApi!, { command, args }),
    [props.containerApi],
  )

  if (!runId) {
    return (
      <div className="panel">
        <div className="panel-toolbar"><span className="title">Run</span><PanelLinkControl controller={panelLink} /></div>
        <div className="panel-body"><Placeholder>no run selected</Placeholder></div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="panel">
        <div className="panel-toolbar"><span className="title">Run</span><PanelLinkControl controller={panelLink} /><span className="id mono">{runId}</span></div>
        <div className="panel-body"><Placeholder big="error">{error}</Placeholder></div>
      </div>
    )
  }
  if (!detail)
    return (
      <div className="panel">
        <div className="panel-toolbar"><span className="title">Run</span><PanelLinkControl controller={panelLink} /><span className="id mono">{runId}</span></div>
        <div className="panel-body panel-pad">
          <div className="skeleton" style={{ height: 60, marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 200 }} />
        </div>
      </div>
    )

  if (!matchesRunScope(detail, runScope)) {
    return (
      <div className="panel">
        <div className="panel-toolbar"><span className="title">Run</span><PanelLinkControl controller={panelLink} /><span className="id mono">{runId}</span></div>
        <div className="panel-body"><Placeholder big="INCOMPATIBLE RUN">Select a {runScopeLabel(runScope)} run for this workspace. The linked run was left unchanged for other panels.</Placeholder></div>
      </div>
    )
  }

  const m = detail.manifest
  const command = asStr(m.command)
  const isValidate = detail.kind === 'runs' && m.verdict !== undefined
  const kindLabel = command ?? (detail.kind === 'runs' ? (isValidate ? 'validate' : 'backtest') : detail.kind)
  const leak = asStr(m.leakage_warning)

  const tabs = tabsFor(detail.kind, isValidate)

  const body = (() => {
    if (tab === 'report') return <FigureReport runId={runId} />
    if (tab === 'artifacts')
      return (
        <Artifacts
          manifest={m as ValidateManifest}
          kind={detail.kind}
          runId={runId}
          hasTearsheet={detail.has_tearsheet}
        />
      )
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
        return (
          <PortfolioDetail
            manifest={m as PortfolioManifest}
            eq={eq}
            analytics={portfolioAnalytics}
            analyticsError={portfolioAnalyticsError}
            analyticsLoading={portfolioAnalyticsLoading}
            onLaunch={onLaunch}
          />
        )
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
            return <TradesTab trades={trades} runId={runId} />
          case 'tearsheet':
            return <NativeTearSheetBody detail={detail} equity={eq} trades={trades} />
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
        <PanelLinkControl controller={panelLink} />
        <span className="id mono">{runId}</span>
        <span className="chip kind">{kindLabel}</span>
        <nav className="rd-tabs" role="tablist" aria-label="Run views">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`rd-tab${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
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
