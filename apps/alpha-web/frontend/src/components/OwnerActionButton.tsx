// Explicit local confirmation binds one closed action and records intent, not biometric presence.

import { useState } from 'react'

import type { OwnerActionType } from '../api/client'
import type { ResearchCase } from '../api/types'
import { contentAddressHash, performOwnerAction, researchCaseRevision } from '../auth/ownerAuth'

interface Props {
  researchCase: ResearchCase
  actionType: OwnerActionType
  /** The verb after `Confirm ·`, e.g. `launch D1`. */
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
        {pending ? 'confirming…' : `Confirm · ${label}`}
      </button>
      {blocked ? <span className="muted owner-action-blocked">{blocked}</span> : null}
      {error ? (
        <div className="workbench-notice" role="alert">
          <strong>ACTION BLOCKED</strong>
          <span>{error}</span>

        </div>
      ) : null}
    </div>
  )
}
