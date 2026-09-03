// Inline SVG glyphs for the terminal chrome (artboard 1-Terminal): no emoji, no icon font, every
// glyph inherits `currentColor` so a disabled or selected button recolours it for free. Buttons
// carry their own `aria-label`; the glyph itself is decorative.

import type { ReactNode } from 'react'

export type IconName =
  | 'bars'
  | 'candles'
  | 'line'
  | 'crosshair'
  | 'grid'
  | 'zoom-in'
  | 'zoom-out'
  | 'data'
  | 'research'
  | 'run'
  | 'stop'
  | 'report'
  | 'lock'
  | 'shield'
  | 'pin'
  | 'close'
  | 'minimise'
  | 'maximise'
  | 'restore'
  | 'folder'
  | 'doc'
  | 'search'
  | 'plus'

const GLYPHS: Record<IconName, ReactNode> = {
  bars: <path d="M3 5v6M1.5 7h1.5M3 9h1.5M8 3v7M6.5 5h1.5M8 8h1.5M13 6v7M11.5 8h1.5M13 11h1.5" />,
  candles: (
    <>
      <path d="M4.5 1.5v3M4.5 11v3.5M11.5 2.5v2M11.5 10.5v3" />
      <rect x="2.5" y="4.5" width="4" height="6.5" fill="currentColor" />
      <rect x="9.5" y="4.5" width="4" height="6" />
    </>
  ),
  line: <path d="M1.5 12.5l4-5.5 3 3 6-7.5" />,
  crosshair: (
    <>
      <path d="M8 1.5v13M1.5 8h13" />
      <circle cx="8" cy="8" r="3" />
    </>
  ),
  grid: <path d="M1.5 5.5h13M1.5 10.5h13M5.5 1.5v13M10.5 1.5v13" />,
  'zoom-in': (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5l4 4M7 5v4M5 7h4" />
    </>
  ),
  'zoom-out': (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5l4 4M5 7h4" />
    </>
  ),
  data: (
    <>
      <ellipse cx="8" cy="4" rx="5.5" ry="2.2" />
      <path d="M2.5 4v8c0 1.2 2.5 2.2 5.5 2.2s5.5-1 5.5-2.2V4M2.5 8c0 1.2 2.5 2.2 5.5 2.2s5.5-1 5.5-2.2" />
    </>
  ),
  research: <path d="M6 1.5h4M7 1.5v5l-4.2 7a1 1 0 0 0 .9 1.5h8.6a1 1 0 0 0 .9-1.5L9 6.5v-5" />,
  run: <path d="M4 2.5v11l9-5.5z" fill="currentColor" />,
  stop: <rect x="3" y="3" width="10" height="10" fill="currentColor" />,
  report: <path d="M3 1.5h7l3 3v10H3zM10 1.5v3h3M5.5 8h5M5.5 11h5" />,
  lock: (
    <>
      <rect x="3" y="7" width="10" height="7" />
      <path d="M5 7V5a3 3 0 0 1 6 0v2" />
    </>
  ),
  shield: <path d="M8 1.5l5.5 2v4.5c0 3.3-2.3 5.7-5.5 6.5C4.8 13.7 2.5 11.3 2.5 8V3.5z" />,
  pin: <path d="M10 1.5l4.5 4.5-1.5.5-2 2v3l-2-1-3.5 3.5-1.5-1.5L7.5 9.5l-1-2h3l2-2z" />,
  close: <path d="M3 3l10 10M13 3L3 13" />,
  minimise: <path d="M3 12.5h10" />,
  maximise: <rect x="3" y="3" width="10" height="10" />,
  restore: <path d="M5.5 5.5V3h7.5v7.5H10.5M3 5.5h7.5V13H3z" />,
  folder: <path d="M1.5 3.5h5l1.5 2h6.5v8h-13z" />,
  doc: <path d="M4 1.5h6l3 3v10H4zM10 1.5v3h3" />,
  search: (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5l4 4" />
    </>
  ),
  plus: <path d="M8 3v10M3 8h10" />,
}

export function Icon({ name, size = 14 }: { name: IconName; size?: number }) {
  return (
    <svg
      className={`icon icon-${name}`}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {GLYPHS[name]}
    </svg>
  )
}
