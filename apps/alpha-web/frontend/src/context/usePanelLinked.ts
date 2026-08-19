import { useCallback, useMemo } from 'react'

import type { PanelHandleProps } from './panelHandle'
import type { PanelBindingMode, PanelLinkBinding } from './panelLinkModel'
import {
  linkedGroup,
  setLinked,
  useLinked,
  type LinkedState,
  type LinkGroup,
} from './linked'

export interface PanelLinkedController {
  linked: LinkedState
  binding: PanelLinkBinding
  setLinked: (patch: Partial<LinkedState>) => void
  setBinding: (mode: PanelBindingMode, group?: LinkGroup) => void
}

/**
 * Fixed Workstation screens have one canonical workspace context. Legacy panel bindings remain
 * readable in saved documents, but mounted panels no longer fork, pin, or locally override the
 * selected project. This is the seam every panel uses, so header, backlog, evidence, development,
 * and restored workspaces now agree immediately.
 */
export function usePanelLinked(_props: PanelHandleProps): PanelLinkedController {
  const linked = useLinked()
  const binding = useMemo<PanelLinkBinding>(
    () => ({ mode: 'follow-active', group: linked.linkGroup, local: linkedGroup(linked) }),
    [linked],
  )
  const update = useCallback((patch: Partial<LinkedState>) => setLinked(patch), [])
  const keepCanonical = useCallback((_mode: PanelBindingMode, _group?: LinkGroup) => undefined, [])
  return useMemo(
    () => ({ linked, binding, setLinked: update, setBinding: keepCanonical }),
    [binding, keepCanonical, linked, update],
  )
}
