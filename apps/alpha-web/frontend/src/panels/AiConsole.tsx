// AI Console — run any `alpha` command and watch it stream. Natural-language orchestration lives in
// the alpha MCP server (paired with a Claude client); this is the direct command surface.

import { useState } from 'react'

import { api } from '../api/client'
import { JobConsole } from '../components/JobConsole'

export function AiConsole() {
  const [args, setArgs] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)

  function run(): void {
    const a = args.trim()
    if (!a) return
    // empty command → the backend runs the raw argv (a free-form console, no run linking)
    api.launch('', a).then((r) => setJobId(r.job_id))
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">AI Console</span>
      </div>
      <div className="panel-body panel-pad ai">
        <div className="ai-note">
          Full natural-language control lives in the <strong>alpha MCP server</strong> — pair it
          with a Claude client (<code>uv run alpha-mcp</code>; the repo ships <code>.mcp.json</code>
          ). Here you can run any <code>alpha</code> command directly and watch it stream live.
        </div>
        <div className="ai-input">
          <span className="ai-prompt mono">alpha</span>
          <input
            className="field"
            value={args}
            onChange={(e) => setArgs(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder="validate SPY --strategy ma_crossover"
            spellCheck={false}
          />
          <button className="btn primary" onClick={run}>
            Run
          </button>
        </div>
        {jobId ? <JobConsole jobId={jobId} /> : null}
      </div>
    </div>
  )
}
