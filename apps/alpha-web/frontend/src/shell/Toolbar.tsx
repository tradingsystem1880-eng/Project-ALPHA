// Toolbar (spec 2026-09-01 §4.2 item 3; artboard 1-Terminal): chart-type, crosshair, grid and
// zoom glyphs that drive the price chart through `chartControls`; timeframes (only what the data
// house serves is enabled); Data / Research / Run / Stop / Report glyphs; the Profile combo; the
// symbol · venue · timeframe combo; the `Search Ctrl+K` field; the lock `Paper only` status chip
// and the shield Governance button. Every enabled button opens a real surface; Stop is disabled
// because the terminal owns no running process (jobs cancel from the Jobs table).

import { useEffect } from 'react'

import { setChartControls, useChartControls, zoomStep, type ChartType } from '../context/chartControls'
import { useLinked } from '../context/linked'
import { useLinkedProjectGate } from '../panels/useLinkedProjectGate'
import { useSelectedRunWatermark } from '../panels/useSelectedRunWatermark'
import { setSettings, useSettings, workspaceModeFor, type Profile } from '../state/settings'
import { ContextBar } from './ContextBar'
import { Icon, type IconName } from './icons'
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

const CHART_TYPES: { id: ChartType; icon: IconName; label: string }[] = [
  { id: 'bars', icon: 'bars', label: 'OHLC bars' },
  { id: 'candles', icon: 'candles', label: 'Candlesticks' },
  { id: 'line', icon: 'line', label: 'Line (closes)' },
]

function ChartControls() {
  const controls = useChartControls()
  return (
    <div className="toolbar-group" role="group" aria-label="Chart">
      {CHART_TYPES.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`btn glyph${controls.type === item.id ? ' active' : ''}`}
          aria-label={item.label}
          aria-pressed={controls.type === item.id}
          title={item.label}
          onClick={() => setChartControls({ type: item.id })}
        >
          <Icon name={item.icon} />
        </button>
      ))}
      <span className="toolbar-sep" />
      <button
        type="button"
        className={`btn glyph${controls.crosshair ? ' active' : ''}`}
        aria-label="Crosshair"
        aria-pressed={controls.crosshair}
        title="Crosshair"
        onClick={() => setChartControls({ crosshair: !controls.crosshair })}
      >
        <Icon name="crosshair" />
      </button>
      <button
        type="button"
        className={`btn glyph${controls.grid ? ' active' : ''}`}
        aria-label="Grid"
        aria-pressed={controls.grid}
        title="Grid"
        onClick={() => setChartControls({ grid: !controls.grid })}
      >
        <Icon name="grid" />
      </button>
      <button
        type="button"
        className="btn glyph"
        aria-label="Zoom in"
        title="Zoom in"
        onClick={() => setChartControls({ zoom: zoomStep(controls.zoom, 1) })}
      >
        <Icon name="zoom-in" />
      </button>
      <button
        type="button"
        className="btn glyph"
        aria-label="Zoom out"
        title="Zoom out"
        onClick={() => setChartControls({ zoom: zoomStep(controls.zoom, -1) })}
      >
        <Icon name="zoom-out" />
      </button>
    </div>
  )
}

function StatusChip({ onOpenGovernance }: { onOpenGovernance: () => void }) {
  const gate = useLinkedProjectGate()
  const watermark = useSelectedRunWatermark()
  const chip = statusChip({ watermark, gateLock: gate.lock })
  return (
    <button
      type="button"
      className={`chip ${chip.tone} status-chip`}
      title={chip.title}
      onClick={onOpenGovernance}
    >
      <Icon name="lock" size={12} />
      {chip.text}
    </button>
  )
}

/** Mirrors the detail mode onto the document so `.advanced-only` rules can read it. */
function WorkspaceModeAttribute() {
  const linked = useLinked()
  const settings = useSettings()
  const mode = workspaceModeFor(settings, linked.projectId)
  useEffect(() => {
    document.documentElement.setAttribute('data-workspace-mode', mode)
  }, [mode])
  return null
}

export function Toolbar({ onData, onResearch, onRun, onReport, onSearch, onGovernance }: Props) {
  const { profile } = useSettings()
  const linked = useLinked()
  return (
    <div className="toolbar" role="toolbar" aria-label="Terminal toolbar">
      <WorkspaceModeAttribute />
      <ChartControls />
      <span className="toolbar-sep" />
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
      <span className="toolbar-sep" />
      <div className="toolbar-group" role="group" aria-label="Actions">
        <button type="button" className="btn glyph" onClick={onData} aria-label="Data" title="Data — show or hide the Data Manager dock">
          <Icon name="data" />
        </button>
        <button type="button" className="btn glyph" onClick={onResearch} aria-label="Research" title="Research — open the research case document">
          <Icon name="research" />
        </button>
        <button type="button" className="btn glyph" onClick={onRun} aria-label="Run" title="Run — open Strategy Development to launch a run">
          <Icon name="run" />
        </button>
        <button type="button" className="btn glyph" disabled aria-label="Stop" title="Stop — the terminal owns no running process; cancel a job from the Jobs table">
          <Icon name="stop" />
        </button>
        <button
          type="button"
          className="btn glyph"
          onClick={onReport}
          disabled={!linked.runId}
          aria-label="Report"
          title={linked.runId ? 'Report — open the selected run’s performance report' : 'Report — select a run first'}
        >
          <Icon name="report" />
        </button>
      </div>
      <span className="toolbar-sep" />
      <label className="toolbar-profile">
        <span className="toolbar-label">Profile</span>
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
      <div className="toolbar-search">
        <Icon name="search" size={12} />
        <input
          className="toolbar-search-field"
          type="text"
          readOnly
          value=""
          placeholder="Search  Ctrl+K"
          aria-label="Search commands"
          title="Search commands, runs and symbols (Ctrl+K / ⌘K)"
          onClick={onSearch}
          onKeyDown={(event) => event.key === 'Enter' && onSearch()}
        />
      </div>
      <StatusChip onOpenGovernance={onGovernance} />
      <button
        type="button"
        className="btn governance-btn"
        aria-label="Governance"
        title="Authority, research gates, overrides, providers, storage and the glossary"
        onClick={onGovernance}
      >
        <Icon name="shield" />
        <span className="governance-label">Governance</span>
      </button>
      <SettingsMenu />
    </div>
  )
}
