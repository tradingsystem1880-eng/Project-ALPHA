// Run Detail — the run story.
//
// Report is the surface for every run kind: the server-rendered figure pack, each figure
// carrying the question it answers and what this run's numbers say. The kind-specific
// chart views that used to live here are gone, because every one of them is now a figure
// drawn at full size with an explanation attached.
//
// What survives beside Report is what a figure cannot carry: the gate narrative, a sortable
// trade blotter, an interactive stress test, and artifact provenance.

import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { RunDetail as RunDetailData, TradeRow } from '../../api/types'
import type { PanelHandleProps } from '../../context/panelHandle'
import type { ValidateManifest } from '../../explain/types'
import { Placeholder } from '../../components/Placeholder'
import { usePanelLinked } from '../../context/usePanelLinked'
import { openStrategyLab } from '../actions'
import { researchGateWatermark } from '../researchGateModel'
import { FigureReport } from '../FigureReport'
import { asStr } from './commonUtils'
import { Artifacts } from './Artifacts'
import { Gates } from './Gates'
import { rerunCommand } from './rerun'
import { Risk } from './Risk'
import { TradesTab } from './TradesTab'

type TabId = 'report' | 'gates' | 'trades' | 'risk' | 'artifacts'

interface Tab {
  id: TabId
  label: string
}

/** Every run kind gets Report; the rest depend on what the run actually recorded. */
function tabsFor(kind: string, isValidate: boolean, hasTrades: boolean): Tab[] {
  const tabs: Tab[] = [{ id: 'report', label: 'Report' }]
  if (isValidate) tabs.push({ id: 'gates', label: 'Gates' })
  if (hasTrades) tabs.push({ id: 'trades', label: 'Trades' })
  if (kind === 'runs') tabs.push({ id: 'risk', label: 'Stress test' })
  tabs.push({ id: 'artifacts', label: 'Artifacts' })
  return tabs
}

export function RunDetail(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const runId = panelLink.linked.runId ?? ''
  const [detail, setDetail] = useState<RunDetailData | null>(null)
  const [trades, setTrades] = useState<TradeRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<TabId>('report')

  useEffect(() => {
    if (!runId) {
      setDetail(null)
      return
    }
    let live = true
    setDetail(null)
    setError(null)
    setTab('report')
    api
      .run(runId)
      .then((value) => {
        if (!live) return
        setDetail(value)
        if (value.has_trades) {
          api
            .trades(runId)
            .then((rows) => live && setTrades(rows))
            .catch(() => live && setTrades([]))
        } else {
          setTrades([])
        }
      })
      .catch((cause: unknown) => live && setError(String(cause)))
    return () => {
      live = false
    }
  }, [runId])

  const onLaunch = useMemo(
    () => (command: string, args: string) => openStrategyLab({ command, args }),
    [],
  )

  if (!runId)
    return (
      <Placeholder big="Select a run">
        Pick one from the Library on the left, or press ⌘K.
      </Placeholder>
    )
  if (error) return <Placeholder big="Could not load this run">{error}</Placeholder>
  if (!detail) return <Placeholder big="Loading run…" />

  const manifest = detail.manifest
  // ADR-0026: an override-launched run keeps its exploratory marker on every report surface.
  const gateWatermark = researchGateWatermark(detail)
  const command = asStr(manifest.command)
  const isValidate = detail.kind === 'runs' && manifest.verdict !== undefined
  const kindLabel =
    command ?? (detail.kind === 'runs' ? (isValidate ? 'validate' : 'backtest') : detail.kind)
  const leak = asStr(manifest.leakage_warning)
  const tabs = tabsFor(detail.kind, isValidate, Boolean(detail.has_trades))
  const rerun = rerunCommand(command, detail.kind, isValidate)
  // Identity lives at the top level on some manifests and under `metadata` on others.
  const metadata = (manifest.metadata ?? {}) as Record<string, unknown>
  const symbol = asStr(manifest.symbol) ?? asStr(metadata.symbol) ?? ''

  const body = (() => {
    switch (tab) {
      case 'gates':
        return <Gates manifest={manifest as ValidateManifest} />
      case 'trades':
        return <TradesTab trades={trades} runId={runId} />
      case 'risk':
        return <Risk manifest={manifest as ValidateManifest} runId={runId} />
      case 'artifacts':
        return (
          <Artifacts
            manifest={manifest as ValidateManifest}
            kind={detail.kind}
            runId={runId}
            hasTearsheet={detail.has_tearsheet}
          />
        )
      default:
        return <FigureReport runId={runId} />
    }
  })()

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Run</span>
        <span className="id mono">{runId}</span>
        <span className="chip kind">{kindLabel}</span>
        <nav className="rd-tabs" role="tablist" aria-label="Run views">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={`rd-tab${tab === item.id ? ' active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <span className="spacer" />
        {rerun ? (
          <button className="btn ghost" onClick={() => onLaunch(rerun, symbol)}>
            Run again
          </button>
        ) : null}
      </div>
      {gateWatermark ? (
        <div className="leak rg-watermark-banner">
          ▲ {gateWatermark} — launched under an owner research-gate override
        </div>
      ) : null}
      {leak ? <p className="leak-warning">{leak}</p> : null}
      <div className="panel-body rd-body">{body}</div>
    </div>
  )
}
