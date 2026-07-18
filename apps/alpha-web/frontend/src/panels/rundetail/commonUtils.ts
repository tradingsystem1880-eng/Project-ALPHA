import { useEffect, useState } from 'react'

export { asNum, asStr } from '../../util/format'

export type Dict = Record<string, unknown>
export const asObj = (v: unknown): Dict | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Dict) : null

export function useProjection<T>(enabled: boolean, runId: string, fetcher: () => Promise<T>): T | null {
  const [value, setValue] = useState<T | null>(null)
  useEffect(() => {
    if (!enabled) return
    let live = true
    fetcher()
      .then((v) => live && setValue(v))
      .catch(() => {})
    return () => {
      live = false
    }
    // fetcher identity is per-render; the fetch is keyed by run + flag only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, runId])
  return value
}
