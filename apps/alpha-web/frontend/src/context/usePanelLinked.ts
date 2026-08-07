import { useCallback, useEffect, useMemo, useState } from 'react'

import type { PanelHandleProps } from './panelHandle'

import {
  migratePanelBinding,
  patchLocalPanelBinding,
  resolvePanelLinked,
  type PanelBindingMode,
  type PanelLinkBinding,
} from './panelLinkModel'
import {
  getLinked,
  linkedGroup,
  setGroupLinked,
  useLinkedWorkspace,
  type LinkedState,
  type LinkGroup,
} from './linked'

export interface PanelLinkedController {
  linked: LinkedState
  binding: PanelLinkBinding
  setLinked: (patch: Partial<LinkedState>) => void
  setBinding: (mode: PanelBindingMode, group?: LinkGroup) => void
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export function usePanelLinked(props: PanelHandleProps): PanelLinkedController {
  const workspace = useLinkedWorkspace()
  const initialParams = record(props.params)
  const [binding, setBindingState] = useState(() =>
    migratePanelBinding(initialParams.linkBinding, getLinked(), initialParams.runId),
  )

  useEffect(() => {
    const disposable = props.api.onDidParametersChange((parameters) => {
      const next = record(parameters)
      setBindingState(migratePanelBinding(next.linkBinding, getLinked(), next.runId))
    })
    return () => disposable.dispose()
  }, [props.api])

  const linked = useMemo(() => resolvePanelLinked(workspace, binding), [binding, workspace])

  const persist = useCallback(
    (next: PanelLinkBinding) => {
      setBindingState(next)
      props.api.updateParameters({
        ...props.api.getParameters(),
        linkBinding: next,
      })
    },
    [props.api],
  )

  const updateLinked = useCallback(
    (patch: Partial<LinkedState>) => {
      if (binding.mode === 'follow-active') {
        setGroupLinked(workspace.linkGroup, patch)
      } else if (binding.mode === 'pinned-to-group') {
        setGroupLinked(binding.group, patch)
      } else {
        persist(patchLocalPanelBinding(binding, patch))
      }
    },
    [binding, persist, workspace.linkGroup],
  )

  const updateBinding = useCallback(
    (nextMode: PanelBindingMode, requestedGroup?: LinkGroup) => {
      const nextGroup = requestedGroup ?? linked.linkGroup
      persist({
        mode: nextMode,
        group: nextMode === 'follow-active' ? workspace.linkGroup : nextGroup,
        local: nextMode === 'unlinked-local' ? linkedGroup(linked) : binding.local,
      })
    },
    [binding.local, linked, persist, workspace.linkGroup],
  )

  return useMemo(
    () => ({ linked, binding, setLinked: updateLinked, setBinding: updateBinding }),
    [binding, linked, updateBinding, updateLinked],
  )
}
