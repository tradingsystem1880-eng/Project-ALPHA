// The story column of the idea page, one small component per section. Every section has an honest
// empty state and says what is missing. Readings only: no pass or fail, no grade, no advice.

import type { ReactNode } from 'react'

import type { IdeaFile, IdeaTest } from '../../api/types'
import { CopyCommand } from '../../components/CopyCommand'
import {
  dataFacts, followLine, hypothesisPairs, ideaPairs, NO_RDAGENT, ruleSentence, timeline, toolRows, type Pair,
} from './ideaModel'

export function Step({ id, number, title, children }: { id: string; number: number; title: string; children: ReactNode }) {
  return (
    <section id={`idea-step-${id}`} className="idea-step" aria-labelledby={`idea-h-${id}`}>
      <h3 id={`idea-h-${id}`}><span className="idea-step-no" aria-hidden="true">{number}</span>{title}</h3>
      {children}
    </section>
  )
}

export function Pairs({ rows }: { rows: Pair[] }) {
  return (
    <dl className="idea-pairs">
      {rows.map(([label, value]) => (
        <div key={label}><dt className="muted">{label}</dt><dd data-stated={value !== 'not stated' ? 'yes' : 'no'}>{value}</dd></div>
      ))}
    </dl>
  )
}

export const IdeaStep = ({ file }: { file: IdeaFile }) => (
  <Step id="idea" number={1} title="Idea"><Pairs rows={ideaPairs(file)} />
    {file.card.supersedes ? <p className="muted">This card replaces card {file.card.supersedes}.</p> : null}
    {file.card.superseded_by ? <p className="muted">A newer card replaces this one: {file.card.superseded_by}.</p> : null}
  </Step>
)

export const HypothesisStep = ({ file }: { file: IdeaFile }) => (
  <Step id="hypothesis" number={2} title="Hypothesis"><Pairs rows={hypothesisPairs(file)} /></Step>
)

export function RuleStep({ run }: { run: IdeaTest | null }) {
  return (
    <Step id="rule" number={3} title="Rule as built">
      <p>{ruleSentence(run)}</p>
      {run?.tested.rule ? (
        <details className="idea-spec">
          <summary>See the exact spec</summary>
          <pre className="mono" aria-label="The rule exactly as stored">{run.tested.rule}</pre>
          <p className="muted">Read only. This is the rule text stored with run {run.id}. The full spec file is not shown here.</p>
        </details>
      ) : <p className="idea-empty">No rule test is linked to this idea yet, so no rule has been built from it.</p>}
    </Step>
  )
}

export function DataStep({ run }: { run: IdeaTest | null }) {
  const facts = dataFacts(run)
  return (
    <Step id="data" number={4} title="Data used">
      {run ? <Pairs rows={facts} /> : <p className="idea-empty">No test is selected, so no data is shown.</p>}
    </Step>
  )
}

export function TestsStep({ file, selected, onSelect }: { file: IdeaFile; selected: string | null; onSelect(id: string): void }) {
  const rows = timeline(file)
  const note = file.readings_total > file.readings.length ? (
    <p className="muted">{`Showing the newest ${file.readings.length} of ${file.readings_total} linked tests.`}</p>
  ) : null
  return (
    <Step id="tests" number={5} title="Tests run">
      {!rows.length ? <p className="idea-empty">No test or setup find is linked to this idea yet.</p> : null}
      {note}
      <ol className="idea-timeline" aria-label="Every linked test, oldest first">
        {rows.map(row => {
          const pickable = row.kind === 'rule test'
          const inner = (
            <>
              <span className="mono idea-t-day">{row.day}</span>
              <span className="idea-t-kind">{row.kind} {row.id.slice(0, 8)}</span>
              <strong className="idea-t-word">{row.word}</strong>
              <span className="idea-t-aim">{row.aim}</span>
              <span className="muted idea-t-tries">{row.tries}</span>
              {row.problem ? <span className="idea-t-problem" role="note">Fault: {row.problem}</span> : null}
            </>
          )
          return (
            <li key={row.id}>
              {pickable ? (
                <button type="button" className="idea-t-row" data-run={row.id} aria-pressed={row.id === selected} onClick={() => onSelect(row.id)}>{inner}</button>
              ) : <div className="idea-t-row idea-t-find" data-run={row.id}>{inner}</div>}
            </li>
          )
        })}
      </ol>
    </Step>
  )
}

export function ToolsStep({ file }: { file: IdeaFile }) {
  const rows = toolRows(file)
  return (
    <Step id="tools" number={8} title="Tools run">
      {!rows.length ? <p className="idea-empty">No stored tool result is linked to this idea yet.</p> : (
        <ul className="idea-tools">
          {rows.map(row => (
            <li key={row.file}>
              <span className="idea-tool-name mono">{row.tool}</span>
              <span className="chip idea-tool-word" data-word={row.word}>{row.word}</span>
              <span>{row.reading}</span>
              <span className="muted">run {row.run.slice(0, 8)}</span>
            </li>
          ))}
        </ul>
      )}
    </Step>
  )
}

export const RdAgentStep = () => <Step id="rdagent" number={9} title="RD-Agent steps"><p className="idea-empty">{NO_RDAGENT}</p></Step>

export function FollowStep({ file }: { file: IdeaFile }) {
  return (
    <Step id="follow" number={10} title="Forward follow">
      {!file.follows.length ? (
        <>
          <p className="idea-empty">No paper follow names this idea yet.</p>
          <CopyCommand command="alpha follow start --test <run id>" why="Starting a follow is an owner step in the terminal. This page only shows." />
        </>
      ) : <ul>{file.follows.map(item => <li key={item.follow_id}>{followLine(item)}</li>)}</ul>}
    </Step>
  )
}

export function OpenStep({ file }: { file: IdeaFile }) {
  const open = file.open_points
  const group = (title: string, items: string[]) => (items.length ? <div><h4>{title}</h4><ul>{items.map(item => <li key={item}>{item}</li>)}</ul></div> : null)
  return (
    <Step id="open" number={11} title="Open points and next steps">
      {group('Card fields not stated', open.not_stated)}
      {group('Map lines not yet done', open.map_not_yet)}
      {group('Readings that say too little to read', open.too_little_to_read)}
      {open.next_steps.length ? (
        <div><h4>A next step could be</h4>
          {open.next_steps.map(item => <CopyCommand key={item.step} command={item.command} why={item.step} />)}
        </div>
      ) : null}
      {!open.not_stated.length && !open.map_not_yet.length && !open.too_little_to_read.length && !open.next_steps.length
        ? <p className="idea-empty">No open point is recorded.</p> : null}
    </Step>
  )
}
