// View settings popover: profile, density, explanations. Opened from the toolbar gear.

import { useState } from 'react'

import { setSettings, useSettings } from '../state/settings'

export function SettingsMenu() {
  const { density, explain, profile } = useSettings()
  const [open, setOpen] = useState(false)
  return (
    <div className="settings-menu">
      <button
        type="button"
        className="btn settings-toggle"
        aria-expanded={open}
        aria-label="View settings"
        onClick={() => setOpen((v) => !v)}
        title="View settings"
      >
        ⚙
      </button>
      {open ? (
        <div className="settings-pop" role="dialog" aria-label="View settings">
          <button
            type="button"
            className="settings-row"
            onClick={() => setSettings({ profile: profile === 'crypto' ? 'equities' : 'crypto' })}
          >
            <span>Profile</span>
            <span className="mono">{profile}</span>
          </button>
          <button
            type="button"
            className="settings-row"
            onClick={() => setSettings({ density: density === 'compact' ? 'comfortable' : 'compact' })}
          >
            <span>Density</span>
            <span className="mono">{density}</span>
          </button>
          <button
            type="button"
            className="settings-row"
            onClick={() => setSettings({ explain: explain === 'terse' ? 'narrative' : 'terse' })}
          >
            <span>Explanations</span>
            <span className="mono">{explain}</span>
          </button>
        </div>
      ) : null}
    </div>
  )
}
