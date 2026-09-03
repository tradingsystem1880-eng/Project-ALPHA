// Strategy Performance Report — the run story, read the way a trader reads a report window
// (spec 2026-09-01 §4.4): a left tree (Strategy Analysis · Trade Analysis · Periodical Analysis ·
// Robustness · Settings & data) selects one view; Summary is a key/value table of what the
// manifest recorded; figure views are the server-rendered figure pack, each figure carrying the
// question it answers; the gate narrative, the trade blotter, the stress test and artifact
// provenance keep their views under the same tree. Governance watermarks are one chip in the
// title bar whose title carries the full sentences.

import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { FigureCatalogue, RunDetail as RunDetailData, TradeRow } from '../../api/types'
import type { PanelHandleProps } from '../../context/panelHandle'
import type { ValidateManifest } from '../../explain/types'
import { Placeholder } from '../../components/Placeholder'
import { usePanelLinked } from '../../context/usePanelLinked'
import { researchGateWatermark } from '../researchGateModel'
import { FigureSection } from '../FigureReport'
import { reportTree, summaryRows, tradesCsv, watermarkChip } from '../reportModel'
import { Icon } from '../../shell/icons'
import { setSettings, useSettings } from '../../state/settings'
import { openCompare, openStrategyLab } from '../actions'
import { asStr } from './commonUtils'
import { Artifacts } from './Artifacts'
import { Gates } from './Gates'
import { rerunCommand } from './rerun'
import { Risk } from './Risk'
import { TradesTab } from './TradesTab'

/** Hand the browser a CSV file; the rows are the trades projection exactly. */
function downloadCsv(name: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

export function RunDetail(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const { explain } = useSettings()
  const runId = panelLink.linked.runId ?? ''
  const [detail, setDetail] = useState<RunDetailData | null>(null)
  const [trades, setTrades] = useState<TradeRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [catalogue, setCatalogue] = useState<FigureCatalogue | null>(null)
  const [view, setView] = useState('summary')

  useEffect(() => {
    if (!runId) {
      setDetail(null)
      return
    }
    let live = true
    setDetail(null)
    setError(null)
    setView('summary')
    setCatalogue(null)
    api
      .figures(runId)
      .then((value) => live && setCatalogue(value))
      .catch(() => live && setCatalogue(null))
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
  const tree = reportTree({
    kind: detail.kind,
    isValidate,
    hasTrades: Boolean(detail.has_trades),
    tradeCount: detail.has_trades ? trades.length : null,
    items: catalogue?.items ?? [],
  })
  const leaves = tree.flatMap((group) => group.leaves)
  const leaf = leaves.find((item) => item.id === view) ?? leaves[0]
  const chip = watermarkChip(gateWatermark, detail.run_context_watermark)
  const rerun = rerunCommand(command, detail.kind, isValidate)
  // Identity lives at the top level on some manifests and under `metadata` on others.
  const metadata = (manifest.metadata ?? {}) as Record<string, unknown>
  const symbol = asStr(manifest.symbol) ?? asStr(metadata.symbol) ?? ''
  // Save PNG hands over the first drawable figure of the current view; nothing is drawn here.
  const firstFigure = (catalogue?.items ?? []).find((item) => leaf.figureIds.includes(item.figure_id) && item.available) ?? null
  const notes = explain === 'narrative'

  const body = (() => {
    switch (leaf.id) {
      case 'summary':
        return (
          <table className="blotter summary-table">
            <caption>Summary — what this run recorded</caption>
            <tbody>
              {summaryRows(manifest as Record<string, unknown>).map((row) => (
                <tr key={row.label}>
                  <td className="k">{row.label}</td>
                  <td className="mono">{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      case 'gates':
        return <Gates manifest={manifest as ValidateManifest} />
      case 'trades':
        return <TradesTab trades={trades} runId={runId} />
      case 'stress':
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
      default: {
        if (leaf.empty) return <Placeholder big={leaf.label}>{leaf.reason}</Placeholder>
        const wanted = new Set(leaf.figureIds)
        const items = (catalogue?.items ?? []).filter((item) => wanted.has(item.figure_id))
        return <FigureSection runId={runId} runName={detail.display_name} title={leaf.label} items={items} reason={leaf.reason} />
      }
    }
  })()

  return (
    <div className="panel report-document">
      <div className="panel-toolbar report-toolbar" role="toolbar" aria-label="Report toolbar">
        <button type="button" className="btn glyph" disabled aria-label="Save report" title="The report is its run directory on disk — already saved, immutable">
          <Icon name="report" />
        </button>
        <button type="button" className="btn glyph" aria-label="Print" title="Print this report view" onClick={() => window.print()}>
          <Icon name="doc" />
        </button>
        <span className="toolbar-sep" />
        <button
          type="button"
          className="btn"
          disabled={!trades.length}
          title={trades.length ? 'Download the trades projection as CSV, exactly as served' : 'No trades to export'}
          onClick={() => downloadCsv(`${runId.slice(0, 8)}-trades.csv`, tradesCsv(trades))}
        >
          Export CSV
        </button>
        {firstFigure ? (
          <a
            className="btn"
            href={`/api/runs/${runId}/figures/${firstFigure.figure_id}/image?fmt=png`}
            download={`${runId.slice(0, 8)}-${firstFigure.figure_id}.png`}
            title={`Save ${firstFigure.figure_id} as PNG`}
          >
            Save PNG
          </a>
        ) : (
          <button type="button" className="btn" disabled title="This view has no figure to save">
            Save PNG
          </button>
        )}
        <button type="button" className="btn" onClick={openCompare} title="Open the Compare document and tick this run there">
          Compare…
        </button>
        {rerun ? (
          <button className="btn" onClick={() => onLaunch(rerun, symbol)} title="Prefill Strategy Development with this run's command">
            Run again
          </button>
        ) : null}
        <span className="chip kind">{kindLabel}</span>
        {chip ? (
          <span className="chip warn rg-watermark-chip" title={chip.title}>
            {chip.text}
          </span>
        ) : null}
        <span className="spacer" />
        <button
          type="button"
          className={`btn${notes ? ' active' : ''}`}
          aria-pressed={notes}
          title="Show each figure's question, uncertainty and caveat beside it"
          onClick={() => setSettings({ explain: notes ? 'terse' : 'narrative' })}
        >
          Notes
        </button>
      </div>
      {leak ? <p className="leak-warning">{leak}</p> : null}
      <div className="panel-body rd-body figure-report">
        <nav className="figure-rail report-tree">
          <ul role="tree" aria-label="Report sections">
            {tree.map((group) => (
              <li key={group.label} role="treeitem" aria-expanded="true">
                <span className="tree-group">
                  <span className="tree-caret" aria-hidden="true">▾</span>
                  <Icon name="folder" size={12} />
                  {group.label}
                </span>
                <ul role="group">
                  {group.leaves.map((item) => (
                    <li
                      key={item.id}
                      role="treeitem"
                      aria-selected={leaf.id === item.id}
                      className={item.id === 'artifacts' ? 'advanced-only' : undefined}
                    >
                      <button
                        type="button"
                        className={`tree-leaf${leaf.id === item.id ? ' active' : ''}${item.empty ? ' empty' : ''}`}
                        title={item.reason ?? undefined}
                        onClick={() => setView(item.id)}
                      >
                        <Icon name="doc" size={12} />
                        {item.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </nav>
        <div className="figure-scroll">
          {body}
          <p className="report-hint muted">Double-click any chart to open it full-screen · Save PNG / SVG / Copy from there</p>
        </div>
      </div>
    </div>
  )
}
