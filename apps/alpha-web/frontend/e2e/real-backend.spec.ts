import { expect, test } from '@playwright/test'

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
  await page.getByRole('button', { name: 'New Idea' }).click()
  await page
    .getByLabel('Raw research idea')
    .fill('SPY may bounce after a point-in-time double bottom on equal daily sessions.')
  await page.getByLabel('Research Case name').fill('Real backend isolated walkthrough')
  await page.getByRole('button', { name: 'capture · no compute' }).click()

  const questions = page.getByLabel('Material research questions')
  await expect(questions).toBeVisible({ timeout: 15_000 })
  await expect(questions.locator('.research-material-question')).toHaveCount(3)
  await expect(page.getByText('APPROVAL UNAVAILABLE', { exact: true })).toBeVisible()
  await expect(page.getByText(/SYNTHETIC D0 IS NOT REAL-MARKET EVIDENCE/)).toBeVisible()
  expect(externalRequests).toEqual([])
})
