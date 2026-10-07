import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { preparePage, openDeskTool, openTask } from './support/workstationHarness'

const candles = { 'XRP/USDT': Array.from({ length: 60 }, (_, i) => ({ t: 1700000000 + i * 86400, o: 100 + i, h: 102 + i, l: 99 + i, c: 101 + i, v: 1000 })) }
const rule = { name: 'trend', spec_name: 'Trend', sha256: 'a'.repeat(64), history: 60, warmup: 20, long_conditions: ['close > sma:20'], short_conditions: [] }

test('chart checklist reports backend values and dock layout survives navigation', async ({ page }) => {
  await preparePage(page, { candles })
  await page.route('**/api/rules', route => route.fulfill({ json: { rules: [rule] } }))
  let evaluations = 0
  await page.route('**/api/rules/evaluate', route => {
    evaluations++
    return route.fulfill({ json: { schema_version: 1, rules_id: 'trend', rules_sha256: rule.sha256, symbol: 'XRP/USDT', as_of: '2024-01-01', bar_ts: 1704067200, signal: 1, error: null, authority: 'none', conditions: [{ side: 'long', index: 0, label: 'close > sma:20', left: 160, right: 150, status: 'pass', reason: null }] } })
  })
  await page.goto('/#page=data&pane=PriceChart')
  await openDeskTool(page, 'Research tools')
  await page.getByLabel('Saved conditions', { exact: true }).selectOption('trend')
  await expect(page.getByRole('region', { name: 'Condition checklist' })).toContainText('160 / 150')
  await expect(page.getByRole('region', { name: 'Condition checklist' })).toContainText('Long condition')
  expect(evaluations).toBe(1)
  await page.getByRole('tab', { name: 'Indicators', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Search indicators' })).toBeVisible()
  await openTask(page, 'Research', 'Literature')
  await openTask(page, 'Data & Assets', 'Price')
  await expect(page.getByRole('tab', { name: 'Indicators', exact: true })).toHaveAttribute('aria-selected', 'true')
  await openDeskTool(page, 'Workspace results')
  await page.getByRole('tab', { name: 'Scan results', exact: true }).press('ArrowRight')
  await expect(page.getByRole('region', { name: 'Workspace results', exact: true }).getByRole('tab', { name: 'Trades', exact: true })).toBeFocused()
  await expect(page.getByRole('region', { name: 'Recorded trades' })).toContainText('Choose a recorded run')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.screenshot({ path: `/tmp/alpha-edge-workspace-${test.info().project.name}.png`, fullPage: true })
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()
  expect(accessibility.violations).toEqual([])
})

test('assistant receives identifiers, shows cited output and refuses stale drafts', async ({ page }) => {
  await preparePage(page, { candles })
  await page.route('**/api/assistant/readiness', route => route.fulfill({ json: { available: true, reason: null, model: 'fixture-model', isolation_verified: true } }))
  let session: Record<string, unknown> = {}
  await page.route('**/api/assistant/sessions', async route => {
    const body = route.request().postDataJSON()
    expect(body.context.symbol).toBe('XRP/USDT')
    expect(body.context).not.toHaveProperty('bars')
    session = { session_id: 'fixture-session', context: body.context, context_hash: 'a'.repeat(64), authority: 'none', created_at: new Date().toISOString(), attachments: [{ ref: 'chart', label: 'Stored chart', content_hash: 'b'.repeat(64) }], turns: [], active_job_id: null }
    await route.fulfill({ json: session })
  })
  await page.route('**/api/assistant/sessions/fixture-session', route => route.fulfill({ json: session }))
  await page.route('**/api/assistant/sessions/fixture-session/turns', route => {
    session.turns = [{ turn_id: 'turn-1', action: 'draft_rules', message: 'test the trend', status: 'completed', context_hash: session.context_hash, error: null, answer: { text: 'This is an untested hypothesis; costs and out-of-sample evidence are missing.', citations: ['chart'], rule_draft: { name: 'Trend', long_when: [{ left: { source: 'close' }, op: '>', right: { indicator: 'sma', params: [20] } }], short_when: [] } } }]
    return route.fulfill({ json: { job_id: 'assistant-job', status: 'running', session_id: null } })
  })
  await page.route('**/api/jobs/assistant-job', route => route.fulfill({ json: { job_id: 'assistant-job', status: 'done' } }))
  await page.goto('/#page=data&pane=PriceChart')
  await openDeskTool(page, 'Research tools')
  await page.getByRole('tab', { name: 'Assistant', exact: true }).click()
  await page.getByLabel('Assistant task').selectOption('draft_rules')
  await page.getByLabel('Ask the market assistant').fill('test the trend')
  await page.getByRole('button', { name: 'Ask assistant', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Market assistant' })).toContainText('out-of-sample evidence are missing')
  await expect(page.getByRole('button', { name: 'Open draft in rule builder' })).toBeEnabled()
  await page.getByRole('button', { name: 'Show attached source chart' }).click()
  await expect(page.getByText('Stored chart', { exact: true }).first()).toBeVisible()
  await page.route('**/api/symbols', route => route.fulfill({ json: { symbols: ['XRP/USDT', 'BTC/USDT'] } }))
  await page.getByRole('button', { name: 'Symbol, venue and timeframe' }).click()
  await page.getByRole('combobox', { name: 'Active asset' }).fill('BTC/USDT')
  await page.getByRole('option', { name: /^BTC\/USDT / }).click()
  await expect(page.getByRole('region', { name: 'Market assistant' })).toContainText('Market context changed')
  await expect(page.getByRole('button', { name: 'Open draft in rule builder' })).toBeDisabled()
})

test('retired assistant restoration and draft checks cannot replace a new conversation', async ({ page }) => {
  await preparePage(page, { candles })
  await page.route('**/api/assistant/readiness', route => route.fulfill({ json: { available: true, model: 'fixture', reason: null, isolation_verified: true } }))
  const session = { session_id: 'restore-session', context: { symbol: 'XRP/USDT', as_of: '2024-01-01T23:59:59Z' }, context_hash: 'a'.repeat(64), attachments: [], authority: 'none', created_at: '2024-01-01T00:00:00Z', active_job_id: null,
    turns: [{ turn_id: 'draft', action: 'draft_rules', message: '', status: 'completed', error: null, answer: { text: 'Retained draft', citations: [], rule_draft: { name: 'draft' } } }] }
  await page.route('**/api/assistant/sessions', route => route.fulfill({ json: session }))
  await page.route('**/api/assistant/sessions/restore-session/turns', route => route.fulfill({ json: { job_id: 'restore-job', status: 'running' } }))
  await page.route('**/api/jobs/restore-job', route => route.fulfill({ json: { job_id: 'restore-job', status: 'done' } }))
  let releaseRestore: (() => void) | undefined
  let delayRestore = false
  let restoreStarted = false
  await page.route('**/api/assistant/sessions/restore-session', async route => {
    if (delayRestore) { restoreStarted = true; await new Promise<void>(resolve => { releaseRestore = resolve }) }
    await route.fulfill({ json: session })
  })
  await page.goto('/#page=data&pane=PriceChart')
  await openDeskTool(page, 'Research tools')
  await page.getByRole('tab', { name: 'Assistant', exact: true }).click()
  await page.getByRole('button', { name: 'Ask assistant', exact: true }).click()
  await expect(page.getByText('Retained draft', { exact: true })).toBeVisible()
  delayRestore = true
  await page.getByRole('tab', { name: 'Conditions', exact: true }).click()
  await page.getByRole('tab', { name: 'Assistant', exact: true }).click()
  await expect.poll(() => restoreStarted).toBe(true)
  await expect(page.getByRole('button', { name: 'Restoring conversation…' })).toBeDisabled()
  await page.getByRole('button', { name: 'New conversation', exact: true }).click()
  const restored = page.waitForResponse('**/api/assistant/sessions/restore-session')
  releaseRestore!()
  await restored
  await expect(page.getByRole('button', { name: 'Ask assistant', exact: true })).toBeEnabled()
  await expect(page.getByText('Retained draft', { exact: true })).toHaveCount(0)
  delayRestore = false
  await page.getByRole('button', { name: 'Ask assistant', exact: true }).click()
  await expect(page.getByText('Retained draft', { exact: true })).toBeVisible()
  let releaseCheck: (() => void) | undefined
  await page.route('**/api/assistant/sessions/restore-session/check', async route => {
    await new Promise<void>(resolve => { releaseCheck = resolve })
    await route.fulfill({ json: { valid: true, context_hash: session.context_hash } })
  })
  let validations = 0
  await page.route('**/api/rules/validate', route => { validations++; return route.fulfill({ json: { valid: true } }) })
  await page.getByRole('button', { name: 'Open draft in rule builder' }).click()
  await expect.poll(() => Boolean(releaseCheck)).toBe(true)
  await page.getByRole('button', { name: 'New conversation', exact: true }).click()
  const checked = page.waitForResponse('**/api/assistant/sessions/restore-session/check')
  releaseCheck!()
  await checked
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())))
  await expect(page.getByText('Retained draft', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Market assistant' })).toBeVisible()
  expect(validations).toBe(0)
})
