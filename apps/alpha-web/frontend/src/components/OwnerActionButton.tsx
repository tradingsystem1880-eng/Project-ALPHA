// One owner step, completable where it is announced: a reason field and a `Touch ID · <verb>`
// button that binds this exact project, artifact, case revision, consequence and reason through
// the existing owner-auth challenge/perform routes (owner_auth.py). It grants nothing the CLI
// would not: the server re-verifies presence and dispatches the closed action vocabulary. When
// the step cannot be offered, the button is disabled with the reason; when Touch ID is not
// enrolled, the error carries a link to enrol.

import { useState } from 'react'

import type { OwnerActionType } from '../api/client'
import type { ResearchCase } from '../api/types'
import { contentAddressHash, performOwnerAction, researchCaseRevision } from '../auth/ownerAuth'

interface Props {
  researchCase: ResearchCase
  actionType: OwnerActionType
  /** The verb after `Touch ID ·`, e.g. `launch D1`. */
  label: string
  consequence: string
  payload: Record<string, unknown>
  /** Content-addressed artifact the decision binds to; the active contract by default. */
  artifactId?: string | null
  disabledReason?: string | null
  primary?: boolean
  onComplete: () => void
}

function describe(cause: unknown): string {
  if (cause instanceof Error) return cause.message
  return String(cause)
}

/** Errors that mean "no credential yet" rather than "refused". */
function needsEnrollment(message: string): boolean {
  return /enrol|no owner credential|not registered|credential/i.test(message)
}

export function OwnerActionButton({
  researchCase,
  actionType,
  label,
  consequence,
  payload,
  artifactId,
  disabledReason = null,
  primary = true,
  onComplete,
}: Props) {
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const artifact = artifactId ?? researchCase.active_contract_id

  async function perform(): Promise<void> {
    setPending(true)
    setError(null)
    try {
      if (!artifact) throw new Error('This case has no content-addressed artifact to bind the decision to.')
      await performOwnerAction({
        action_type: actionType,
        project_id: researchCase.project_id,
        artifact_hash: contentAddressHash(artifact),
        expected_case_revision: await researchCaseRevision(researchCase),
        consequence_summary: consequence,
        reason: reason.trim(),
        payload,
      })
      setReason('')
      onComplete()
    } catch (cause) {
      setError(describe(cause))
    } finally {
      setPending(false)
    }
  }

  const blocked = disabledReason ?? (artifact ? null : 'no content-addressed artifact on this case')
  return (
    <div className="owner-action" role="group" aria-label={`Owner step: ${label}`}>
      <input
        className="field owner-action-reason"
        value={reason}
        maxLength={8192}
        placeholder="Reason (recorded with the receipt)"
        aria-label={`Reason for ${label}`}
        disabled={blocked !== null || pending}
        onChange={(event) => setReason(event.target.value)}
      />
      <button
        type="button"
        className={`btn${primary ? ' primary' : ''}`}
        disabled={blocked !== null || pending || !reason.trim()}
        title={blocked ?? consequence}
        onClick={() => void perform()}
      >
        {pending ? 'waiting for Touch ID…' : `Touch ID · ${label}`}
      </button>
      {blocked ? <span className="muted owner-action-blocked">{blocked}</span> : null}
      {error ? (
        <div className="workbench-notice" role="alert">
          <strong>ACTION BLOCKED</strong>
          <span>{error}</span>
          {needsEnrollment(error) ? (
            <a className="btn" href="/owner-auth/enroll">
              Enroll Touch ID
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
