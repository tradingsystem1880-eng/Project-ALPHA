// One shared one-second UTC clock for the chrome (Market Watch header, status bar).

import { useEffect, useState } from 'react'

export function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

/** `HH:MM:SS` in UTC. */
export function clockText(now: number): string {
  return new Date(now).toISOString().slice(11, 19)
}
