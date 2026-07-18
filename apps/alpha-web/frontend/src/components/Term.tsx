// A glossary-linked term: dotted underline, rich definition on hover/focus.
// Definitions come from explain/glossary.ts; unknown keys render as plain text.

import { useCallback, useRef, useState, type ReactNode } from 'react'

import { glossaryEntry } from '../explain/glossary'

interface Tip {
  x: number
  y: number
}

export function Term({ k, children }: { k: string; children: ReactNode }) {
  const entry = glossaryEntry(k)
  const [tip, setTip] = useState<Tip | null>(null)
  const ref = useRef<HTMLSpanElement>(null)

  const show = useCallback(() => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    // clamp near the right edge so the 340px tip stays on screen
    const x = Math.min(rect.left, window.innerWidth - 356)
    const y = rect.bottom + 6
    setTip({ x, y })
  }, [])
  const hide = useCallback(() => setTip(null), [])

  if (!entry) return <>{children}</>
  return (
    <span
      ref={ref}
      className="term"
      tabIndex={0}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {tip && (
        <span className="term-tip" style={{ left: tip.x, top: tip.y }}>
          <span className="term-name">{entry.name}</span>
          {entry.short}
        </span>
      )}
    </span>
  )
}
