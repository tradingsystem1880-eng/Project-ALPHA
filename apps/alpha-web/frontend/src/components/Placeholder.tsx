// The shared empty/loading/error placeholder used across panels.

import type { ReactNode } from 'react'

export function Placeholder({ big, children }: { big?: string; children?: ReactNode }) {
  return (
    <div className="placeholder">
      {big ? <div className="big">{big}</div> : null}
      {children}
    </div>
  )
}
