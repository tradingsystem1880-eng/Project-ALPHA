/**
 * The terminal shell (spec 2026-09-01 §4.2): title bar, menu bar, toolbar, docked Market Watch
 * and Navigator on the left, the MDI document area with its bottom tabs, the Toolbox under it,
 * the Data Manager dock on the right and the status bar. Documents come from the registry in
 * `shell/documents.ts`; which ones a profile may open is the manifest's decision. Only the active
 * document mounts, so nothing polls behind a hidden tab.
 */

import { useCallback, useEffect, useState } from 'react'

import { CommandPalette } from './components/CommandPalette'
import { Toasts } from './components/Toasts'
import { OwnerEnrollment } from './auth/OwnerEnrollment'
import { clockText, useNow } from './context/clock'
import { getLinked, setLinked, useLinked } from './context/linked'
import { requestNewIdea } from './context/newIdea'
import { onResearchCase } from './context/researchCase'
import { registerNavigator } from './panels/actions'
import { DataManager } from './panels/DataManager'
import { MarketWatch } from './panels/MarketWatch'
import { Navigator } from './panels/Navigator'
import { DockFrame } from './shell/DockFrame'
import { DocumentArea, type PaneFocus } from './shell/DocumentArea'
import { DOCKS, DOCUMENTS, documentOf } from './shell/documents'
import { Icon } from './shell/icons'
import { MenuBar } from './shell/MenuBar'
import type { WorkspaceMode } from './shell/menuModel'
import {
  EMPTY_MDI,
  activateDocument,
  closeDocument,
  openDocument,
  windowOf,
  type MdiState,
} from './shell/mdiModel'
import { PanelHost } from './shell/PanelHost'
import { profile as manifest, showsWindow, symbolFitsProfile, type DockId, type WindowId } from './shell/profiles'
import { StatusBar } from './shell/StatusBar'
import { Toolbar } from './shell/Toolbar'
import { chartHeader, windowTitle } from './shell/toolbarModel'
import { Toolbox } from './shell/Toolbox'
import { useSymbolVenue } from './shell/useSymbolVenue'
import { initActivity } from './state/activity'
import { setSettings, useSettings, workspaceModeFor, type Profile } from './state/settings'

const MDI_KEY = 'alpha.shell.mdi'
const DOCKS_KEY = 'alpha.shell.docks'

type DockState = Record<DockId, boolean>

/**
 * Every dock open by default; the Toolbox opens only on a window at least as tall as the artboard
 * (991px) so a 900px terminal keeps its documents' room — the strip is one click away.
 */
function restoreDocks(): DockState {
  const state = Object.fromEntries(DOCKS.map((dock) => [dock.id, true])) as DockState
  state.Toolbox = window.innerHeight >= 960
  try {
    const parsed = JSON.parse(localStorage.getItem(DOCKS_KEY) ?? '{}') as Partial<Record<string, unknown>>
    for (const dock of DOCKS) {
      if (typeof parsed[dock.id] === 'boolean') state[dock.id] = parsed[dock.id] as boolean
    }
  } catch {
    // an unreadable saved state falls back to the defaults above
  }
  return state
}

function runIdFromHash(): string | null {
  const match = /(?:^|[#&])run=([0-9a-f]{16})\b/.exec(window.location.hash)
  return match ? match[1] : null
}

/** Documents the profile can open, in registry order. */
function availableDocuments(profile: Profile): { id: WindowId; title: string }[] {
  return DOCUMENTS.filter((item) => showsWindow(profile, item.id)).map((item) => ({
    id: item.id,
    title: item.title,
  }))
}

/** Restore the saved MDI state, dropping anything the current profile does not show. */
function restoreMdi(profile: Profile): MdiState {
  let state: MdiState = EMPTY_MDI
  try {
    const raw = localStorage.getItem(MDI_KEY)
    const parsed = raw ? (JSON.parse(raw) as MdiState) : null
    if (parsed && Array.isArray(parsed.documents)) {
      for (const item of parsed.documents) {
        const window = windowOf(item.key)
        if (DOCUMENTS.some((doc) => doc.id === window) && showsWindow(profile, window)) {
          state = openDocument(state, item.key, item.title)
        }
      }
      if (parsed.active && state.documents.some((item) => item.key === parsed.active)) {
        state = activateDocument(state, parsed.active)
      }
    }
  } catch {
    state = EMPTY_MDI
  }
  if (state.documents.length === 0) {
    state = openDocument(state, 'chart', documentOf('chart').title)
    state = openDocument(state, 'research', documentOf('research').title)
  }
  return state
}

function WorkstationApp() {
  const linked = useLinked()
  const settings = useSettings()
  const { profile } = settings
  const [mdi, setMdi] = useState<MdiState>(() => restoreMdi(profile))
  const [focus, setFocus] = useState<PaneFocus | null>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [docks, setDocks] = useState<DockState>(restoreDocks)
  const [maximised, setMaximised] = useState(false)
  const now = useNow()
  const venue = useSymbolVenue(linked.symbol)

  useEffect(() => {
    initActivity()
  }, [])
  useEffect(() => {
    localStorage.setItem(MDI_KEY, JSON.stringify(mdi))
  }, [mdi])
  useEffect(() => {
    localStorage.setItem(DOCKS_KEY, JSON.stringify(docks))
  }, [docks])
  const setDock = useCallback((id: DockId, open: boolean) => {
    setDocks((current) => (current[id] === open ? current : { ...current, [id]: open }))
  }, [])
  const toggleDock = useCallback((id: DockId) => {
    setDocks((current) => ({ ...current, [id]: !current[id] }))
  }, [])
  useEffect(() => {
    document.documentElement.setAttribute('data-profile', profile)
    // The linked symbol must fit the active profile: a fresh terminal charts the profile's
    // default instead of an empty frame, and a switch drops a symbol of the other market (an
    // equities screener asked about XRP/USDT fails loud). A symbol set later by a run is never
    // fought, which is why this reads the store once here rather than depending on it. A profile
    // switch also closes the documents it does not show; nothing is sent to the server.
    const { symbol } = getLinked()
    if (!symbol || !symbolFitsProfile(profile, symbol)) {
      setLinked({ symbol: manifest(profile).defaultSymbol })
    }
    setMdi((current) => {
      let next: MdiState = current
      for (const item of current.documents) {
        if (!showsWindow(profile, item.window)) next = closeDocument(next, item.key)
      }
      return next
    })
  }, [profile])
  const active = mdi.documents.find((item) => item.key === mdi.active) ?? null
  const title = windowTitle(
    profile,
    { symbol: linked.symbol, timeframe: 'D1' },
    active && active.window !== 'chart' ? active.title : null,
  )
  useEffect(() => {
    document.title = title
  }, [title])

  const activate = useCallback((key: string) => {
    setMdi((current) => activateDocument(current, key))
    const [window, instance] = key.split(/:(.*)/s)
    if (window === 'report' && instance) setLinked({ runId: instance })
  }, [])

  const openWindow = useCallback(
    (id: WindowId, instance?: string, title?: string) => {
      if (!showsWindow(profile, id)) {
        setSettings({ profile: manifest(profile).id === 'crypto' ? 'equities' : 'crypto' })
      }
      const key = instance ? `${id}:${instance}` : id
      setMdi((current) => openDocument(current, key, title ?? documentOf(id).title))
      if (id === 'report' && instance) setLinked({ runId: instance })
    },
    [profile],
  )

  const close = useCallback((key: string) => {
    setMdi((current) => closeDocument(current, key))
  }, [])

  const openRun = useCallback(
    (runId: string, title?: string) => {
      window.location.hash = `run=${runId}`
      openWindow('report', runId, title ?? `run ${runId.slice(0, 8)}`)
    },
    [openWindow],
  )

  const showPane = useCallback(
    (id: WindowId, pane: string) => {
      openWindow(id)
      setFocus((previous) => ({ pane, seq: (previous?.seq ?? 0) + 1 }))
    },
    [openWindow],
  )

  // Panels raise navigation intents ("show the lab with this command") rather than reaching
  // into the shell; the shell decides which document and pane that lands on.
  useEffect(() => {
    registerNavigator({
      showRun: openRun,
      showStrategyLab: () => showPane('build', 'StrategyLab'),
      showProjects: () => showPane('build', 'DevelopmentCenter'),
      showResearchSources: () => showPane('research', 'Literature'),
      showResearchData: () => setDock('DataManager', true),
      showDataSymbol: () => {
        setDock('DataManager', true)
        window.setTimeout(() => document.getElementById('data-manager-symbol')?.focus(), 50)
      },
      showProviders: () => showPane('jobs', 'ProviderSystem'),
      showCompare: () => openWindow('compare'),
    })
  }, [openRun, openWindow, setDock, showPane])

  // `#run=<id>` deep-links to a run's report document.
  useEffect(() => {
    const apply = () => {
      const runId = runIdFromHash()
      if (runId) openWindow('report', runId, `run ${runId.slice(0, 8)}`)
    }
    apply()
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [openWindow])

  // New Idea opens the research case pane and asks the cockpit to focus its capture field.
  const newIdea = useCallback(() => {
    showPane('research', 'ResearchCockpit')
    window.setTimeout(requestNewIdea, 50)
  }, [showPane])

  // R6h (spec §15): a gated surface's "open research case" link lands on the holding case.
  useEffect(
    () =>
      onResearchCase((projectId) => {
        setLinked({ projectId })
        showPane('research', 'ResearchCockpit')
      }),
    [showPane],
  )

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      } else if (event.key === 'Escape') {
        setPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const available = availableDocuments(profile)
  const mode = workspaceModeFor(settings, linked.projectId)
  const chooseMode = (next: WorkspaceMode) => {
    if (!linked.projectId) return
    const projectModes = { ...settings.projectModes }
    if (next === 'guided') delete projectModes[linked.projectId]
    else projectModes[linked.projectId] = next
    setSettings({ projectModes })
  }
  const leftOpen = !maximised && (docks.MarketWatch || docks.Navigator)
  const rightOpen = !maximised && docks.DataManager
  const header = !active
    ? ''
    : active.window === 'chart'
      ? chartHeader(linked.symbol, venue, linked.start, linked.end)
      : active.window === 'report' && active.key !== 'report'
        ? `Strategy Performance Report — ${active.title}`
        : active.window === 'governance'
          ? 'Governance — everything the banners used to say, in one window'
          : active.title

  return (
    <div className={`shell terminal${leftOpen ? '' : ' terminal--no-left'}${rightOpen ? '' : ' terminal--no-right'}`}>
      <header className="titlebar">
        <span className="titlebar-text">{title}</span>
        <span className="titlebar-glyphs" role="group" aria-label="Window controls">
          {(['minimise', 'maximise', 'close'] as const).map((glyph) => (
            <button
              key={glyph}
              type="button"
              className="dock-glyph"
              disabled
              aria-label={`${glyph.charAt(0).toUpperCase()}${glyph.slice(1)} window`}
              title="Window controls belong to the browser"
            >
              <Icon name={glyph} size={12} />
            </button>
          ))}
        </span>
      </header>
      <MenuBar
        open={mdi.documents}
        active={mdi.active}
        available={available}
        shell={{
          docks: DOCKS.map((dock) => ({ id: dock.id, label: dock.title, open: docks[dock.id] })),
          mode: { current: mode, advancedAvailable: linked.projectId !== null },
        }}
        onOpenWindow={(id) => openWindow(id)}
        onActivate={activate}
        onPalette={() => setPaletteOpen(true)}
        onSettings={() => document.querySelector<HTMLButtonElement>('.settings-toggle')?.click()}
        onNewIdea={newIdea}
        onToggleDock={toggleDock}
        onMode={chooseMode}
      />
      <Toolbar
        onData={() => toggleDock('DataManager')}
        onResearch={() => showPane('research', 'ResearchCockpit')}
        onRun={() => showPane('build', 'StrategyLab')}
        onReport={() => linked.runId && openRun(linked.runId)}
        onSearch={() => setPaletteOpen(true)}
        onGovernance={() => openWindow('governance')}
      />
      <div className="terminal-body">
        {leftOpen ? (
          <aside className="dock dock--left" aria-label="Left docks">
            {docks.MarketWatch ? (
              <DockFrame
                id="MarketWatch"
                title={
                  <>
                    Market Watch: <span className="dock-clock">{clockText(now)}</span>
                  </>
                }
                onClose={() => setDock('MarketWatch', false)}
              >
                <MarketWatch />
              </DockFrame>
            ) : null}
            {docks.Navigator ? (
              <DockFrame id="Navigator" onClose={() => setDock('Navigator', false)}>
                <Navigator onOpenRun={openRun} />
              </DockFrame>
            ) : null}
          </aside>
        ) : null}
        <main className="terminal-centre" aria-label="Documents">
          <DocumentArea
            mdi={mdi}
            focus={focus}
            contextKey={linked.projectId ?? 'no-project'}
            header={header}
            maximised={maximised}
            onActivate={activate}
            onClose={close}
            onToggleMaximise={() => setMaximised((value) => !value)}
          />
          {maximised ? null : <Toolbox open={docks.Toolbox} onOpenChange={(open) => setDock('Toolbox', open)} />}
        </main>
        {rightOpen ? (
          <aside className="dock dock--right" aria-label="Data Manager">
            <DockFrame id="DataManager" onClose={() => setDock('DataManager', false)}>
              <PanelHost name="DataManager" component={DataManager} />
            </DockFrame>
          </aside>
        ) : null}
      </div>
      <StatusBar />

      <Toasts onOpenRun={openRun} />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        documents={available}
        onOpenDocument={(id) => openWindow(id)}
        onOpenRun={openRun}
        onNewIdea={newIdea}
      />
    </div>
  )
}

export function App() {
  if (window.location.pathname === '/owner-auth/enroll') return <OwnerEnrollment />
  return <WorkstationApp />
}
