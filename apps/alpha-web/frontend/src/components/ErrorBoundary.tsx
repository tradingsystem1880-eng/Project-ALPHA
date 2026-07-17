// Per-panel error boundary. Dockview mounts each panel in its own React root, so a single
// top-level boundary catches nothing — the registry wraps every panel with this instead.
// Fail loud (message + stack) but stay contained: one broken panel never blanks the desk.

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  panel: string
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[panel:${this.props.panel}]`, error, info.componentStack)
  }

  render(): ReactNode {
    const { error } = this.state
    if (error === null) return this.props.children
    return (
      <div className="panel-error">
        <span className="eyebrow">panel crashed — {this.props.panel}</span>
        <span>{error.message}</span>
        <button className="btn" onClick={() => this.setState({ error: null })}>
          ↻ Retry
        </button>
      </div>
    )
  }
}
