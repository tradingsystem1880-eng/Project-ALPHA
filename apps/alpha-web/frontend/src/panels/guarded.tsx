import type { IDockviewPanelProps } from 'dockview-react'
import type { FunctionComponent } from 'react'

import { ErrorBoundary } from '../components/ErrorBoundary'

export function guarded(
  name: string,
  Panel: FunctionComponent<IDockviewPanelProps>,
): FunctionComponent<IDockviewPanelProps> {
  const Guarded: FunctionComponent<IDockviewPanelProps> = (props) => (
    <ErrorBoundary panel={name}>
      <Panel {...props} />
    </ErrorBoundary>
  )
  Guarded.displayName = `Guarded(${name})`
  return Guarded
}
