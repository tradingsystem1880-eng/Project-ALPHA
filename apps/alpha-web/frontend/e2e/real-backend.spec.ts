import { expect, test } from '@playwright/test'

import { openDocument } from './support/workstationHarness'

test('real backend captures a case and renders all material questions without vendor network', async ({
  page,
  request,
}) => {
  const externalRequests: string[] = []
  page.on('request', (outbound) => {
    const url = new URL(outbound.url())
    if (url.hostname !== 'localhost') externalRequests.push(outbound.url())
  })

  const system = await request.get('/api/system')
  expect(system.ok()).toBe(true)
  expect((await system.json()) as Record<string, unknown>).toMatchObject({
    paper_enabled: false,
    ibkr_paper_enabled: false,
  })
  const readiness = await request.get('/api/paper/readiness')
  expect(readiness.ok()).toBe(true)
  expect((await readiness.json()) as Record<string, unknown>).toMatchObject({
    schema_version: 2,
    status: 'pending',
    paper_passed: false,
    legacy_journals: 'monitoring_only',
  })

  await page.goto('')
  // New Idea lives at the top of the Research menu (artboard: no titlebar button).
  await page.getByRole('menubar').getByRole('menuitem', { name: 'Research', exact: true }).click()
  await page.getByRole('menu', { name: 'Research' }).getByRole('menuitem', { name: 'New Idea…' }).click()
  await page
    .getByLabel('Raw research idea')
    .fill('SPY may bounce after a point-in-time double bottom on equal daily sessions.')
  await page.getByLabel('Research Case name').fill('Real backend isolated walkthrough')
  await page.getByRole('button', { name: 'capture · no compute' }).click()

  const questions = page.getByLabel('Material research questions')
  await expect(questions).toBeVisible({ timeout: 15_000 })
  await expect(questions.locator('.research-material-question')).toHaveCount(3)
  await expect(page.getByText('APPROVAL UNAVAILABLE', { exact: true })).toBeVisible()
  await expect(page.locator('.sandbox-banner')).toHaveCount(0)
  await page.getByRole('button', { name: 'Governance' }).click()
  await expect(
    page.getByRole('region', { name: 'Governance', exact: true }).getByText(/SYNTHETIC D0 IS NOT REAL-MARKET EVIDENCE/),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Close Governance' }).click()
  expect(externalRequests).toEqual([])
})

test('generated project workspace is visible and refreshes without authority escalation', async ({
  page,
  request,
}) => {
  const created = await request.post('/api/projects', {
    data: {
      name: `Workspace walkthrough ${test.info().project.name}`,
      hypothesis: 'A bounded BTC event effect may exist.',
      falsification_criterion: 'Reject on an inconclusive locked result.',
    },
  })
  expect(created.ok()).toBe(true)
  const project = (await created.json()) as { project_id: string }

  await page.goto('')
  await openDocument(page, 'Build')
  await page.getByRole('tab', { name: 'Development Center', exact: true }).click()
  await page.getByLabel('Strategy project').selectOption(project.project_id)

  const workspace = page.getByRole('region', { name: 'Project workspace' })
  await expect(workspace).toBeVisible({ timeout: 15_000 })
  await expect(workspace.getByText('VERIFIED', { exact: true })).toBeVisible()
  await expect(workspace.getByText('NONE · REFERENCE PROJECTION', { exact: true })).toBeVisible()
  await expect(workspace.getByText('NON TRANSMITTING SANDBOX ONLY', { exact: true })).toBeVisible()
  await expect(workspace.getByText('NO BROKER OR ORDER AUTHORITY', { exact: true })).toBeVisible()
  await expect(workspace.getByLabel('Workspace reference indexes').locator('.chip')).toHaveCount(12)
  await workspace.getByRole('button', { name: 'Refresh generated references' }).click()
  await expect(workspace.getByRole('button', { name: 'Refresh generated references' })).toBeEnabled()
})

test('late workspace refresh cannot overwrite a newly selected project', async ({ page, request }) => {
  test.setTimeout(60_000)
  const createProject = async (name: string) => {
    const response = await request.post('/api/projects', {
      data: {
        name,
        hypothesis: 'A bounded BTC event effect may exist.',
        falsification_criterion: 'Reject on an inconclusive locked result.',
      },
    })
    expect(response.ok()).toBe(true)
    return (await response.json()) as { project_id: string }
  }
  const first = await createProject(`Workspace race A ${test.info().project.name}`)
  const second = await createProject(`Workspace race B ${test.info().project.name}`)
  let releaseRefresh!: () => void
  let markStarted!: () => void
  const refreshReleased = new Promise<void>((resolve) => { releaseRefresh = resolve })
  const refreshStarted = new Promise<void>((resolve) => { markStarted = resolve })
  await page.route(`**/api/projects/${first.project_id}/workspace/refresh`, async (route) => {
    markStarted()
    await refreshReleased
    await route.continue()
  })

  await page.goto('')
  await openDocument(page, 'Build')
  await page.getByRole('tab', { name: 'Development Center', exact: true }).click()
  const selector = page.getByLabel('Strategy project')
  const workspace = page.getByRole('region', { name: 'Project workspace' })
  const firstWorkspaceResponse = page.waitForResponse((response) => (
    response.request().method() === 'GET'
    && response.url().endsWith(`/api/projects/${first.project_id}/workspace`)
  ))
  const firstProjectResponse = page.waitForResponse((response) => (
    response.request().method() === 'GET'
    && response.url().includes(`/api/projects/${first.project_id}?lineage_limit=`)
  ))
  await selector.selectOption(first.project_id)
  const [firstWorkspace, firstProject] = await Promise.all([
    firstWorkspaceResponse,
    firstProjectResponse,
  ])
  expect(firstWorkspace.ok()).toBe(true)
  expect(firstProject.ok()).toBe(true)
  await expect(workspace.getByText(first.project_id, { exact: false })).toBeVisible({
    timeout: 15_000,
  })
  const lateRefreshResponse = page.waitForResponse((response) => (
    response.request().method() === 'POST'
    && response.url().endsWith(`/api/projects/${first.project_id}/workspace/refresh`)
  ))
  await workspace.getByRole('button', { name: 'Refresh generated references' }).click()
  await refreshStarted

  const secondWorkspaceResponse = page.waitForResponse((response) => (
    response.request().method() === 'GET'
    && response.url().endsWith(`/api/projects/${second.project_id}/workspace`)
  ))
  const secondProjectResponse = page.waitForResponse((response) => (
    response.request().method() === 'GET'
    && response.url().includes(`/api/projects/${second.project_id}?lineage_limit=`)
  ))
  await selector.selectOption(second.project_id)
  const [secondWorkspace, secondProject] = await Promise.all([
    secondWorkspaceResponse,
    secondProjectResponse,
  ])
  expect(secondWorkspace.ok()).toBe(true)
  expect(secondProject.ok()).toBe(true)
  await expect(workspace.getByText(second.project_id, { exact: false })).toBeVisible({
    timeout: 15_000,
  })
  releaseRefresh()
  await lateRefreshResponse
  await expect(workspace.getByRole('button', { name: 'Refresh generated references' })).toBeEnabled()
  await expect(workspace.getByText(second.project_id, { exact: false })).toBeVisible()
  await expect(workspace.getByText(first.project_id, { exact: false })).toHaveCount(0)
})
