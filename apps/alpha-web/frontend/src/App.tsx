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
    event.api.addPanel({ id: 'run-browser', component: 'RunBrowser', title: 'Run Browser' })
  }, [])

  const openPanel = useCallback((component: string, title: string) => {
    const dv = dockRef.current
    if (!dv) return
    const existing = dv.panels.find((p) => p.id.startsWith(component))
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
