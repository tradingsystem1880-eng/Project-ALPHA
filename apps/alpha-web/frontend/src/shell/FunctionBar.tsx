/** Function codes navigate existing screens; they never dispatch research or trading actions. */
import { useState } from 'react'
import type { Profile } from '../state/settings'
import { functionEntries, resolveFunction } from './terminalModel'
import type { PageId } from './workflowModel'

export function FunctionBar({ profile, onNavigate }: { profile: Profile; onNavigate: (page: PageId, pane: string) => void }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const entries = functionEntries(profile)
  return <form className="terminal-function" onSubmit={event => {
    event.preventDefault()
    const entry = resolveFunction(value, profile)
    if (!entry) { setError('Choose a listed function for this market.'); return }
    onNavigate(entry.page, entry.pane)
    setValue('')
    setError(null)
  }}>
    <label htmlFor="terminal-function-input">Function</label>
    <input id="terminal-function-input" className="field" aria-label="Terminal function" list="terminal-functions" placeholder="CHART, SCAN, HELP…  F2" autoComplete="off" value={value} onChange={event => { setValue(event.target.value); setError(null) }} onKeyDown={event => { if (event.key === 'Escape') { setValue(''); setError(null) } }} />
    <datalist id="terminal-functions">{entries.map(entry => <option key={entry.code} value={entry.code}>{entry.section} · {entry.title}</option>)}</datalist>
    <button className="btn" type="submit">Go</button>
    {error ? <span role="alert">{error}</span> : null}
  </form>
}
