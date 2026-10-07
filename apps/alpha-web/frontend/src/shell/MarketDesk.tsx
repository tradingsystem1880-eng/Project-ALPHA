/** Browser-local layout preferences never alter data identity or research authority. */
import { createPortal } from 'react-dom'
import type { ArchiveChartDataset } from '../api/client'
import { AssistantDock } from '../panels/AssistantDock'
import { ConditionChecklist } from '../panels/ConditionChecklist'
import { IndicatorPicker } from '../components/IndicatorPicker'
import { DeskNotes } from '../panels/DeskNotes'
import { DeskResults } from '../panels/DeskResults'
import { RESULT_TABS, type ResultTab } from './edgeWorkspace'
import './edgeDesk.css'
import { useEffect, useState, type ReactNode, type KeyboardEvent } from 'react'
import { MarketWatch } from '../panels/MarketWatch'
import { Navigator } from '../panels/Navigator'
import { DataManager } from '../panels/DataManager'
import { openRunDetail } from '../panels/actions'
import type { Profile } from '../state/settings'
import { PanelHost } from './PanelHost'
import { restoreDesk, type DeskPreferences } from './terminalModel'

function moveTab(event: KeyboardEvent<HTMLElement>) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
  const index = tabs.indexOf(event.target as HTMLButtonElement)
  if (index < 0) return
  event.preventDefault()
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
  tabs[next]?.focus(); tabs[next]?.click()
}

export function MarketDesk({ children, tools, profile, archive, onFooterMount }: { children: ReactNode; tools: ReactNode; profile: Profile; archive: ArchiveChartDataset | null; onFooterMount?: (node: HTMLDivElement | null) => void }) {
  const key = `alpha.desk.v1.${profile}`
  const [desk, setDesk] = useState(() => {
    try { return restoreDesk(JSON.parse(localStorage.getItem(key) ?? 'null')) }
    catch { return restoreDesk(null) }
  })
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(desk)) }
    catch { /* Layout remains usable when browser persistence is unavailable. */ }
  }, [key, desk])
  const update = (patch: Partial<DeskPreferences>) => setDesk(value => ({ ...value, ...patch }))
  const [edge, setEdge] = useState(() => {
    try { const raw = JSON.parse(localStorage.getItem(`alpha.edge-desk.v1.${profile}`) ?? '{}'); return {
      open: typeof raw.open === 'boolean' ? raw.open : false,
      tab: ['Assistant', 'Conditions', 'Indicators', 'Notes'].includes(raw.tab) ? String(raw.tab) : 'Conditions',
      bottom: typeof raw.bottom === 'boolean' ? raw.bottom : false,
      result: RESULT_TABS.includes(raw.result) ? raw.result as ResultTab : 'Scan results' as ResultTab,
      width: typeof raw.width === 'number' && Number.isFinite(raw.width) ? Math.min(480, Math.max(280, raw.width)) : 340,
    } } catch { return { open: false, tab: 'Conditions', bottom: false, result: 'Scan results' as ResultTab, width: 340 } }
  })
  useEffect(() => { try { localStorage.setItem(`alpha.edge-desk.v1.${profile}`, JSON.stringify(edge)) } catch { /* Optional presentation preferences. */ } }, [edge, profile])
  const dockTools = <div className="market-desk-tools" aria-label="Desk layout">
      {tools}
      <span className="desk-tool-divider" />
      <button className="btn" aria-pressed={desk.watch} onClick={() => update({ watch: !desk.watch, maximized: false })}>Market Watch</button>
      <button className="btn" aria-pressed={desk.data} onClick={() => { update({ data: !desk.data, maximized: false }); setEdge(value => ({ ...value, open: false })) }}>Data Manager</button>
      <button className="btn" aria-pressed={desk.maximized} onClick={() => update({ maximized: !desk.maximized })}>{desk.maximized ? 'Restore chart' : 'Maximize chart'}</button>
      <button className="btn" aria-pressed={edge.open} onClick={() => { setEdge(value => ({ ...value, open: !value.open })); update({ data: false, maximized: false }) }}>Research tools</button>
      <button className="btn" aria-pressed={edge.bottom} onClick={() => { setEdge(value => ({ ...value, bottom: !value.bottom })); update({ maximized: false }) }}>Workspace results</button>
      <details className="desk-options"><summary>Layout</summary><div>
        <button className="btn" onClick={() => { setDesk(restoreDesk(null)); setEdge(value => ({ ...value, open: false, bottom: false })) }}>Analysis layout</button>
        <button className="btn" onClick={() => { setDesk({ ...restoreDesk(null), watch: false, data: true }); setEdge(value => ({ ...value, open: false, bottom: false })) }}>Data review layout</button>
        <label>Watchlist width<input aria-label="Watchlist width" type="range" min="230" max="420" step="5" value={desk.width} onChange={event => update({ width: Number(event.target.value) })} /></label>
        <label>Research dock width<input aria-label="Research dock width" type="range" min="280" max="480" step="10" value={edge.width} onChange={event => setEdge(value => ({ ...value, width: Number(event.target.value) }))} /></label>
      </div></details>
    </div>
  return <div className={`market-desk${desk.maximized ? ' market-desk-maximized' : ''}`}>
    {document.getElementById('dock-toolbar') ? createPortal(dockTools, document.getElementById('dock-toolbar')!) : dockTools}
    <div className="market-desk-windows">
      {desk.watch && !desk.maximized ? <aside className="market-desk-left" style={{ width: desk.width }} aria-label="Market tools">
        <section className="terminal-dock"><h2>Market Watch</h2><MarketWatch /></section>
        <section className="terminal-dock"><h2>Navigator</h2><Navigator onOpenRun={openRunDetail} /></section>
      </aside> : null}
      <div className="market-desk-chart">{children}<div className="chart-document-footer" ref={onFooterMount}/></div>
      {edge.open && !desk.maximized ? <aside className="edge-dock terminal-dock" style={{ width: edge.width }} aria-label="Research tools">
        <nav onKeyDown={moveTab} role="tablist" aria-label="Research tools tabs">{['Assistant', 'Conditions', 'Indicators', 'Notes'].map(tab => <button className="btn" role="tab" aria-selected={edge.tab === tab} tabIndex={edge.tab === tab ? 0 : -1} key={tab} onClick={() => setEdge(value => ({ ...value, tab }))}>{tab}</button>)}</nav>
        <div className="edge-dock-body">{edge.tab === 'Assistant' ? <AssistantDock archive={archive} /> : edge.tab === 'Conditions' ? <ConditionChecklist archive={archive} /> : edge.tab === 'Indicators' ? <IndicatorPicker inline /> : <DeskNotes />}</div>
      </aside> : null}
      {desk.data && !desk.maximized ? <aside className="market-desk-right terminal-dock" aria-label="Data Manager dock"><h2>Data Manager</h2><PanelHost name="DataManager" component={DataManager} /></aside> : null}
    </div>
    {edge.bottom && !desk.maximized ? <section className="edge-results" aria-label="Workspace results"><nav onKeyDown={moveTab} role="tablist" aria-label="Workspace result tabs">{RESULT_TABS.map(tab => <button className="btn" key={tab} role="tab" aria-selected={edge.result === tab} tabIndex={edge.result === tab ? 0 : -1} onClick={() => setEdge(value => ({ ...value, result: tab }))}>{tab}</button>)}</nav><div className="edge-results-body"><DeskResults tab={edge.result} /></div></section> : null}
  </div>
}
