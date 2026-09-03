// Toolbar (spec 2026-09-01 §4.2 item 3): timeframes (only what the data house serves is enabled),
// Data / Research / Run / Report, the Profile combo, the symbol · venue · timeframe combo, search,
// the one status chip and the Governance button. Every button opens a real surface; there is no
// Stop because the terminal owns no running process to stop (jobs cancel from the Jobs table).

import { useEffect } from 'react'

import { useLinked } from '../context/linked'
import { useLinkedProjectGate } from '../panels/useLinkedProjectGate'
import { useSelectedRunWatermark } from '../panels/useSelectedRunWatermark'
import { setSettings, useSettings, workspaceModeFor, type Profile } from '../state/settings'
import { useActivityField } from '../state/activity'
import { ContextBar } from './ContextBar'
import { PROFILES } from './profiles'
import { SettingsMenu } from './SettingsMenu'
import { statusChip } from './statusModel'
import { timeframeButtons } from './toolbarModel'

interface Props {
  onData: () => void
  onResearch: () => void
  onRun: () => void
  onReport: () => void
  onSearch: () => void
  onGovernance: () => void
}

function StatusCluster({ onOpenGovernance }: { onOpenGovernance: () => void }) {
  const connection = useActivityField('connection')
  const runningJobs = useActivityField('runningJobs')
  const gate = useLinkedProjectGate()
  const watermark = useSelectedRunWatermark()
  const chip = statusChip({ watermark, gateLock: gate.lock })
  const dotClass = connection === 'live' ? '' : connection === 'connecting' ? 'busy' : 'down'
  return (
    <div className="status" title={`activity stream: ${connection}`}>
      <span className={`dot ${dotClass}`} />
      {runningJobs > 0 ? <span className="chip kind">{runningJobs} running</span> : null}
      <button
        type="button"
        className={`chip ${chip.tone} status-chip`}
        title={chip.title}
        onClick={onOpenGovernance}
      >
        {chip.text}
      </button>
    </div>
  )
}

function WorkspaceModeControl() {
  const linked = useLinked()
  const settings = useSettings()
  const mode = workspaceModeFor(settings, linked.projectId)

  useEffect(() => {
    document.documentElement.setAttribute('data-workspace-mode', mode)
  }, [mode])

  function choose(next: 'guided' | 'advanced'): void {
    if (!linked.projectId || next === 'guided') {
      if (linked.projectId) {
        const projectModes = { ...settings.projectModes }
        delete projectModes[linked.projectId]
        setSettings({ projectModes })
      }
      return
    }
    setSettings({ projectModes: { ...settings.projectModes, [linked.projectId]: next } })
  }

  return (
    <div className="workspace-mode" role="group" aria-label="Workspace detail mode">
      <button
        type="button"
        className={`btn${mode === 'guided' ? ' active' : ''}`}
        aria-pressed={mode === 'guided'}
        onClick={() => choose('guided')}
        title="One next action with plain-language evidence and recovery"
      >
        Guided
      </button>
      <button
        type="button"
        className={`btn${mode === 'advanced' ? ' active' : ''}`}
        aria-pressed={mode === 'advanced'}
        disabled={!linked.projectId}
        onClick={() => choose('advanced')}
        title="Show immutable contracts, hashes, receipts, and command previews; authority is unchanged"
      >
        Advanced
      </button>
    </div>
  )
}

export function Toolbar({ onData, onResearch, onRun, onReport, onSearch, onGovernance }: Props) {
  const { profile } = useSettings()
  const linked = useLinked()
  return (
    <div className="toolbar" role="toolbar" aria-label="Terminal toolbar">
      <div className="toolbar-group" role="group" aria-label="Timeframe">
        {timeframeButtons(['D1']).map((item) => (
          <button
            key={item.label}
            type="button"
            className={`btn tf${item.label === 'D1' ? ' active' : ''}`}
            aria-pressed={item.label === 'D1'}
            disabled={item.disabled}
            title={item.reason ?? 'daily bars'}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="toolbar-group" role="group" aria-label="Actions">
        <button type="button" className="btn" onClick={onData} title="Show or hide the Data Manager dock">
          Data
        </button>
        <button type="button" className="btn" onClick={onResearch} title="Open the research case document">
          Research
        </button>
        <button type="button" className="btn" onClick={onRun} title="Open Strategy Development to launch a run">
          Run
        </button>
        <button
          type="button"
          className="btn"
          onClick={onReport}
          disabled={!linked.runId}
          title={linked.runId ? 'Open the selected run’s performance report' : 'Select a run first'}
        >
          Report
        </button>
      </div>
      <label className="toolbar-profile">
        <span className="sr-only">Profile</span>
        <select
          className="field"
          aria-label="Profile"
          value={profile}
          onChange={(event) => setSettings({ profile: event.target.value as Profile })}
        >
          {Object.values(PROFILES).map((manifest) => (
            <option key={manifest.id} value={manifest.id}>
              {manifest.label}
            </option>
          ))}
        </select>
      </label>
      <ContextBar />
      <div className="spacer" />
      <WorkspaceModeControl />
      <button type="button" className="btn" onClick={onSearch} aria-label="Search commands" title="Search commands, runs and symbols (⌘K)">
        <kbd>⌘K</kbd>
      </button>
      <StatusCluster onOpenGovernance={onGovernance} />
      <button
        type="button"
        className="btn"
        aria-label="Governance"
        title="Authority, research gates, overrides, providers, storage and the glossary"
        onClick={onGovernance}
      >
        ⚖<span className="governance-label">Governance</span>
      </button>
      <SettingsMenu />
    </div>
  )
}
