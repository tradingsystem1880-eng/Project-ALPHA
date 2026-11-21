import './IdeaWorkspace.css'
// Ideas: the whole story of one idea on one page: the card, the rule built from it, the data, every
// test, the charts and checks of the selected run, the tools run, the paper follow and the open
// points. A list of cards first (newest first), then one page per card. Read only: the server relays
// `alpha idea list|file` (`GET /api/ideas`, `GET /api/ideas/{card}`); this file lays the answer out.

import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { IdeaFile, IdeaList } from '../../api/types'
import { useAreaVersion } from '../../state/activity'
import { RunCharts, RunChecks } from './IdeaRunPanels'
import {
  DataStep, FollowStep, HypothesisStep, IdeaStep, OpenStep, RdAgentStep, RuleStep, Step, TestsStep, ToolsStep,
} from './IdeaSections'
import { defaultRun, ideaSteps, newestFirst, runsOf, shortDay, STATE_WORD, type StepSummary } from './ideaModel'

const FOOTER = 'This page joins stored records. It computes nothing new. A reading is not advice and not an approval.'

export interface IdeaListViewProps { data: IdeaList | null; error: string | null; onOpen(card: string): void }

export function IdeaListView({ data, error, onOpen }: IdeaListViewProps) {
  const rows = data ? newestFirst(data.cards) : []
  return (
    <div className="idea-root">
      <header className="idea-head"><h2>Ideas</h2><span className="muted">{data ? `${data.total} idea card${data.total === 1 ? '' : 's'}, newest first` : ''}</span></header>
      {error ? <p role="alert" className="idea-error">{error}</p> : null}
      {!data && !error ? <p className="muted" role="status">Loading the idea cards…</p> : null}
      {data && !rows.length ? (
        <p className="idea-empty">No idea card is written yet. Write one in the terminal: <code className="mono">alpha idea new</code></p>
      ) : null}
      {data?.truncated ? <p className="muted">Only the newest {rows.length} cards are shown.</p> : null}
      <ul className="idea-cards" aria-label="Idea cards">
        {rows.map(row => (
          <li key={row.id}>
            <button type="button" className="idea-card" data-card={row.id} onClick={() => onOpen(row.id)}>
              <span className="idea-card-claim">{row.claim || 'claim not stated'}</span>
              <span className="muted idea-card-meta">
                {`${shortDay(row.saved_at)} · card ${row.id} · ${row.tests_linked} linked test${row.tests_linked === 1 ? '' : 's'} · ${row.not_stated.length} of 9 fields not stated`}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Navigator({ steps, onJump }: { steps: StepSummary[]; onJump(id: string): void }) {
  return (
    <nav className="idea-nav" aria-label="Steps of this idea">
      <ol>
        {steps.map(step => (
          <li key={step.id}>
            <button type="button" className="idea-nav-item" data-step={step.id} data-state={step.state} onClick={() => onJump(step.id)}
              aria-label={`${step.number} ${step.title}: ${STATE_WORD[step.state]}, ${step.count}`}>
              <span className="idea-dot" aria-hidden="true" />
              <span className="idea-nav-title">{`${step.number} ${step.title}`}</span>
              <span className="mono idea-nav-count">{step.count}</span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}

export interface IdeaPageViewProps { file: IdeaFile | null; error: string | null; selectedRun: string | null; onSelectRun(id: string): void; onBack(): void }

export function IdeaPageView({ file, error, selectedRun, onSelectRun, onBack }: IdeaPageViewProps) {
  const run = useMemo(() => (file ? runsOf(file).find(item => item.id === selectedRun) ?? defaultRun(file) : null), [file, selectedRun])
  const jump = (id: string) => document.getElementById(`idea-step-${id}`)?.scrollIntoView({ block: 'start' })
  return (
    <div className="idea-root">
      <header className="idea-head">
        <button type="button" className="btn" onClick={onBack}>All ideas</button>
        <h2>{file?.card.claim ?? 'Idea'}</h2>
        {file ? <span className="muted mono">card {file.card.id}</span> : null}
      </header>
      {error ? <p role="alert" className="idea-error">{error}</p> : null}
      {!file && !error ? <p className="muted" role="status">Loading this idea…</p> : null}
      {file ? (
        <div className="idea-layout">
          <Navigator steps={ideaSteps(file, run)} onJump={jump} />
          <div className="idea-story">
            <IdeaStep file={file} />
            <HypothesisStep file={file} />
            <RuleStep run={run} />
            <DataStep run={run} />
            <TestsStep file={file} selected={run?.id ?? null} onSelect={onSelectRun} />
            <Step id="charts" number={6} title={run ? `Charts for run ${run.id.slice(0, 8)}` : 'Charts'}>
              {run ? <RunCharts key={run.id} run={run} /> : <p className="idea-empty">No rule test is selected, so there are no charts.</p>}
            </Step>
            <Step id="checks" number={7} title={run ? `Checks for run ${run.id.slice(0, 8)}` : 'Checks'}>
              {run ? <RunChecks key={run.id} run={run} /> : <p className="idea-empty">No rule test is selected, so there are no checks to show.</p>}
            </Step>
            <ToolsStep file={file} />
            <RdAgentStep />
            <FollowStep file={file} />
            <OpenStep file={file} />
            <p className="muted idea-foot">{FOOTER}</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}

const words = (cause: unknown): string => (cause instanceof Error ? cause.message : String(cause))
const CARD_PARAM = 'idea'

function cardFromHash(): string | null {
  const value = new URLSearchParams(window.location.hash.replace(/^#/, '')).get(CARD_PARAM)
  return value && /^[0-9a-f]{4,12}$/.test(value) ? value : null
}

/** Mirror the open card in the address without firing the shell's hashchange handler. */
function mirror(card: string | null): void {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  if (card) params.set(CARD_PARAM, card)
  else params.delete(CARD_PARAM)
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${params}`)
}

export function IdeaWorkspace() {
  const version = useAreaVersion('ideas')
  const [card, setCard] = useState<string | null>(cardFromHash)
  const [list, setList] = useState<IdeaList | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [file, setFile] = useState<{ card: string; value: IdeaFile } | null>(null)
  const [fileError, setFileError] = useState<{ card: string; text: string } | null>(null)
  const [run, setRun] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    api.ideaList().then(
      value => { if (live) { setList(value); setListError(null) } },
      (cause: unknown) => { if (live) setListError(words(cause)) },
    )
    return () => { live = false }
  }, [version])
  useEffect(() => {
    if (!card) return
    let live = true
    api.ideaFile(card).then(
      value => { if (live) { setFile({ card, value }); setFileError(null) } },
      (cause: unknown) => { if (live) setFileError({ card, text: words(cause) }) },
    )
    return () => { live = false }
  }, [card, version])
  const open = (next: string | null) => { setCard(next); setRun(null); mirror(next) }
  if (!card) return <IdeaListView data={list} error={listError} onOpen={open} />
  return (
    <IdeaPageView file={file && file.card === card ? file.value : null} error={fileError && fileError.card === card ? fileError.text : null}
      selectedRun={run} onSelectRun={setRun} onBack={() => open(null)} />
  )
}
