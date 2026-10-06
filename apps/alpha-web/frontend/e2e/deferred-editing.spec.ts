import { expect, test, type Route } from '@playwright/test'
import { preparePage, openDeskTool } from './support/workstationHarness'

const rule = (name: string) => ({ name, spec_name: name, sha256: 'a'.repeat(64), history: 60, warmup: 20, long_conditions: ['close > sma:20'], short_conditions: [], error: null, spec: { name, long_when: [{ left: { source: 'close' }, op: '>', right: { indicator: 'sma', params: [20] } }], short_when: [] } })

for (const newer of ['edit', 'load'] as const) {
  test(`late automatic rule load cannot overwrite a newer ${newer}`, async ({ page }) => {
    await preparePage(page)
    await page.route('**/api/rules/evaluate', route => route.fulfill({ json: { conditions: [], signal: null, error: 'Fixture has no evaluated bar' } }))
    await page.route('**/api/rules', route => route.fulfill({ json: { rules: [rule('first'), rule('second')] } }))
    let pending: Route | undefined
    await page.route('**/api/rules/first', route => { pending = route })
    await page.route('**/api/rules/second', route => route.fulfill({ json: rule('second') }))
    await page.goto('/#page=data&pane=PriceChart')
    await openDeskTool(page, 'Research tools')
    await page.getByLabel('Saved conditions', { exact: true }).selectOption('first')
    await page.getByRole('button', { name: 'Edit / test rules' }).click()
    await expect.poll(() => Boolean(pending)).toBe(true)
    const name = page.getByLabel('Display name', { exact: true })
    if (newer === 'edit') await name.fill('Unsaved revision')
    else await page.getByRole('complementary', { name: 'Saved rule sets' }).getByRole('button', { name: 'second second', exact: true }).click()
    await expect(name).toHaveValue(newer === 'edit' ? 'Unsaved revision' : 'second')
    const response = page.waitForResponse('**/api/rules/first')
    await pending!.fulfill({ json: rule('first') })
    await response
    await expect(name).toHaveValue(newer === 'edit' ? 'Unsaved revision' : 'second')
  })
}

test('saving a note preserves text entered while the save was pending', async ({ page }) => {
  await preparePage(page)
  await page.getByLabel('Research Case project ID').fill('research-project-1')
  await page.getByRole('button', { name: 'open case' }).click()
  let pending: Route | undefined
  let reads = 0
  await page.route('**/api/research/cases/research-project-1/notes**', route => {
    if (route.request().method() === 'POST') { pending = route; return }
    reads++
    return route.fulfill({ json: { items: [], limit: 50, offset: 0, has_more: false } })
  })
  await page.goto('/#page=data&pane=PriceChart')
  await openDeskTool(page, 'Research tools')
  await page.getByRole('tab', { name: 'Notes', exact: true }).click()
  const body = page.getByLabel('Observation or invalidation')
  await body.fill('First observation')
  await page.getByRole('button', { name: 'Save observation', exact: true }).click()
  await expect.poll(() => Boolean(pending)).toBe(true)
  await body.fill('Next observation, not submitted')
  await pending!.fulfill({ json: { note_id: 'note-1' } })
  await expect.poll(() => reads).toBeGreaterThan(1)
  await expect(page.getByRole('button', { name: 'Save observation', exact: true })).toBeEnabled()
  await expect(body).toHaveValue('Next observation, not submitted')
})
