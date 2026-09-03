// The metric glossary panel: every statistic the workstation shows, searchable, defined once.

import { useMemo, useState } from 'react'

import { useSettings } from '../state/settings'
import { glossaryEntries } from './governanceModel'

export function Glossary() {
  const { profile } = useSettings()
  const [query, setQuery] = useState('')
  const entries = useMemo(() => {
    const q = query.trim().toLowerCase()
    const all = glossaryEntries(profile)
    if (!q) return all
    return all.filter(
      ([key, e]) =>
        key.includes(q) || e.name.toLowerCase().includes(q) || e.long.toLowerCase().includes(q),
    )
  }, [profile, query])

  return (
    <div className="panel-pad glossary">
      <div className="field-row">
        <input
          className="field"
          placeholder="Filter terms…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="muted">{entries.length} terms</span>
      </div>
      <div className="glossary-list" tabIndex={0} aria-label="Metric definitions">
        {entries.map(([key, e]) => (
          <section key={key} className="glossary-entry">
            <h3>{e.name}</h3>
            <p className="glossary-short">{e.short}</p>
            <p className="glossary-long">{e.long}</p>
          </section>
        ))}
      </div>
    </div>
  )
}
