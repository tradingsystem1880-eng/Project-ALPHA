import { openTask } from './support/workstationHarness'
import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { writeFile } from 'node:fs/promises'

test('real workflow navigation, asset selection, chart and history', async ({ page }) => {
  test.setTimeout(120_000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByRole('menubar', { name: 'Terminal menu' })).toBeVisible()
  for (const [section, task] of [['Data & Assets', 'Data downloads'], ['Research', 'Research Case'], ['Strategies & Tests', 'Builder'], ['Results', 'Run library'], ['Operations', 'Jobs'], ['Settings', 'Governance']]) {
    await openTask(page, section, task)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width)
    await expect(page.getByText(/panel crashed/i)).toHaveCount(0)
  }
  await page.getByRole('button', { name: 'Symbol, venue and timeframe' }).click()
  const asset = page.getByRole('combobox', { name: 'Active asset' })
  await asset.click()
  await expect(page.getByRole('listbox', { name: 'Stored assets' }).getByRole('option', { name: /BTC\/USDT/ })).toBeVisible({ timeout: 30_000 })
  await asset.fill('BTC')
  await asset.press('Enter')
  await expect(page.getByRole('dialog', { name: 'Working context' })).toHaveCount(0)
  await openTask(page, 'Data & Assets', 'Price')
  await expect(page.getByRole('region', { name: 'Price', exact: true }).locator('.count')).toHaveText('400 bars', { timeout: 30_000 })
  await openTask(page, 'Research', 'Research Case')
  await page.goBack()
  await expect(page.getByRole('tab', { name: 'Price', exact: true })).toHaveAttribute('aria-selected', 'true')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Symbol, venue and timeframe' })).toContainText('BTCUSDT')
  const axe = await new AxeBuilder({ page }).analyze()
  expect(axe.violations.filter(item => ['serious', 'critical'].includes(item.impact ?? '')), JSON.stringify(axe.violations)).toEqual([])
  expect(errors).toEqual([])
})

test('real rule validation, persistence, scanner and workspace round trip', async ({ page, request }) => {
  test.setTimeout(120_000)
  const suffix = test.info().project.name.replaceAll('-', '_')
  const rule = `browser_${suffix}`
  await page.goto('/#page=strategies&pane=StrategyBuilder')
  const editor = page.getByRole('region', { name: 'Rule editor' })
  await editor.getByLabel('long condition 1 left').fill('sma:5')
  await editor.getByLabel('long condition 1 right').fill('sma:20')
  await expect(editor.getByRole('status')).toContainText(/^valid ·/, { timeout: 30_000 })
  await editor.getByRole('combobox', { name: 'Test asset' }).click()
  await page.getByRole('listbox', { name: 'Stored assets' }).getByRole('option', { name: /BTC\/USDT/ }).click()
  await editor.getByLabel('File name').fill(rule)
  await editor.getByRole('button', { name: 'Save rule set' }).click()
  await expect(editor.getByRole('button', { name: 'Test in sandbox' })).toBeEnabled({ timeout: 30_000 })
  const persisted = await request.get(`/api/rules/${rule}`)
  expect(persisted.ok()).toBe(true)
  expect((await persisted.json()).long_conditions).toEqual(['sma:5 > sma:20'])
  await page.reload()
  await expect(page.getByRole('complementary', { name: 'Saved rule sets' })).toContainText(rule, { timeout: 30_000 })
  await openTask(page, 'Strategies & Tests', 'Scanner')
  await page.getByLabel('Scan name', { exact: true }).fill(rule)
  await page.getByRole('combobox', { name: 'Rule set', exact: true }).selectOption(rule)
  await page.getByLabel('Symbols (blank = all stored)').fill('BTC/USDT')
  await page.getByRole('button', { name: 'Save scan', exact: true }).click()
  const scanRow = page.locator('.scanner-list li').filter({ hasText: rule })
  await expect(scanRow).toBeVisible({ timeout: 30_000 })
  await scanRow.getByRole('button', { name: 'Run', exact: true }).click()
  await expect(page.getByRole('table', { name: 'Scan results' })).toContainText('BTC/USDT', { timeout: 30_000 })
  await scanRow.getByRole('button', { name: 'Check', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('new alert', { timeout: 30_000 })
  await page.goto('/#page=settings&pane=Workspaces')
  await page.getByRole('button', { name: 'Symbol, venue and timeframe' }).click()
  await page.getByLabel('From', { exact: true }).fill('2020-01-01')
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByPlaceholder('Name this context').fill(rule)
  await page.getByRole('button', { name: 'Save current', exact: true }).click()
  await expect(page.getByRole('button', { name: rule, exact: true })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Symbol, venue and timeframe' }).click()
  await page.getByRole('button', { name: 'Clear window', exact: true }).click()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('button', { name: rule, exact: true }).click()
  await page.getByRole('button', { name: 'Symbol, venue and timeframe' }).click()
  await expect(page.getByLabel('From', { exact: true })).toHaveValue('2020-01-01')
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByTitle(`Delete ${rule}`, { exact: true }).click()
  await expect(page.getByRole('button', { name: rule, exact: true })).toHaveCount(0, { timeout: 30_000 })
  await page.goto('/#page=strategies&pane=Scanner')
  await page.getByRole('button', { name: `Delete scan ${rule}`, exact: true }).click()
  await expect(page.locator('.scanner-list li').filter({ hasText: rule })).toHaveCount(0, { timeout: 30_000 })
  await openTask(page, 'Strategies & Tests', 'Builder')
  await page.getByRole('button', { name: `Delete rule set ${rule}`, exact: true }).click()
  await expect(page.getByRole('button', { name: `Delete rule set ${rule}`, exact: true })).toHaveCount(0, { timeout: 30_000 })

})

test('@reference-only every real workflow task opens in both market profiles', async ({ page }, info) => {
  test.setTimeout(300_000)
  const audit: { profile: string; page: string; task: string; alerts: string[] }[] = []
  const failures: { url: string; status: number }[] = []
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('response', response => { if (response.url().includes('/api/') && response.status() >= 400) failures.push({ url: response.url(), status: response.status() }) })
  await page.goto('/')
  for (const profile of ['crypto', 'equities']) {
    await page.getByLabel('Market profile').selectOption(profile)
    for (const section of ['Data & Assets', 'Research', 'Strategies & Tests', 'Results', 'Operations', 'Settings']) {
      await page.getByRole('menuitem', { name: 'View', exact: true }).click()
      const titles = (await page.locator('.menu-pop .menu-item').allTextContents()).filter(t => t.startsWith(`${section} › `)).map(t => t.slice(`${section} › `.length))
      expect(titles.length).toBeGreaterThan(0)
      await page.keyboard.press('Escape')
      for (const title of titles) {
        await openTask(page, section, title)
        await expect(page.locator('.document-tabs').getByRole('tab', { name: title, exact: true })).toHaveAttribute('aria-selected', 'true')
        await expect(title === 'Price' ? page.locator('.chart-document') : page.locator('.workflow-panel')).toBeVisible()
        await page.waitForTimeout(350)
        await expect(page.getByText(/panel crashed/i)).toHaveCount(0)
        audit.push({ profile, page: section, task: title, alerts: await page.getByRole('alert').allTextContents() })
      }
      await page.screenshot({ path: info.outputPath(`${profile}-${section.replaceAll(/[^a-z]/gi, '-')}.png`) })
    }
  }
  const inventory = info.outputPath('real-task-inventory.json')
  await writeFile(inventory, JSON.stringify({ audit, failures, errors }, null, 2))
  await info.attach('real-task-inventory', { path: inventory, contentType: 'application/json' })
  expect(errors).toEqual([])
  expect(audit.filter(item => item.profile === 'crypto').length).toBeGreaterThan(30)
  expect(audit.filter(item => item.profile === 'equities').length).toBeGreaterThan(25)
  expect(failures).toEqual([])
  expect(audit.filter(item => item.alerts.length)).toEqual([])
})

test('@reference-only real sandbox execution produces a persisted report and one history entry', async ({ page, request }) => {
  test.setTimeout(240_000)
  const name = 'browser_execution'
  const saved = await request.post('/api/rules', { data: { name, spec: { name, long_when: [{ left: { indicator: 'sma', params: [5] }, op: '>', right: { indicator: 'sma', params: [20] } }], short_when: [] } } })
  expect(saved.ok(), await saved.text()).toBe(true)
  await page.goto('/#page=strategies&pane=StrategyBuilder')
  await page.getByLabel('Market profile').selectOption('equities')
  await page.getByRole('complementary', { name: 'Saved rule sets' }).getByRole('button', { name: new RegExp(name) }).first().click()
  await page.getByRole('combobox', { name: 'Test asset' }).click()
  await page.getByRole('listbox', { name: 'Stored assets' }).getByRole('option', { name: /SPY/ }).click()
  const accepted = page.waitForResponse(response => response.url().endsWith('/api/jobs') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Test in sandbox', exact: true }).click()
  const response = await accepted
  expect(response.ok(), await response.text()).toBe(true)
  const { job_id: jobId } = await response.json() as { job_id: string }
  let job: { status: string; run_id: string | null; lines: string[] } | undefined
  await expect.poll(async () => {
    job = await (await request.get(`/api/jobs/${jobId}`)).json()
    return job?.status
  }, { timeout: 180_000, intervals: [1000, 2000] }).not.toBe('running')
  expect(job?.status, JSON.stringify(job)).toBe('done')
  expect(job?.run_id).toMatch(/^[0-9a-f]{16}$/)
  await expect(page.getByRole('tree', { name: 'Report sections' })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.rg-watermark-chip')).toContainText(/STANDALONE|UNQUALIFIED/i)
  const persisted = await request.get(`/api/runs/${job!.run_id}`)
  expect(persisted.ok()).toBe(true)
  await page.goBack()
  await expect(page.getByRole('tab', { name: 'Builder', exact: true })).toHaveAttribute('aria-selected', 'true')
})
