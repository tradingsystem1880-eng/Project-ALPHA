// One docked window's frame (artboard 1-Terminal): a title row with the pin and close glyphs, and
// the dock's body. Pin is disabled — docks are always pinned, there are no floating windows — and
// close hides the dock until View › Docks shows it again. The bottom tabs belong to each dock's
// own panel because only it knows what they switch.

import type { ReactNode } from 'react'

import { dockOf } from './documents'
import { Icon } from './icons'
import type { DockId } from './profiles'

export function DockFrame({
  id,
  title,
  onClose,
  children,
}: {
  id: DockId
  /** Displayed title; the accessible name is always the registry title. */
  title?: ReactNode
  onClose: () => void
  children: ReactNode
}) {
  const name = dockOf(id).title
  return (
    <section className="dock-frame" aria-label={name}>
      <div className="dock-head">
        <h2 className="dock-title">{title ?? name}</h2>
        <span className="spacer" />
        <button
          type="button"
          className="dock-glyph"
          disabled
          aria-label={`Pin ${name}`}
          title="Docks are always pinned — this terminal has no floating windows"
        >
          <Icon name="pin" size={12} />
        </button>
        <button
          type="button"
          className="dock-glyph"
          aria-label={`Close ${name}`}
          title={`Hide ${name} (View › Docks shows it again)`}
          onClick={onClose}
        >
          <Icon name="close" size={12} />
        </button>
      </div>
      <div className="dock-frame-body">{children}</div>
    </section>
  )
}
