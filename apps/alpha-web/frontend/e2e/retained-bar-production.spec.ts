import { expect, test, type Page } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { once } from 'node:events'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

// No browser request interception: load the production SPA and actual HTTP API directly.
let fixture: ChildProcess
let endpoint = ''
let ids: Record<string, string>
const root = resolve(process.cwd(), '../../..')

test.beforeAll(async () => {
  let errors = ''
  fixture = spawn(process.env.ALPHA_TEST_PYTHON ?? resolve(root, '.venv/bin/python'),
    [resolve(root, 'tests/fixtures/retained_coverage_web_fixture.py'), 'serve'],
    {cwd: root, env: process.env, stdio: ['ignore', 'pipe', 'pipe']})
  fixture.stderr!.on('data', body => { errors += String(body) })
  const ready = await new Promise<{port: number; ids: Record<string, string>}>((accept, reject) => {
    let text = ''
    const timeout = setTimeout(() => reject(new Error(`Disposable retained fixture not ready: ${errors}`)), 15000)
    fixture.once('error', reject)
    fixture.once('exit', code => { clearTimeout(timeout); reject(new Error(`Fixture exited ${code}: ${errors}`)) })
    fixture.stdout!.on('data', body => {
      text += String(body)
      if (text.includes('\n')) { clearTimeout(timeout); accept(JSON.parse(text.split('\n')[0])) }
    })
  })
  endpoint = `http://localhost:${ready.port}`
  ids = ready.ids
  const metadata = await (await fetch(endpoint+'/__fixture/retained-coverage')).json()
  expect(metadata).toMatchObject({synthetic: true, ids})
  for (const resource of ['catalog', 'capabilities', 'asset-masters', 'storage', 'coverage', 'features', 'profiles', 'batches']) {
    const response = await fetch(endpoint+'/api/crypto-data/'+resource)
    expect(response.ok, `${resource}: ${await response.text()}`).toBe(true)
  }
})

test.afterAll(async () => {
  if (fixture?.exitCode === null) { fixture.kill('SIGTERM'); await once(fixture, 'exit') }
})

async function openProductionQuality(page: Page) {
  await page.goto(endpoint)
  await page.getByLabel('Market profile').selectOption('crypto')
  await page.goto(endpoint+'/#page=data&pane=FundingData')
  const center = page.getByRole('region', {name: 'Crypto Data Center'})
  await expect(center).toBeVisible()
  await center.getByRole('tab', {name: 'CEX History', exact: true}).click()
  const card = center.locator('.crypto-dataset:visible').filter({has: page.getByText('BTCUSDT', {exact: true})})
  await card.getByRole('button', {name: 'Quality', exact: true}).click()
  const panel = page.getByRole('region', {name: 'Retained daily bar coverage'})
  await expect(panel).toBeVisible()
  return {center, panel}
}

async function fillGrid(page: Page, cap = '1000000') {
  await page.getByLabel('Coverage start (ISO UTC)', {exact: true}).fill('2024-01-01T00:00:00Z')
  await page.getByLabel('Coverage end exclusive (ISO UTC)', {exact: true}).fill('2024-01-05T00:00:00Z')
  await page.getByLabel('Closure cutoff as_of (ISO UTC)', {exact: true}).fill('2024-01-05T00:00:00Z')
  await page.getByLabel('Maximum artifact hash bytes', {exact: true}).fill(cap)
}

test('production-served bundle and real retained API show exact gaps without mutation or provider calls', async ({page}, info) => {
  test.setTimeout(90000)
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  const {panel} = await openProductionQuality(page)
  const localIndex = await readFile(resolve(root, 'apps/alpha-web/src/alpha_web/static/app/index.html'))
  const servedIndex = await (await fetch(endpoint)).arrayBuffer()
  expect(createHash('sha256').update(Buffer.from(servedIndex)).digest('hex'))
    .toBe(createHash('sha256').update(localIndex).digest('hex'))
  const assetUrls = await page.locator('script[type="module"][src]').evaluateAll(nodes => nodes.map(node => (node as HTMLScriptElement).src))
  expect(assetUrls.length).toBeGreaterThan(0)
  for (const url of assetUrls) {
    expect(new URL(url).origin).toBe(endpoint)
    const file = resolve(root, 'apps/alpha-web/src/alpha_web', new URL(url).pathname.slice(1))
    const local = await readFile(file)
    const served = Buffer.from(await (await fetch(url)).arrayBuffer())
    expect(createHash('sha256').update(served).digest('hex')).toBe(createHash('sha256').update(local).digest('hex'))
  }
  const before = await (await fetch(endpoint+'/__fixture/retained-coverage')).json()
  expect(before.commands.filter((args: string[]) => args.includes('--coverage-start'))).toHaveLength(0)
  await fillGrid(page)
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await expect(panel.getByText('2 covered / 4 expected slots · 2 missing slots.')).toBeVisible()
  await expect(panel.getByText('Stored quality remains qualified; it has not been rewritten.')).toBeVisible()
  await expect(panel.getByText(/Provider-history completeness and PIT eligibility: unproven/)).toBeVisible()
  const table = panel.getByRole('table', {name: 'Missing declared daily intervals'})
  await expect(table.locator('tbody tr')).toHaveCount(2)
  const after = await (await fetch(endpoint+'/__fixture/retained-coverage')).json()
  expect(after.fingerprint).toEqual(before.fingerprint)
  expect(after.commands.filter((args: string[]) => args.includes('--coverage-start'))).toHaveLength(1)
  expect(after.commands.every((args: string[]) => !args.includes('acquire') && !args.includes('check'))).toBe(true)
  expect(pageErrors).toEqual([])
  await table.scrollIntoViewIfNeeded()
  await page.screenshot({path: info.outputPath('production-retained-gaps.png')})
  await info.attach('served-bundle.json', {body: JSON.stringify({endpoint, ids, assetUrls, index_sha256: createHash('sha256').update(localIndex).digest('hex')}), contentType:'application/json'})
})

test('production retained inspection reports limits and real validation errors and resets selected identity', async ({page}) => {
  test.setTimeout(90000)
  const {center, panel} = await openProductionQuality(page)
  await fillGrid(page, '1')
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await expect(panel.getByText(/Retained evidence unavailable or unverifiable/)).toBeVisible()
  await fillGrid(page)
  await page.getByLabel('Closure cutoff as_of (ISO UTC)', {exact: true}).fill('2024-01-01T00:00:00Z')
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await expect(panel.getByRole('alert')).toBeVisible()
  await fillGrid(page)
  const request = page.waitForRequest(request => request.url().endsWith('/retained-coverage'))
  await panel.getByRole('button', {name: 'Inspect retained grid', exact: true}).click()
  await request
  const eth = center.locator('.crypto-dataset:visible').filter({has: page.getByText('ETHUSDT', {exact: true})})
  await eth.getByRole('button', {name: 'Quality', exact: true}).click()
  await expect(panel.getByLabel('Coverage start (ISO UTC)', {exact: true})).toHaveValue('')
  await expect(panel.getByLabel('Maximum artifact hash bytes', {exact: true})).toHaveValue('')
  await expect(panel.getByLabel('Retained grid result')).toHaveCount(0)
  await expect(panel.getByRole('alert')).toHaveCount(0)
  const invalid = await page.request.post(endpoint+'/api/crypto-data/quality/invalid/retained-coverage', {data: {
    coverage_start:'2024-01-01T00:00:00Z', coverage_end:'2024-01-05T00:00:00Z',
    as_of:'2024-01-05T00:00:00Z', expected_cadence_seconds:86400,max_verify_artifact_bytes:1000000,
  }})
  expect(invalid.status()).toBe(422)
})
