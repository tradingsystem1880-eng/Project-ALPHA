import { expect, test, type Page } from '@playwright/test'
import { preparePage, openDeskTool } from './support/workstationHarness'

function session(status?: 'running' | 'completed' | 'interrupted') {
  return { session_id: 'recovery-session', context: { symbol: 'XRP/USDT', as_of: '2024-01-01T23:59:59Z' }, context_hash: 'a'.repeat(64), attachments: [], authority: 'none', created_at: '2024-01-01T00:00:00Z', active_job_id: null,
    turns: status ? [{ turn_id: 'turn-1', action: 'explain_chart', message: 'Explain', status, context_hash: 'a'.repeat(64), error: status === 'interrupted' ? 'Recorded worker interruption' : null, answer: status === 'completed' ? { text: 'Recovered recorded answer', citations: [], rule_draft: null } : null }] : [] }
}
async function openAssistant(page: Page) {
  await preparePage(page)
  await page.route('**/api/assistant/readiness', route => route.fulfill({ json: { available: true, reason: null, model: 'fixture', isolation_verified: true } }))
  await page.route('**/api/assistant/sessions', route => route.fulfill({ json: session() }))
  await page.route('**/api/assistant/sessions/recovery-session/turns', route => route.fulfill({ json: { job_id: 'recovery-job', status: 'running' } }))
  await page.goto('/#page=data&pane=PriceChart')
  await openDeskTool(page, 'Research tools')
  await page.getByRole('tab', { name: 'Assistant', exact: true }).click()
}

test('assistant surfaces job rejection before a turn was appended', async ({ page }) => {
  await openAssistant(page)
  await page.route('**/api/assistant/sessions/recovery-session', route => route.fulfill({ json: session() }))
  await page.route('**/api/jobs/recovery-job', route => route.fulfill({ json: { job_id: 'recovery-job', status: 'failed', current_step: 'Rules changed since this scan', lines: [] } }))
  await page.getByRole('button', { name: 'Ask assistant', exact: true }).click()
  const dock = page.getByRole('region', { name: 'Market assistant' })
  await expect(dock.getByRole('alert')).toContainText('Rules changed since this scan')
  await expect(dock.getByRole('alert')).toContainText('new conversation')
  await expect(dock.getByRole('alert')).toContainText('current rules')
  await expect(page.getByRole('button', { name: 'Ask assistant', exact: true })).toBeEnabled()
})

test('restored running turn without a web job handle continues polling its saved session', async ({ page }) => {
  await openAssistant(page)
  let completed = false
  let reads = 0
  let turns = 0
  await page.route('**/api/assistant/sessions/recovery-session/turns', route => { turns++; return route.fulfill({ json: { job_id: 'recovery-job', status: 'running' } }) })
  await page.route('**/api/assistant/sessions/recovery-session', route => { reads++; return route.fulfill({ json: session(completed ? 'completed' : 'running') }) })
  await page.route('**/api/jobs/recovery-job', route => route.fulfill({ json: { job_id: 'recovery-job', status: 'running' } }))
  await page.getByRole('button', { name: 'Ask assistant', exact: true }).click()
  await expect.poll(() => reads).toBeGreaterThan(0)
  await page.getByRole('tab', { name: 'Conditions', exact: true }).click()
  await page.getByRole('tab', { name: 'Assistant', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Working…', exact: true })).toBeDisabled()
  const before = reads
  completed = true
  await expect(page.getByText('Recovered recorded answer', { exact: true })).toBeVisible()
  expect(reads).toBeGreaterThan(before)
  await expect(page.getByRole('button', { name: 'Ask assistant', exact: true })).toBeEnabled()
  expect(turns).toBe(1) // Recovery never starts another inference.
})

for (const status of ['completed', 'interrupted'] as const) {
 test(`missing web job does not hide a ${status} saved outcome`, async ({ page }) => {
  await openAssistant(page)
  await page.route('**/api/assistant/sessions/recovery-session', route => route.fulfill({ json: session(status) }))
  await page.route('**/api/jobs/recovery-job', route => route.fulfill({ status: 404, json: { detail: 'Job not retained after restart' } }))
  await page.getByRole('button', { name: 'Ask assistant', exact: true }).click()
  await expect(page.getByText(status === 'completed' ? 'Recovered recorded answer' : 'Recorded worker interruption', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ask assistant', exact: true })).toBeEnabled()
 })
}
