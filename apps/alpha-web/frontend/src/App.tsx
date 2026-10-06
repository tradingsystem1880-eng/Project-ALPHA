/** Workflow pages over the existing CLI-backed panels. Only the selected task mounts. */
import { useCallback, useEffect, useState, useRef, type ReactNode } from 'react'
import type { ArchiveChartDataset } from './api/client'
import { createPortal } from 'react-dom'
import { CommandPalette } from './components/CommandPalette'
import { IndicatorsDialog } from './components/IndicatorsDialog'
import { Toasts } from './components/Toasts'
import { OwnerEnrollment } from './auth/OwnerEnrollment'
import { getLinked, getLinkedWorkspace, restoreLinked, setLinked, useLinked } from './context/linked'
import { requestNewIdea } from './context/newIdea'
import { onResearchCase } from './context/researchCase'
import { ChartWorkspace } from './shell/ChartWorkspace'
import { MenuBar } from './shell/MenuBar'
import { restoreDocumentTabs, type TerminalDocument } from './shell/documentTabs'
import { Toolbox } from './shell/Toolbox'
import { ResearchBacklog } from './panels/ResearchBacklog'
import { registerNavigator } from './panels/actions'
import { ContextBar } from './shell/ContextBar'
import { DOCUMENTS } from './shell/documents'
import { PanelHost } from './shell/PanelHost'
import { showsWindow, symbolFitsProfile, type WindowId } from './shell/profiles'
import { StatusChip, WorkspaceModeAttribute } from './shell/Toolbar'
import { StatusBar } from './shell/StatusBar'
import { functionEntries } from './shell/terminalModel'
import { workflowPages, resolveWorkflow, workflowHash, documentRoute, type PageId } from './shell/workflowModel'
import { initActivity, useActivityField } from './state/activity'
import { setSettings, useSettings, workspaceModeFor } from './state/settings'

const CONTEXT_KEY = 'alpha.workflow.context'
function restoreContext() {
  try { const raw = localStorage.getItem(CONTEXT_KEY); if (raw) restoreLinked(JSON.parse(raw)) }
  catch { /* An unreadable preference must not prevent the app opening. */ }
}
restoreContext()

function WorkstationApp() {
  const linked = useLinked()
  const settings = useSettings()
  const { profile } = settings
  const [hash, setHash] = useState(window.location.hash)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [archiveContext, setArchiveContext] = useState<ArchiveChartDataset | null>(null)
  const [openTabs, setOpenTabs] = useState<TerminalDocument[]>(() => {
    try { return (['crypto', 'equities'] as const).flatMap(p => restoreDocumentTabs(JSON.parse(localStorage.getItem(`alpha.documents.v1.${p}`) ?? '[]'), p)) } catch { return [] }
  })
  const [toolboxOpen, setToolboxOpen] = useState(window.innerHeight >= 960)
  const [chartFooter, setChartFooter] = useState<HTMLElement | null>(null)
  const [workspaceRequest, setWorkspaceRequest] = useState<{ sequence: number; profile: 'crypto' | 'equities'; action: 'canonical' | 'duplicate' | 'tile'; archive?: ArchiveChartDataset } | null>(null)
  const requestSequence = useRef(0)
  const requestWorkspace = useCallback((action: 'canonical' | 'duplicate' | 'tile', archive?: ArchiveChartDataset) => setWorkspaceRequest({ sequence: ++requestSequence.current, profile, action, archive }), [profile])
  const [chartOpened, setChartOpened] = useState(false)
  const [lastTasks, setLastTasks] = useState<Record<string, string>>(() => {
    try {
      const value: unknown = JSON.parse(localStorage.getItem('alpha.last-tasks.v1') ?? '{}')
      return value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).filter(([, pane]) => typeof pane === 'string')) : {}
    } catch { return {} }
  })
  const [indicatorsOpen, setIndicatorsOpen] = useState(false)
  const running = useActivityField('runningJobs')
  const route = resolveWorkflow(hash, profile)
  const pages = workflowPages(profile)
  const page = pages.find(item => item.id === route.page)!
  const pane = page.panes.find(item => item.name === route.pane)
  const go = useCallback((page: PageId, pane?: string, runId?: string) => {
    window.location.hash = workflowHash(page, pane, pane === 'RunDetail' ? runId ?? getLinked().runId ?? undefined : runId)
    setHash(window.location.hash)
  }, [])
  const openRun = useCallback((runId: string) => { go('results', 'RunDetail', runId); setArchiveContext(null); setLinked({ runId }) }, [go])
  const openDocument = useCallback((id: WindowId) => {
    if (!showsWindow(profile, id)) setSettings({ profile: profile === 'crypto' ? 'equities' : 'crypto' })
    const destination = documentRoute(id)
    go(destination.page, destination.pane)
  }, [go, profile])
  const newIdea = useCallback(() => {
    go('research', 'ResearchCockpit')
    window.setTimeout(requestNewIdea, 100)
  }, [go])
  useEffect(() => { initActivity() }, [])
  useEffect(() => {
    if (route.pane) setLastTasks(previous => previous[`${profile}:${route.page}`] === route.pane ? previous : { ...previous, [`${profile}:${route.page}`]: route.pane! })
  }, [profile, route.page, route.pane])
  useEffect(() => {
    try { localStorage.setItem('alpha.last-tasks.v1', JSON.stringify(lastTasks)) }
    catch { /* Task navigation remains available without persistence. */ }
  }, [lastTasks])
  useEffect(() => {
    const update = () => setHash(window.location.hash)
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  useEffect(() => {
    if (route.runId) setLinked({ runId: route.runId })
  }, [route.runId])
  useEffect(() => {
    try { localStorage.setItem(CONTEXT_KEY, JSON.stringify(getLinkedWorkspace())) }
    catch { /* Private mode or a full browser store must not make the app unusable. */ }
  }, [linked])
  useEffect(() => {
    const symbol = getLinked().symbol
    if (symbol && !symbolFitsProfile(profile, symbol)) setLinked({ symbol: null })
  }, [profile])
  useEffect(() => { document.title = `ALPHA · ${page.title}` }, [page.title])
  useEffect(() => {
    registerNavigator({
      showChart: () => { setArchiveContext(null); requestWorkspace('canonical'); go('data', 'PriceChart') },
      showCryptoData: () => go('data', 'FundingData'),
      showArchiveChart: dataset => { setArchiveContext(dataset); requestWorkspace('canonical', dataset); go('data', 'PriceChart') },
      showRules: () => go('strategies', 'StrategyBuilder'),
      showScanner: () => go('strategies', 'Scanner'),
      showRun: openRun,
      showStrategyLab: () => go('strategies', 'StrategyLab'),
      showProjects: () => go('strategies', 'DevelopmentCenter'),
      showResearchSources: () => go('research', 'Literature'),
      showResearchData: () => go('data', 'DataManager'),
      showDataSymbol: () => { go('data', 'DataManager'); window.setTimeout(() => document.getElementById('data-manager-symbol')?.focus(), 100) },
      showProviders: () => go('operations', 'ProviderSystem'),
      showCompare: () => go('results', 'CompareRuns'),
      showIndicators: () => setIndicatorsOpen(true),
    })
    return onResearchCase(projectId => { setLinked({ projectId }); go('research', 'ResearchCockpit') })
  }, [go, openRun, requestWorkspace])
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPaletteOpen(value => !value) }
      if (event.key === 'F2') { event.preventDefault(); setPaletteOpen(true) }
      if (event.key === 'F1') { event.preventDefault(); setPaletteOpen(true) }
      if (event.key === 'Escape') setPaletteOpen(false)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [])
  useEffect(() => { if (route.pane !== 'PriceChart') setArchiveContext(null) }, [route.pane])
  useEffect(() => { setArchiveContext(null) }, [linked.symbol, linked.linkGroup, profile])
  useEffect(() => { if (linked.runId || linked.snapshotId) setArchiveContext(null) }, [linked.runId, linked.snapshotId])
  const tabKey = `${profile}:${route.page}:${route.pane ?? ''}:${route.runId ?? ''}`
  useEffect(() => {
    if (route.pane === 'PriceChart') setChartOpened(true)
    setOpenTabs(tabs => tabs.some(t => t.key === tabKey) ? tabs : [...tabs, { key: tabKey, title: route.pane === 'PriceChart' ? 'Price' : pane?.title ?? page.title, page: route.page, pane: route.pane ?? undefined, runId: route.runId ?? undefined }])
  }, [tabKey, route.page, route.pane, route.runId, pane?.title, page.title])
  useEffect(() => {
    try { for (const market of ['crypto', 'equities']) localStorage.setItem(`alpha.documents.v1.${market}`, JSON.stringify(openTabs.filter(t => t.key.startsWith(`${market}:`)))) } catch { /* Tabs work without persistence. */ }
  }, [openTabs])
  const visibleTabs = openTabs.filter(t => t.key.startsWith(`${profile}:`))
  const closeTab = (key: string) => {
    if (openTabs.find(t => t.key === key)?.pane === 'PriceChart') setChartOpened(false)
    const index = visibleTabs.findIndex(t => t.key === key)
    const remaining = visibleTabs.filter(t => t.key !== key)
    setOpenTabs(tabs => tabs.filter(t => t.key !== key))
    if (key === tabKey) { const next = remaining[Math.max(0, index - 1)]; go(next?.page ?? 'overview', next?.pane, next?.runId) }
  }
  const mode = workspaceModeFor(settings, linked.projectId)
  const documentFooter: ReactNode = <><nav className="document-strip" aria-label="Document navigation"><div className="document-tabs" role="tablist" aria-label="Open documents" onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
        const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role=tab]'))
        const index = tabs.indexOf(document.activeElement as HTMLButtonElement)
        if (index < 0) return
        event.preventDefault()
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
        tabs[next]?.focus(); tabs[next]?.click()
      }}>{visibleTabs.map(tab => <button key={tab.key} className="btn" role="tab" tabIndex={tab.key === tabKey ? 0 : -1} aria-selected={tab.key === tabKey} onClick={() => go(tab.page, tab.pane, tab.runId)}>{tab.title}{tab.runId ? ` · ${tab.runId.slice(0, 8)}` : ''}</button>)}</div><button className="btn" aria-label={`Close document ${visibleTabs.find(t => t.key === tabKey)?.title ?? 'active'}`} onClick={() => closeTab(tabKey)}>×</button></nav>
      <Toolbox open={toolboxOpen && route.pane === 'PriceChart'} onOpenChange={setToolboxOpen}/></>
  return <div className="workflow-shell shell">
    <WorkspaceModeAttribute />
    <a className="workflow-skip" href="#workflow-main" onClick={event => { event.preventDefault(); document.getElementById('workflow-main')?.focus() }}>Skip to content</a>
    <div role="region" aria-label="Terminal title"><h1 className="terminal-titlebar">ALPHA Terminal — {profile === 'crypto' ? 'Crypto' : 'Equities'}{archiveContext ? ` — [${archiveContext.instrument},${archiveContext.frequency}] — ${archiveContext.venue} ${archiveContext.market_type} archive` : linked.symbol ? ` — [${linked.symbol},${linked.timeframe}]` : ''}</h1></div>
    <nav aria-label="Terminal navigation"><MenuBar tasks={pages.flatMap(p => p.panes.map(pane => ({ title: `${p.title} › ${pane.title}`, page: p.id, pane: pane.name })))} onTask={(page, pane) => go(page as PageId, pane)} open={visibleTabs.map(t => ({ key: t.key, title: t.title, window: 'chart' as WindowId }))} active={tabKey} available={DOCUMENTS.filter(doc => showsWindow(profile, doc.id))} shell={{ mode: { current: mode, advancedAvailable: Boolean(linked.projectId) } }} onOpenWindow={openDocument} onActivate={key => { const tab = openTabs.find(t => t.key === key); if (tab) go(tab.page, tab.pane, tab.runId) }} onPalette={() => setPaletteOpen(true)} onSettings={() => go('settings', 'Governance')} onNewIdea={newIdea} onIndicators={() => setIndicatorsOpen(true)} onNewChart={() => { go('data', 'PriceChart'); requestWorkspace('duplicate') }} onTile={() => { go('data', 'PriceChart'); requestWorkspace('tile') }} onToggleDock={() => go('data', 'DataManager')} onMode={value => linked.projectId && setSettings({ projectModes: { ...settings.projectModes, [linked.projectId]: value } })} /></nav>
    <div className="workflow-content">
      <header className="workflow-topbar" aria-label="Terminal controls">
        <div id="analytical-toolbar" hidden={route.pane !== 'PriceChart'} /><details className="desk-options" hidden={route.pane !== 'PriceChart'}><summary>Docks</summary><div id="dock-toolbar" /></details>
        <label>Profile<select aria-label="Market profile" className="field" value={profile} onChange={e => setSettings({ profile: e.target.value as 'crypto' | 'equities' })}><option value="crypto">Crypto</option><option value="equities">Equities</option></select></label>
        <ContextBar archive={archiveContext} />
        <button className="btn toolbar-search" onClick={() => setPaletteOpen(true)}>Search · Ctrl+K</button>
        <StatusChip onOpenGovernance={() => go('settings', 'Governance')} />
        <button className="btn" onClick={() => go('settings', 'Governance')}>Governance</button>
      </header>
      <main id="workflow-main" className="workflow-main" tabIndex={-1}>
        <header className="document-caption" hidden={route.pane === 'PriceChart'}>{pane?.title ?? page.title}{linked.projectId ? <span className="chip" title={linked.projectId}>Project {linked.projectId.slice(0, 12)}</span> : null}</header>
        {page.id === 'overview' ? <>
          <div className="workflow-cards">{pages.filter(item => !['overview', 'settings'].includes(item.id)).map(item => <a key={item.id} href={workflowHash(item.id)}><h2>{item.title}</h2><p>{item.description}</p><span>Open {item.title.toLowerCase()} →</span></a>)}</div>
          <div className="workflow-overview-status"><h2>Continue your work</h2><p>{running} active jobs · {linked.projectId ? `Selected project: ${linked.projectId}` : 'No project selected. Start a research idea or choose a case below.'}</p><button className="btn" onClick={() => go('operations', 'ProviderSystem')}>Check system readiness</button></div>
          <div className="workflow-panel workflow-overview-panel"><PanelHost name="ResearchBacklog" component={ResearchBacklog} /></div>
        </> : <>
          {page.id === 'settings' ? <div className="workflow-preferences">
            <label>Density<select aria-label="Density" className="field" value={settings.density} onChange={e => setSettings({ density: e.target.value as 'compact' | 'comfortable' })}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
            <label>Explanations<select aria-label="Explanations" className="field" value={settings.explain} onChange={e => setSettings({ explain: e.target.value as 'terse' | 'narrative' })}><option value="narrative">Detailed notes</option><option value="terse">Concise</option></select></label>
            <label>Project detail<select aria-label="Project detail" className="field" value={mode} disabled={!linked.projectId} title={!linked.projectId ? 'Select a project to change its detail level' : undefined} onChange={e => linked.projectId && setSettings({ projectModes: { ...settings.projectModes, [linked.projectId]: e.target.value as 'guided' | 'advanced' } })}><option value="guided">Guided</option><option value="advanced">Advanced</option></select></label>
          </div> : null}
          {pane && pane.name !== 'PriceChart' ? <section className="workflow-panel" aria-label={pane.title}><PanelHost key={`${pane.name}:${linked.projectId ?? ''}`} name={pane.name} component={pane.component} params={pane.params} /></section> : null}

        </>}
        {chartOpened ? <div className="chart-document" hidden={route.pane !== 'PriceChart'}><ChartWorkspace key={profile} profile={profile} archive={archiveContext} onArchiveChange={setArchiveContext} visible={route.pane === 'PriceChart'} command={workspaceRequest} onCommandHandled={sequence => setWorkspaceRequest(v => v?.sequence === sequence ? null : v)} onFooterMount={setChartFooter}/></div> : null}
      </main>
      {route.pane === 'PriceChart' && chartFooter ? createPortal(documentFooter, chartFooter) : documentFooter}
      <StatusBar />
    </div>
    {indicatorsOpen ? <IndicatorsDialog onClose={() => setIndicatorsOpen(false)} /> : null}
    <Toasts onOpenRun={openRun} />
    <CommandPalette functions={functionEntries(profile)} onNavigate={go} open={paletteOpen} onClose={() => setPaletteOpen(false)} documents={DOCUMENTS.filter(doc => showsWindow(profile, doc.id))} onOpenDocument={openDocument} onOpenRun={openRun} onNewIdea={newIdea} />
  </div>
}

export function App() {
  return window.location.pathname === '/owner-auth/enroll' ? <OwnerEnrollment /> : <WorkstationApp />
}
