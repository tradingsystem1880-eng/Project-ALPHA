// Codex Bench — a workbench, not a chat. The conversation happens in the owner's Codex
// CLI/IDE session attached to alpha-mcp; this panel prepares context (packet composer +
// protocol picker), records nothing itself, and displays byte-identically what Codex was
// given (packet history) and what it said (notes, fenced as never-evidence).

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { useAreaVersion } from '../state/activity'
import type {
  ResearchContextPacket,
  ResearchNote,
  ResearchProtocolEntry,
} from '../api/types'
import { Placeholder } from '../components/Placeholder'
import type { PanelHandleProps } from '../context/panelHandle'
import { usePanelLinked } from '../context/usePanelLinked'
import {
  NOTE_FENCE_BADGE,
  PACKET_KINDS,
  noteAuthorLabel,
  packetBuildCommand,
  packetHistoryRows,
  packetPayloadJson,
  type PacketKind,
} from './codexBenchModel'

export function CodexBench(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const projectId = panelLink.linked.projectId
  const [protocols, setProtocols] = useState<ResearchProtocolEntry[] | null>(null)
  const [packets, setPackets] = useState<ResearchContextPacket[] | null>(null)
  const researchVersion = useAreaVersion('research')
  const [notesVersion, setNotesVersion] = useState(0)
  const [notes, setNotes] = useState<ResearchNote[] | null>(null)
  const [kind, setKind] = useState<PacketKind>('research_case')
  const [protocolId, setProtocolId] = useState<string>('new-idea-intake')
  const [openPacket, setOpenPacket] = useState<ResearchContextPacket | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api
      .researchProtocols()
      .then((library) => {
        if (live) setProtocols(library.protocols)
      })
      .catch((reason: unknown) => {
        if (live) setError(reason instanceof Error ? reason.message : String(reason))
      })
    return () => {
      live = false
    }
  }, [])

  useEffect(() => {
    if (!projectId) {
      setPackets(null)
      setNotes(null)
      setOpenPacket(null)
      return
    }
    let live = true
    setError(null)
    Promise.all([api.researchContextPackets(projectId), api.researchNotes(projectId)])
      .then(([packetPage, notePage]) => {
        if (!live) return
        setPackets(packetPage.items)
        setNotes(notePage.items)
      })
      .catch((reason: unknown) => {
        if (!live) return
        setError(reason instanceof Error ? reason.message : String(reason))
      })
    return () => {
      live = false
    }
  }, [projectId, researchVersion, notesVersion])

  const command = projectId
    ? packetBuildCommand(projectId, kind, protocolId || null, panelLink.linked.symbol)
    : null
  const activeProtocol = protocols?.find((entry) => entry.id === protocolId) ?? null
  const history = packetHistoryRows(packets ?? [])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Codex Bench</span>
        <span className="chip kind">MCP-ATTACHED · NO CHAT · NO API KEY</span>
        <span className="muted">packet composer · protocol picker · history · notes</span>
      </div>
      <div className="panel-body panel-pad workbench codex-bench" tabIndex={0}>
        {error ? (
          <div className="workbench-notice" role="alert">
            <strong>CODEX BENCH UNAVAILABLE</strong>
            <span>{error}</span>
          </div>
        ) : null}
        {!projectId ? (
          <Placeholder big="NO CASE SELECTED">
            Select a case in the Research Backlog; the bench prepares its context for the
            external Codex session.
          </Placeholder>
        ) : (
          <>
            <section aria-label="Packet composer">
              <div className="rd-head">Compose a context packet</div>
              <div className="research-form-row">
                <label>
                  <span className="eyebrow">Packet kind</span>
                  <select
                    className="field"
                    value={kind}
                    onChange={(event) => setKind(event.target.value as PacketKind)}
                  >
                    {PACKET_KINDS.map((value) => (
                      <option key={value} value={value}>
                        {value.replaceAll('_', ' ')}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span className="eyebrow">Protocol (paired, hash-recorded)</span>
                  <select
                    className="field"
                    value={protocolId}
                    onChange={(event) => setProtocolId(event.target.value)}
                  >
                    <option value="">No protocol</option>
                    {(protocols ?? []).map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.title}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {activeProtocol ? (
                <p className="muted">
                  {activeProtocol.purpose} → {activeProtocol.output_contract}
                </p>
              ) : null}
              {command ? (
                <div className="workbench-notice" role="note">
                  <strong>RECORDING HAPPENS ON THE GOVERNED SEAMS</strong>
                  <span>
                    Run this on the trusted-local CLI (or let Codex call
                    build_research_context_packet over MCP); the recorded packet appears in
                    the history below, byte-identically.
                  </span>
                  <code className="mono">{command}</code>
                  <button
                    className="btn"
                    type="button"
                    onClick={() => {
                      void navigator.clipboard.writeText(command).then(() => {
                        setCopied(true)
                        window.setTimeout(() => setCopied(false), 1_500)
                      })
                    }}
                  >
                    {copied ? 'copied' : 'copy command'}
                  </button>
                </div>
              ) : null}
            </section>

            <section aria-label="Packet history">
              <div className="rd-head">
                Packet history <span className="muted">— every byte Codex was given</span>
              </div>
              {history.length === 0 ? (
                <p className="muted">No packets recorded for this case yet.</p>
              ) : (
                <ul className="backlog-list">
                  {history.map((row) => (
                    <li key={row.packet_id}>
                      <button
                        type="button"
                        className="backlog-row"
                        onClick={() => {
                          const match = packets?.find(
                            (candidate) => candidate.packet_id === row.packet_id,
                          )
                          setOpenPacket(match ?? null)
                        }}
                      >
                        <span className="backlog-title mono">
                          {row.packet_id.slice(0, 14)}… · {row.packet_kind}
                        </span>
                        <span className="backlog-meta mono">
                          {row.protocol_id ?? 'no protocol'} · {row.payload_bytes} bytes ·{' '}
                          {row.created_at}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {openPacket ? (
                <div className="codex-packet-view">
                  <div className="rd-head mono">{openPacket.packet_id}</div>
                  <pre className="mono codex-packet-json">{packetPayloadJson(openPacket)}</pre>
                </div>
              ) : null}
            </section>

            <section aria-label="Notes stream">
              <div className="rd-head">Notes stream</div>
              <NoteComposer projectId={projectId} onAdded={() => setNotesVersion((v) => v + 1)} />
              {(notes ?? []).length === 0 ? (
                <p className="muted">No commentary recorded for this case yet.</p>
              ) : (
                <div className="research-findings">
                  {(notes ?? []).map((note) => (
                    <div key={note.note_id}>
                      <span className="eyebrow">
                        {note.note_kind.replaceAll('_', ' ')} · {noteAuthorLabel(note)}
                      </span>
                      <span className="chip fail">{NOTE_FENCE_BADGE}</span>
                      <p>{note.body}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

const NOTE_KINDS = ['critique', 'confounder_review', 'test_design', 'completeness_review', 'synthesis'] as const

/** The owner answers Codex in the same stream its notes are read from — commentary, never evidence. */
function NoteComposer({ projectId, onAdded }: { projectId: string; onAdded: () => void }) {
  const [kind, setKind] = useState<(typeof NOTE_KINDS)[number]>('critique')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <form
      className="note-composer"
      aria-label="Add owner note"
      onSubmit={(event) => {
        event.preventDefault()
        setBusy(true)
        setError(null)
        api
          .researchNoteAdd(projectId, { note_kind: kind, body: body.trim() })
          .then(() => {
            setBody('')
            onAdded()
          })
          .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)))
          .finally(() => setBusy(false))
      }}
    >
      <label className="field-row">
        <span className="field-label">Note kind</span>
        <select className="field" value={kind} onChange={(event) => setKind(event.target.value as (typeof NOTE_KINDS)[number])}>
          {NOTE_KINDS.map((item) => (
            <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>
          ))}
        </select>
      </label>
      <label className="field-row">
        <span className="field-label">Owner note</span>
        <textarea className="field" value={body} onChange={(event) => setBody(event.target.value)} placeholder="Your reply to Codex — recorded as commentary, never evidence" />
      </label>
      <button className="btn primary" type="submit" disabled={busy || !body.trim()}>
        {busy ? 'Adding…' : 'Add note'}
      </button>
      {error ? <span className="leak">⚠ {error}</span> : null}
    </form>
  )
}
