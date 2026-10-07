import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { ResearchNote } from '../api/types'
import { useLinked } from '../context/linked'

export function DeskNotes() {
  const { projectId, symbol } = useLinked()
  const [notes, setNotes] = useState<ResearchNote[]>([])
  const [body, setBody] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)
  const generation = useRef(0)
  const editRevision = useRef(0)
  const invalidateNotes = useCallback(() => { generation.current++ }, [])
  useEffect(() => {
    invalidateNotes(); setBody(''); setError(null); setBusy(false)
    return invalidateNotes
  }, [projectId, invalidateNotes])
  useEffect(() => {
    let live = true
    setNotes([])
    if (projectId) api.researchNotes(projectId).then(value => { if (live) setNotes(value.items) }).catch(cause => { if (live) setError(String(cause)) })
    return () => { live = false }
  }, [projectId, version])
  return <section className="desk-notes" aria-label="Research notes"><h2>Keep the reasoning</h2>
    {!projectId ? <p>Select a research case in Research to attach observations and negative findings.</p> : <>
      <p>Case {projectId} · {symbol ?? 'No market selected'}</p>
      <label>Observation or invalidation<textarea className="field" value={body} onChange={event => { editRevision.current++; setBody(event.target.value) }} placeholder="What changed? What would invalidate the edge?" /></label>
      <button className="btn" disabled={busy || !body.trim()} onClick={() => {
        const submittedGeneration = generation.current
        const submittedRevision = editRevision.current
        setBusy(true); setError(null)
        void api.researchNoteAdd(projectId, { body: body.trim(), note_kind: 'synthesis' }).then(() => {
          if (generation.current !== submittedGeneration) return
          if (editRevision.current === submittedRevision) setBody('')
          setVersion(value => value + 1)
        }).catch(cause => { if (generation.current === submittedGeneration) setError(String(cause)) })
          .finally(() => { if (generation.current === submittedGeneration) setBusy(false) })
      }}>{busy ? 'Saving…' : 'Save observation'}</button>
      <p className="muted">Notes record reasoning; they are not admitted empirical evidence.</p>
      {notes.map(note => <article key={note.note_id}><strong>{note.author_kind} · {note.created_at.slice(0, 16)}</strong><p>{note.body}</p></article>)}
    </>}{error ? <p role="alert">{error}</p> : null}</section>
}
