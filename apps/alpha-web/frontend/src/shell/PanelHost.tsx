/**
 * Renders a panel outside any docking library.
 *
 * A panel's only real dependency on its host is a small parameter bag it can read, write
 * and subscribe to — that is what `PanelHandleProps` declares. This provides one backed by
 * React state, so the same components work in a fixed screen as they did in a dock.
 */

import { useEffect, useMemo, useRef, useState, type FunctionComponent } from 'react'

import type { PanelHandleProps, PanelParameterHandle } from '../context/panelHandle'
import { ErrorBoundary } from '../components/ErrorBoundary'

type Listener = (parameters: unknown) => void

function useParameterHandle(initial: Record<string, unknown>): {
  api: PanelParameterHandle
  params: Record<string, unknown>
} {
  const [params, setParams] = useState(initial)
  const listeners = useRef(new Set<Listener>())
  const current = useRef(params)
  current.current = params

  // A screen can change a panel's inputs (a different run, a different symbol) without
  // remounting it, so incoming parameters have to flow through the same channel a panel's
  // own writes use.
  //
  // Notifying listeners happens here rather than inside the state updater: React may call an
  // updater twice, and a subscriber must not be told about a change twice.
  useEffect(() => {
    const previous = current.current
    const merged = { ...previous, ...initial }
    const same =
      Object.keys(merged).length === Object.keys(previous).length &&
      Object.entries(merged).every(([key, value]) => previous[key] === value)
    if (same) return
    current.current = merged
    setParams(merged)
    for (const listener of listeners.current) listener(merged)
  }, [initial])

  const api = useMemo<PanelParameterHandle>(
    () => ({
      getParameters: () => current.current,
      updateParameters: (next) => {
        setParams(next)
        for (const listener of listeners.current) listener(next)
      },
      onDidParametersChange: (listener) => {
        listeners.current.add(listener)
        return {
          dispose: () => {
            listeners.current.delete(listener)
          },
        }
      },
    }),
    [],
  )
  return { api, params }
}

export function PanelHost({
  name,
  component: Panel,
  params: incoming,
}: {
  name: string
  component: FunctionComponent<PanelHandleProps>
  params?: Record<string, unknown>
}) {
  const initial = useMemo(() => incoming ?? {}, [incoming])
  const { api, params } = useParameterHandle(initial)
  return (
    <ErrorBoundary panel={name}>
      <Panel api={api} params={params} />
    </ErrorBoundary>
  )
}
