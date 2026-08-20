import { useMemo, useState } from 'react'

import { registerOwnerCredential } from './ownerAuth'

function enrollmentToken(): string {
  const params = new URLSearchParams(window.location.hash.replace(/^#/u, ''))
  return params.get('token') ?? ''
}

export function OwnerEnrollment() {
  const token = useMemo(enrollmentToken, [])
  const [busy, setBusy] = useState(false)
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function enroll(): Promise<void> {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await registerOwnerCredential(token)
      window.history.replaceState(null, '', '/owner-auth/enroll')
      setComplete(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="owner-enrollment-shell">
      <section className="owner-enrollment-card" aria-labelledby="owner-enrollment-title">
        <span className="eyebrow">Project ALPHA · local owner ceremony</span>
        <h1 id="owner-enrollment-title">Enroll Touch ID</h1>
        <p>
          This credential can authorize only the closed research-lifecycle actions shown in the
          Workstation. It cannot override a research gate, reveal a holdout, authorize paper entry,
          operate a broker, or place an order.
        </p>
        {complete ? (
          <div className="workbench-notice" role="status">
            <strong>ENROLLED</strong>
            <span>Touch ID is ready. You may close this page and return to Research.</span>
          </div>
        ) : null}
        {!token && !complete ? (
          <div className="workbench-notice" role="alert">
            <strong>TRUSTED CLI REQUIRED</strong>
            <span>Run alpha owner-auth enroll --reason &quot;your reason&quot; to issue a short-lived link.</span>
          </div>
        ) : null}
        {error ? (
          <div className="workbench-notice" role="alert">
            <strong>ENROLLMENT FAILED</strong>
            <span>{error} Issue a fresh link with alpha owner-auth recover if needed.</span>
          </div>
        ) : null}
        <button
          className="btn primary"
          type="button"
          disabled={!token || busy || complete}
          onClick={() => void enroll()}
        >
          {busy ? 'waiting for Touch ID…' : complete ? 'Touch ID enrolled' : 'Start Touch ID enrollment'}
        </button>
        <a href="/">Return to Workstation</a>
      </section>
    </main>
  )
}
