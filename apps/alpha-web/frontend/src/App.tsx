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
import { getLinked, setLinked, useLinked } from './context/linked'
import { requestNewIdea } from './context/newIdea'
import { onResearchCase } from './context/researchCase'
import { registerNavigator } from './panels/actions'
import { DataManager } from './panels/DataManager'
import { MarketWatch } from './panels/MarketWatch'
import { Navigator } from './panels/Navigator'
import { DocumentArea, type PaneFocus } from './shell/DocumentArea'
import { DOCUMENTS, documentOf } from './shell/documents'
import { MenuBar } from './shell/MenuBar'
import {
  EMPTY_MDI,
  activateDocument,
  closeDocument,
  openDocument,
  windowOf,
  type MdiState,
} from './shell/mdiModel'
import { PanelHost } from './shell/PanelHost'
import { profile as manifest, showsWindow, symbolFitsProfile, type WindowId } from './shell/profiles'
import { StatusBar } from './shell/StatusBar'
import { Toolbar } from './shell/Toolbar'
import { venueLabel, windowTitle } from './shell/toolbarModel'
import { Toolbox } from './shell/Toolbox'
import { initActivity } from './state/activity'
import { setSettings, useSettings, type Profile } from './state/settings'

const MDI_KEY = 'alpha.shell.mdi'
const RIGHT_DOCK_KEY = 'alpha.shell.right-dock'

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
  const [rightDock, setRightDock] = useState(() => localStorage.getItem(RIGHT_DOCK_KEY) !== 'closed')

  useEffect(() => {
    initActivity()
  }, [])
  useEffect(() => {
    localStorage.setItem(MDI_KEY, JSON.stringify(mdi))
  }, [mdi])
  useEffect(() => {
    localStorage.setItem(RIGHT_DOCK_KEY, rightDock ? 'open' : 'closed')
  }, [rightDock])
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
  useEffect(() => {
    document.title = windowTitle(profile, {
      symbol: linked.symbol,
      venue: venueLabel(profile),
      timeframe: 'D1',
    })
  }, [profile, linked.symbol])

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
      showResearchData: () => setRightDock(true),
      showProviders: () => showPane('jobs', 'ProviderSystem'),
    })
  }, [openRun, showPane])

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

  const active = mdi.documents.find((item) => item.key === mdi.active) ?? null
  const available = availableDocuments(profile)

  return (
    <div className={`shell terminal${rightDock ? '' : ' terminal--no-right'}`}>
      <header className="titlebar">
        <span className="titlebar-text">
          ALPHA Terminal — {manifest(profile).label}
          {active ? ` — [${active.title}]` : ''}
        </span>
        <button type="button" className="btn ghost titlebar-idea" onClick={newIdea} title="Capture a raw research observation in your own words — no trading rules asked">
          ＋ New Idea
        </button>
      </header>
      <MenuBar
        open={mdi.documents}
        active={mdi.active}
        available={available}
        onOpenWindow={(id) => openWindow(id)}
        onActivate={activate}
        onPalette={() => setPaletteOpen(true)}
        onSettings={() => document.querySelector<HTMLButtonElement>('.settings-toggle')?.click()}
      />
      <Toolbar
        onData={() => setRightDock((value) => !value)}
        onResearch={() => showPane('research', 'ResearchCockpit')}
        onRun={() => showPane('build', 'StrategyLab')}
        onReport={() => linked.runId && openRun(linked.runId)}
        onSearch={() => setPaletteOpen(true)}
        onGovernance={() => openWindow('governance')}
      />
      <div className="terminal-body">
        <aside className="dock dock--left" aria-label="Left docks">
          <section className="dock-section" aria-label="Market Watch">
            <h2 className="dock-title">Market Watch</h2>
            <MarketWatch />
          </section>
          <section className="dock-section dock-section--grow" aria-label="Navigator">
            <h2 className="dock-title">Navigator</h2>
            <Navigator onOpenRun={openRun} />
          </section>
        </aside>
        <main className="terminal-centre" aria-label="Documents">
          <DocumentArea
            mdi={mdi}
            focus={focus}
            contextKey={linked.projectId ?? 'no-project'}
            onActivate={activate}
            onClose={close}
          />
          <Toolbox />
        </main>
        {rightDock ? (
          <aside className="dock dock--right" aria-label="Data Manager">
            <PanelHost name="DataManager" component={DataManager} />
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
