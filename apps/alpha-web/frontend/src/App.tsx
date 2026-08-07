/**
 * The shell: a screen switcher, a persistent Library, and one shared context.
 *
 * This replaced a free-form docking desk. Docking is the right answer when nobody can
 * predict which panels a user needs beside which; here the workflow is known, so each
 * screen is laid out once for the job it serves and the 22 panels stop being furniture the
 * user has to arrange. Only the active screen mounts, so nothing polls behind a hidden tab.
 */

import { useCallback, useEffect, useState } from 'react'

import { CommandPalette } from './components/CommandPalette'
import { Toasts } from './components/Toasts'
import { setLinked } from './context/linked'
import { registerNavigator } from './panels/actions'
import { ContextBar } from './shell/ContextBar'
import { LibraryRail } from './shell/LibraryRail'
import { PanelHost } from './shell/PanelHost'
import { areasOf, RESULTS_SCREEN, SCREENS, screen, type ScreenId } from './shell/screens'
import { initActivity, useActivityField } from './state/activity'
import { setSettings, useSettings } from './state/settings'

const SCREEN_KEY = 'alpha.shell.screen'
const RAIL_KEY = 'alpha.shell.rail'

function runIdFromHash(): string | null {
  const match = /(?:^|[#&])run=([0-9a-f]{16})\b/.exec(window.location.hash)
  return match ? match[1] : null
}

function StatusCluster() {
  const connection = useActivityField('connection')
  const runningJobs = useActivityField('runningJobs')
  const dotClass = connection === 'live' ? '' : connection === 'connecting' ? 'busy' : 'down'
  return (
    <div className="status" title={`activity stream: ${connection}`}>
      <span className={`dot ${dotClass}`} />
      {connection === 'live' ? 'live' : connection}
      {runningJobs > 0 ? <span className="chip kind">{runningJobs} running</span> : null}
    </div>
  )
}

function SettingsMenu() {
  const { density, explain } = useSettings()
  const [open, setOpen] = useState(false)
  return (
    <div className="settings-menu">
      <button className="kbd" aria-expanded={open} onClick={() => setOpen((v) => !v)} title="View settings">
        ⚙
      </button>
      {open ? (
        <div className="settings-pop" role="dialog" aria-label="View settings">
          <button
            className="settings-row"
            onClick={() => setSettings({ density: density === 'compact' ? 'comfortable' : 'compact' })}
          >
            <span>Density</span>
            <span className="mono">{density}</span>
          </button>
          <button
            className="settings-row"
            onClick={() => setSettings({ explain: explain === 'terse' ? 'narrative' : 'terse' })}
          >
            <span>Explanations</span>
            <span className="mono">{explain}</span>
          </button>
        </div>
      ) : null}
    </div>
  )
}

/** A request from the shell to bring one named pane to the front. */
interface PaneFocus {
  pane: string
  /** Bumped on every request so asking twice for the same pane still focuses it. */
  seq: number
}

/** One screen area, with tabs when several panes share it. */
function Area({
  areaName,
  panes,
  focus,
}: {
  areaName: string
  panes: ReturnType<typeof areasOf>[number][1]
  focus: PaneFocus | null
}) {
  const [active, setActive] = useState(0)

  useEffect(() => {
    if (!focus) return
    const index = panes.findIndex((item) => item.name === focus.pane)
    if (index >= 0) setActive(index)
  }, [focus, panes])

  const pane = panes[Math.min(active, panes.length - 1)]
  return (
    <section className="area" style={{ gridArea: areaName }} aria-label={pane.title}>
      {panes.length > 1 ? (
        <nav className="area-tabs" role="tablist" aria-label={`${areaName} panes`}>
          {panes.map((item, index) => (
            <button
              key={item.name}
              role="tab"
              aria-selected={index === active}
              className={`area-tab${index === active ? ' active' : ''}`}
              onClick={() => setActive(index)}
            >
              {item.title}
            </button>
          ))}
        </nav>
      ) : null}
      <div className="area-body">
        <PanelHost key={pane.name} name={pane.name} component={pane.component} />
      </div>
    </section>
  )
}

export function App() {
  const [current, setCurrent] = useState<ScreenId>(() => {
    const stored = localStorage.getItem(SCREEN_KEY)
    return SCREENS.some((item) => item.id === stored) ? (stored as ScreenId) : 'explore'
  })
  const [railCollapsed, setRailCollapsed] = useState(
    () => localStorage.getItem(RAIL_KEY) === 'collapsed',
  )
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [focus, setFocus] = useState<PaneFocus | null>(null)

  useEffect(() => {
    initActivity()
  }, [])

  useEffect(() => {
    localStorage.setItem(SCREEN_KEY, current)
  }, [current])
  useEffect(() => {
    localStorage.setItem(RAIL_KEY, railCollapsed ? 'collapsed' : 'open')
  }, [railCollapsed])

  const openRun = useCallback((runId: string) => {
    setLinked({ runId })
    window.location.hash = `run=${runId}`
    setCurrent(RESULTS_SCREEN)
  }, [])

  const showPane = useCallback((screenId: ScreenId, pane: string) => {
    setCurrent(screenId)
    setFocus((previous) => ({ pane, seq: (previous?.seq ?? 0) + 1 }))
  }, [])

  // Panels raise navigation intents ("show the lab with this command") rather than reaching
  // into the shell. Without this registration those intents are silently dropped, which is
  // exactly what happened when the docking container went away.
  useEffect(() => {
    registerNavigator({
      showRun: openRun,
      showStrategyLab: () => showPane('build', 'StrategyLab'),
      showProjects: () => showPane('operate', 'DevelopmentCenter'),
    })
  }, [openRun, showPane])

  // `#run=<id>` still deep-links to a run's report, now by switching screens rather than
  // spawning a floating panel.
  useEffect(() => {
    const apply = () => {
      const runId = runIdFromHash()
      if (runId) {
        setLinked({ runId })
        setCurrent(RESULTS_SCREEN)
      }
    }
    apply()
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [])

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

  const definition = screen(current)

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="mark">ALPHA</span>
          <span className="sub">WORKSTATION</span>
        </div>

        <nav className="screen-tabs" role="tablist" aria-label="Screens">
          {SCREENS.map((item) => (
            <button
              key={item.id}
              role="tab"
              aria-selected={item.id === current}
              className={`screen-tab${item.id === current ? ' active' : ''}`}
              title={item.purpose}
              onClick={() => setCurrent(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="spacer" />
        <ContextBar />
        <button className="kbd" onClick={() => setPaletteOpen(true)}>
          Search <kbd>⌘K</kbd>
        </button>
        <SettingsMenu />
        <StatusCluster />
      </header>

      <div className={`workspace${railCollapsed ? ' workspace--rail-collapsed' : ''}`}>
        <LibraryRail
          onOpenRun={openRun}
          collapsed={railCollapsed}
          onToggle={() => setRailCollapsed((value) => !value)}
        />
        <main className={`screen ${definition.layout}`} aria-label={definition.label}>
          {areasOf(definition).map(([areaName, panes]) => (
            // Keyed by screen as well as area: two screens both have a "main", and sharing a
            // key would carry one screen's selected tab index over to the other's panes.
            <Area
              key={`${definition.id}:${areaName}`}
              areaName={areaName}
              panes={panes}
              focus={focus}
            />
          ))}
        </main>
      </div>

      <Toasts onOpenRun={openRun} />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onOpenScreen={(id) => setCurrent(id)}
        onOpenRun={openRun}
      />
    </div>
  )
}
