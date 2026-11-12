import { expect, test, type Page } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { once } from 'node:events'
import { resolve } from 'node:path'
import { preparePage, openDocument } from './support/workstationHarness'

let fixture: ChildProcess
let endpoint = ''
let identities: Record<string, string>
let fixtureErrors = ''

test.beforeAll(async () => {
  const root = resolve(process.cwd(), '../../..')
  fixture = spawn(process.env.ALPHA_TEST_PYTHON ?? resolve(root, '.venv/bin/python'),
    [resolve(root, 'tests/fixtures/retained_coverage_web_fixture.py'), 'serve'],
    { cwd: root, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] })
  fixture.stderr!.on('data', data => { fixtureErrors += String(data) })
  const ready = await new Promise<{port: number; ids: Record<string, string>}>((accept, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`Synthetic fixture failed to start: ${fixtureErrors}`)), 15000)
    fixture.once('error', reject)
    fixture.once('exit', code => { clearTimeout(timer); reject(new Error(`Fixture exited ${code}: ${fixtureErrors}`)) })
    fixture.stdout!.on('data', data => {
      output += String(data)
      if (output.includes('\n')) {
        clearTimeout(timer)
        try { accept(JSON.parse(output.split('\n')[0])) } catch (cause) { reject(cause) }
      }
    })
  })
  endpoint = `http://127.0.0.1:${ready.port}`
  identities = ready.ids
  // Fixture preflight: the actual test server and real seeded immutable manifests must be ready.
  const response = await fetch(`${endpoint}/__fixture/retained-coverage`)
  expect(response.ok).toBe(true)
  expect(await response.json()).toMatchObject({synthetic: true, ids: identities})
})

test.afterAll(async () => {
  if (fixture && fixture.exitCode === null) { fixture.kill('SIGTERM'); await once(fixture, 'exit') }
})

async function openCoverage(page: Page) {
  await preparePage(page)
  await page.route('**/api/crypto-data/coverage', async route => {
    const response = await route.fetch({url: `${endpoint}/api/crypto-data/coverage`})
    const body = await response.json()
    body.items = body.items.filter((item: {manifest_id: string}) => item.manifest_id === identities.gaps)
    body.count = body.items.length
    await route.fulfill({status: response.status(), json: body})
  })
  await page.route('**/api/crypto-data/quality/**', async route => {
    const path = new URL(route.request().url()).pathname
    const response = await route.fetch({url: endpoint + path})
    await route.fulfill({response})
  })
  await openDocument(page, 'Funding')
  await page.getByRole('tab', {name: 'CEX History', exact: true}).click()
  const card = page.locator('.crypto-dataset:visible').filter({has: page.getByText('BTCUSDT', {exact: true})}).first()
  await expect(card.getByRole('button', {name: 'Quality', exact: true})).toBeVisible()
  // Select the actual retained manifest; all quality responses here come from the real CLI.
  await card.getByRole('button', {name: 'Quality', exact: true}).click()
  const panel = page.getByRole('region', {name: 'Retained daily bar coverage'})
  await expect(panel).toBeVisible()
  return panel
}

async function fillGrid(page: Page) {
  await page.getByLabel('Coverage start (ISO UTC)', {exact: true}).fill('2024-01-01T00:00:00Z')
  await page.getByLabel('Coverage end exclusive (ISO UTC)', {exact: true}).fill('2024-01-05T00:00:00Z')
  await page.getByLabel('Closure cutoff as_of (ISO UTC)', {exact: true}).fill('2024-01-05T00:00:00Z')
  await page.getByLabel('Maximum artifact hash bytes', {exact: true}).fill('1000000')
}

test('retained quality selection evaluates real bytes and renders explicit grid evidence', async ({page}, info) => {
  const before = await (await fetch(`${endpoint}/__fixture/retained-coverage`)).json()
  const panel = await openCoverage(page)
  let evaluations = 0
  page.on('request', request => { if (request.url().endsWith('/retained-coverage')) evaluations++ })
  expect(evaluations).toBe(0)
  await fillGrid(page)
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await expect(panel.getByLabel('Retained grid result')).toBeVisible()
  await expect(panel.getByText(/Provider-history completeness and PIT eligibility: unproven/)).toBeVisible()
  await expect(panel.getByText('2 covered / 4 expected slots · 2 missing slots.')).toBeVisible()
  await expect(panel.getByRole('table', {name: 'Missing declared daily intervals'})).toBeVisible()
  await expect(panel.getByText(/Stored quality remains/)).toBeVisible()
  await expect(panel.getByText(/Source evidence was retrieved after/)).toBeVisible()
  expect(evaluations).toBe(1)
  const after = await (await fetch(`${endpoint}/__fixture/retained-coverage`)).json()
  expect(after.fingerprint).toEqual(before.fingerprint)
  await panel.screenshot({path: info.outputPath('retained-grid-controls.png')})
  await panel.getByRole('table', {name: 'Missing declared daily intervals'}).scrollIntoViewIfNeeded()
  await page.screenshot({path: info.outputPath('retained-grid-result.png')})
})

test('unavailable, request error and stop-waiting states never retain a stale success', async ({page}) => {
  const panel = await openCoverage(page)
  await fillGrid(page)
  await page.getByLabel('Maximum artifact hash bytes', {exact: true}).fill('1')
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await expect(panel.getByText(/Retained evidence unavailable or unverifiable/)).toBeVisible()
  await expect(panel.getByLabel('Retained grid result')).toHaveCount(0)
  await page.route('**/retained-coverage', route => route.fulfill({status: 503, json: {detail: 'fixture failure'}}))
  await page.getByLabel('Maximum artifact hash bytes', {exact: true}).fill('1000000')
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await expect(panel.getByRole('alert')).toBeVisible()
  let release!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  await page.route('**/retained-coverage', async route => {
    await held
    await route.fulfill({status: 503, json: {detail: 'late fixture failure'}})
  })
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await expect(panel.getByText('Inspecting retained evidence…')).toBeVisible()
  await panel.getByRole('button', {name: 'Stop waiting', exact: true}).click()
  await expect(panel.getByText(/Stopped waiting; the server inspection may still finish/)).toBeVisible()
  release()
  await expect(panel.getByRole('alert')).toHaveCount(0)
  await expect(panel.getByLabel('Retained grid result')).toHaveCount(0)
})

test('selecting another retained manifest resets inputs and ignores the old pending result', async ({page}) => {
  const panel = await openCoverage(page)
  await fillGrid(page)
  let release!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  let evaluated!: () => void
  const finished = new Promise<void>(resolve => { evaluated = resolve })
  await page.route('**/retained-coverage', async route => {
    const path = new URL(route.request().url()).pathname
    const response = await route.fetch({url: endpoint + path})
    evaluated()
    await held
    await route.fulfill({response})
  })
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await finished
  await page.route('**/api/crypto-data/coverage', async route => {
    const response = await route.fetch({url: `${endpoint}/api/crypto-data/coverage`})
    const body = await response.json()
    body.items = body.items.filter((item: {manifest_id: string}) => item.manifest_id === identities.full)
    body.count = body.items.length
    await route.fulfill({status: response.status(), json: body})
  })
  await page.getByRole('tab', {name: 'CEX History', exact: true}).click()
  const center = page.getByRole('region', {name: 'Crypto Data Center'})
  await center.getByRole('button', {name: 'Refresh', exact: true}).click()
  const card = center.locator('.crypto-dataset:visible').filter({hasText: '4 rows'})
  await expect(card).toHaveCount(1)
  await card.getByRole('button', {name: 'Quality', exact: true}).click()
  await expect(panel.getByLabel('Coverage start (ISO UTC)', {exact: true})).toHaveValue('')
  await expect(panel.getByLabel('Maximum artifact hash bytes', {exact: true})).toHaveValue('')
  release()
  await expect(panel.getByLabel('Retained grid result')).toHaveCount(0)
  await expect(panel.getByRole('alert')).toHaveCount(0)
})
