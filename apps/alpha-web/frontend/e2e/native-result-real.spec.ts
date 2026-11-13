/** Real built SPA + backend + retained native fixture. No route interception. */
import { test, expect } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { readFile, writeFile, mkdir, unlink } from 'node:fs/promises'
import { join } from 'node:path'

interface Fixture { python: string; root: string; job: string; receipt: string; receipt_sha256: string; port: number; server_env: Record<string, string>; evidence: string }
const file = process.env.ALPHA_NATIVE_WEB_FIXTURE
if (!file) throw new Error('Explicit disposable synthetic fixture required; run test_native_result_web.py.')
const fixture = JSON.parse(await readFile(file, 'utf8')) as Fixture
const base = `http://127.0.0.1:${fixture.port}`
const unknown = '00000000-0000-4000-8000-000000000001'
const serverCode = "import sys,uvicorn; from alpha_web.app import create_app; uvicorn.run(create_app(),host='127.0.0.1',port=int(sys.argv[1]),log_level='warning',access_log=False)"
let server: ChildProcess | null = null
let log = ''
async function stop() {
  const current = server
  if (!current) return
  server = null
  if (current.exitCode !== null) return
  await new Promise<void>((resolve, reject) => {
    let forced = false
    const timeout = setTimeout(() => { forced = true; current.kill('SIGKILL') }, 15_000)
    current.once('exit', () => { clearTimeout(timeout); if (forced) reject(new Error('Synthetic backend required forced termination.')); else resolve() })
    current.once('error', error => { clearTimeout(timeout); reject(error) })
    current.kill('SIGTERM')
  })
}
async function start(mode = 'resume') {
  await stop()
  server = spawn(fixture.python, ['-B', '-c', serverCode, String(fixture.port)], {
    cwd: fixture.root, env: { ...fixture.server_env, ALPHA_NATIVE_RESULT_MODE: mode }, stdio: ['ignore', 'pipe', 'pipe'],
  })
  server.stdout?.on('data', chunk => { log += String(chunk) })
  server.stderr?.on('data', chunk => { log += String(chunk) })
  await expect.poll(async () => {
    if (server?.exitCode !== null) throw new Error('Synthetic backend exited before ready.')
    try { return (await fetch(base)).status } catch { return 0 }
  }, { timeout: 20_000 }).toBe(200)
}
test.afterAll(async () => {
  await stop()
  await writeFile(join(fixture.evidence, 'backend.log'), log)
})

test('Research native UUID lookup reads real owner evidence and clears stale state', async ({ page }) => {
  await mkdir(fixture.evidence, { recursive: true })
  await start()
  const receipts: unknown[] = []
  page.on('response', async response => {
    if (response.url().includes('/api/native-jobs/')) {
      try { receipts.push({ url: new URL(response.url()).pathname, http_status: response.status(), body: await response.json() }) } catch { /* Browser may abort a superseded read. */ }
    }
  })
  await page.goto(base + '/#page=research&pane=NativeJobResult')
  const panel = page.getByLabel('Native job result lookup')
  await expect(panel).toBeVisible()
  // The ordinary Research navigation, not a direct-only orphan route.
  await page.getByRole('menuitem', { name: 'View', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Research › Native job result', exact: true }).click()
  await expect(panel).toBeVisible()
  const input = panel.getByLabel('Native job UUID')
  async function lookup(job: string, heading: string) {
    await input.fill(job)
    await panel.getByRole('button', { name: /^(Read result|Retry read)$/ }).click()
    await expect(panel.getByRole('status')).toHaveText('Reading native result…')
    await expect(panel.getByRole('heading', { name: heading, exact: true })).toBeVisible()
  }
  await lookup(fixture.job, 'Completed — verified retained evidence')
  await expect(panel).toContainText(fixture.receipt_sha256)
  await expect(panel).toContainText('-0.125')
  await expect(panel).toContainText('0 actual model calls')
  await expect(panel.locator('ol li')).toHaveCount(5)
  await page.screenshot({ path: join(fixture.evidence, 'completed.png'), fullPage: true })
  await input.fill('../not-a-job')
  await expect(panel.getByRole('heading', { name: 'Completed — verified retained evidence' })).toHaveCount(0)
  await panel.getByRole('button', { name: /^(Read result|Retry read)$/ }).click()
  await expect(panel.getByRole('alert')).toHaveText('Enter a valid native job UUID.')
  await lookup(unknown, 'Evidence unavailable')
  await expect(panel).not.toContainText('-0.125')
  await page.screenshot({ path: join(fixture.evidence, 'unavailable.png'), fullPage: true })
  const original = await readFile(fixture.receipt)
  try {
    await writeFile(fixture.receipt, Buffer.concat([original, Buffer.from(' ')]))
    await lookup(fixture.job, 'Invalid evidence')
    await expect(panel).not.toContainText('-0.125')
    await page.screenshot({ path: join(fixture.evidence, 'invalid.png'), fullPage: true })
    await unlink(fixture.receipt)
    await lookup(fixture.job, 'Evidence unavailable')
  } finally { await writeFile(fixture.receipt, original) }
  // A completed read is superseded while in flight, with no fake server delay/interception.
  await input.fill(fixture.job)
  const pageOrigin = new URL(page.url()).origin // Existing Workstation canonical-host redirect.
  const first = page.waitForRequest(r => r.url() === `${pageOrigin}/api/native-jobs/${fixture.job}/result`)
  await panel.getByRole('button', { name: /^(Read result|Retry read)$/ }).click()
  await first
  await input.fill(unknown)
  await expect(panel.getByLabel('Native result evidence')).toHaveCount(0)
  await panel.getByRole('button', { name: /^(Read result|Retry read)$/ }).click()
  await expect(panel.getByRole('heading', { name: 'Evidence unavailable', exact: true })).toBeVisible()
  await expect(panel).not.toContainText('-0.125')
  // Retry must really contact the backend. Stop owned backend, then restore same fixture.
  await stop()
  await panel.getByRole('button', { name: 'Retry read', exact: true }).click()
  await expect(panel.getByRole('alert')).toHaveText('Native result read failed. Check the local backend and retry.')
  await start()
  await panel.getByRole('button', { name: 'Retry read', exact: true }).click()
  await expect(panel.getByRole('heading', { name: 'Evidence unavailable', exact: true })).toBeVisible()
  await lookup(fixture.job, 'Completed — verified retained evidence')
  // Profile choice remains server-owned; restart configured differently, no UI selector.
  await start('cancel')
  await panel.getByRole('button', { name: 'Retry read', exact: true }).click()
  await expect(panel.getByRole('heading', { name: 'Invalid evidence', exact: true })).toBeVisible()
  await expect(panel).not.toContainText('-0.125')
  await expect(panel.getByRole('button', { name: /launch|resume/i })).toHaveCount(0)
  await writeFile(join(fixture.evidence, 'browser-receipts.json'), JSON.stringify(receipts, null, 2) + '\n')
})
