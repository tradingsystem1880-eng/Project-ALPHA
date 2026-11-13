// Test-only mount of the actual two risk consumers and API client; no metric substitute.
import React from 'react'
import { createRoot } from 'react-dom/client'

import '../src/index.css'
import { setLinked } from '../src/context/linked'
import { RiskMonitor } from '../src/panels/RiskMonitor'
import { Risk } from '../src/panels/rundetail/Risk'

const query = new URLSearchParams(location.search)
let runId = query.get('run') ?? ''
const monitor = query.get('view') === 'monitor'
const root = createRoot(document.getElementById('risk-root')!)
const api = {
  getParameters: () => ({}), updateParameters: () => undefined,
  onDidParametersChange: () => ({ dispose: () => undefined }),
}
function render() {
  setLinked({ runId })
  root.render(monitor ? <RiskMonitor api={api} /> : <Risk manifest={{}} runId={runId} />)
}
Object.assign(window, { c04SetRun: (value: string) => { runId = value; render() } })
render()
