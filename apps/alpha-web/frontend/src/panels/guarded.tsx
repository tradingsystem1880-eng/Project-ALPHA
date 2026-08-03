import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useState, type FunctionComponent } from 'react'

import { ErrorBoundary } from '../components/ErrorBoundary'

export function guarded(
  name: string,
  Panel: FunctionComponent<IDockviewPanelProps>,
): FunctionComponent<IDockviewPanelProps> {
  const Guarded: FunctionComponent<IDockviewPanelProps> = (props) => {
    // Dockview keeps hidden tab portals mounted. Rendering their panel bodies would leave network
    // effects and pollers running behind the selected tab. `isVisible` means selected within the
    // panel's own group; `isActive` would incorrectly pause visible panes in unfocused groups.
    const [visible, setVisible] = useState(props.api.isVisible)
    useEffect(() => {
      setVisible(props.api.isVisible)
      const disposable = props.api.onDidVisibilityChange(({ isVisible }) => setVisible(isVisible))
      return () => disposable.dispose()
    }, [props.api])

    if (!visible) return null
    return (
      <ErrorBoundary panel={name}>
        <Panel {...props} />
      </ErrorBoundary>
    )
  }
  Guarded.displayName = `Guarded(${name})`
  return Guarded
}
