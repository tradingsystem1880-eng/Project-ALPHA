import {
  DockviewReact,
  themeAbyss,
  type DockviewApi,
  type DockviewReadyEvent,
} from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'
import { useCallback, useEffect, useRef, useState } from 'react'

import { CommandPalette } from './components/CommandPalette'
import { useLinked } from './context/linked'
import { PANELS } from './panels/registry'

export function App() {
  const dockRef = useRef<DockviewApi | null>(null)
  const seq = useRef(0)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const linked = useLinked()

  const onReady = useCallback((event: DockviewReadyEvent) => {
    dockRef.current = event.api
    const saved = localStorage.getItem('alpha.layout')
    let restored = false
    if (saved) {
      try {
        event.api.fromJSON(JSON.parse(saved))
        restored = true
      } catch {
        restored = false
      }
    }
    if (!restored) {
      event.api.addPanel({ id: 'RunBrowser-0', component: 'RunBrowser', title: 'Run Browser' })
    }
    event.api.onDidLayoutChange(() => {
      try {
        localStorage.setItem('alpha.layout', JSON.stringify(event.api.toJSON()))
      } catch {
        /* ignore storage quota / serialization errors */
      }
    })
  }, [])

  const openPanel = useCallback((component: string, title: string) => {
    const dv = dockRef.current
    if (!dv) return
    // singleton panels share the `${Component}-${n}` id scheme (incl. the default RunBrowser-0)
    const existing = dv.panels.find((p) => p.id.startsWith(`${component}-`))
    if (existing) {
      existing.api.setActive()
      return
    }
    seq.current += 1
    dv.addPanel({ id: `${component}-${seq.current}`, component, title })
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      } else if (e.key === 'Escape') {
        setPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="mark">ALPHA</span>
          <span className="sub">WORKSTATION</span>
        </div>
        <div className="linked">
          <button onClick={() => setPaletteOpen(true)} title="Active symbol">
            <span className="tag">SYM</span>
            <span className="sym">{linked.symbol ?? '—'}</span>
          </button>
          <button className="range" title="As-of window">
            <span className="tag">ASOF</span>
            {`${linked.start ?? '—'} → ${linked.end ?? 'latest'}`}
          </button>
        </div>
        <div className="spacer" />
        <button className="kbd" onClick={() => setPaletteOpen(true)}>
          Search <kbd>⌘K</kbd>
        </button>
        <div className="status">
          <span className="dot" /> local · loopback
        </div>
      </header>
      <div className="dock">
        <DockviewReact components={PANELS} onReady={onReady} theme={themeAbyss} />
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onOpenPanel={openPanel}
      />
    </div>
  )
}
