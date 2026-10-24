import react from '@vitejs/plugin-react'
import { expect, test } from '@playwright/test'
import { build } from 'vite'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const harness = resolve(frontend, 'e2e/fixtures/run-investigation-race-harness.tsx')
let outputDirectory = ''
let harnessBundle = ''

interface PanelRaceController {
  ready: boolean
  ids: {parent: string; child: string; created: string}
  holdNext(key: string): void
  pendingCount(key: string): number
  select(id: string): Promise<void>
  selectAndResolve(id: string, key: string, outcome?: 'success' | 'error'): Promise<void>
  startAndResolve(key: string, outcome?: 'success' | 'error'): Promise<void>
  unmountAndResolve(key: string): Promise<void>
}

declare global {
  interface Window { __panelRace: PanelRaceController }
}

test.beforeAll(async () => {
  outputDirectory = await mkdtemp(resolve(tmpdir(), 'alpha-investigation-race-'))
  await build({
    configFile: false,
    root: frontend,
    mode: 'development',
    define: {'process.env.NODE_ENV': JSON.stringify('development')},
    plugins: [react()],
    build: {
      emptyOutDir: true,
      outDir: outputDirectory,
      lib: {entry: harness, name: 'RunInvestigationRaceHarness', formats: ['iife'], fileName: 'race-harness.js'},
    },
  })
  harnessBundle = resolve(outputDirectory, 'race-harness.js.iife.js')
})

test.afterAll(async () => {
  if (outputDirectory) await rm(outputDirectory, {recursive: true, force: true})
})

async function mountPanel(page: import('@playwright/test').Page): Promise<string[]> {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.goto('about:blank')
  await page.addScriptTag({path: harnessBundle})
  await page.waitForFunction(() => {
    const race = window.__panelRace
    return race?.ready && race.pendingCount('parent-investigation') > 0
  }, null, {timeout: 3_000}).catch(async () => {
    const state = await page.evaluate(() => {
      const race = window.__panelRace
      return {ready: race?.ready, pending: race?.pendingCount('parent-investigation'), text: document.body.innerText}
    })
    throw new Error(`Harness did not hold parent poll: ${JSON.stringify(state)}; page errors: ${pageErrors.join(' | ')}`)
  })
  return pageErrors
}

test('@reference-only a parent poll success cannot restore the prior saved investigation', async ({page}) => {
  await mountPanel(page)
  await page.evaluate(async () => {
    const race = window.__panelRace
    await race.selectAndResolve(race.ids.child, race.ids.parent)
  })
  const select = page.getByLabel('Saved investigations')
  await expect(select).toHaveValue('child-investigation')
  await expect(page.locator('[role="status"]').filter({hasText: /^ready · cutoff/})).toBeVisible()
})

test('@reference-only a stale parent poll error is ignored after selecting its child', async ({page}) => {
  await mountPanel(page)
  await page.evaluate(async () => {
    const race = window.__panelRace
    await race.selectAndResolve(race.ids.child, race.ids.parent, 'error')
  })
  await expect(page.getByLabel('Saved investigations')).toHaveValue('child-investigation')
  await expect(page.getByText('Status temporarily unavailable; retrying. stale parent poll failure')).toHaveCount(0)
})

test('@reference-only a rapid select-back rejects an in-flight child poll', async ({page}) => {
  await mountPanel(page)
  await page.evaluate(async () => {
    const race = window.__panelRace
    race.holdNext(race.ids.child)
    await race.select(race.ids.child)
  })
  await page.waitForFunction(() => {
    const race = window.__panelRace
    return Boolean(race && race.pendingCount(race.ids.child) > 0)
  })
  await page.evaluate(async () => {
    const race = window.__panelRace
    await race.selectAndResolve(race.ids.parent, race.ids.child)
  })
  await expect(page.getByLabel('Saved investigations')).toHaveValue('parent-investigation')
  await expect(page.locator('[role="status"]').filter({hasText: /^completed · cutoff/})).toBeVisible()
})

test('@reference-only starting a new case invalidates the prior poll', async ({page}) => {
  await mountPanel(page)
  await page.evaluate(async () => {
    const race = window.__panelRace
    race.holdNext('create')
    await race.startAndResolve(race.ids.parent)
  })
  await expect(page.getByLabel('Saved investigations')).toHaveValue('created-investigation')
})

test('@reference-only a stale parent poll error is ignored after starting a new case', async ({page}) => {
  await mountPanel(page)
  await page.evaluate(async () => {
    const race = window.__panelRace
    race.holdNext('create')
    await race.startAndResolve(race.ids.parent, 'error')
  })
  await expect(page.getByLabel('Saved investigations')).toHaveValue('created-investigation')
  await expect(page.getByText('Status temporarily unavailable; retrying. stale parent poll failure')).toHaveCount(0)
})

test('@reference-only unmount invalidates an unresolved parent poll', async ({page}) => {
  const pageErrors = await mountPanel(page)
  await page.evaluate(async () => {
    const race = window.__panelRace
    await race.unmountAndResolve(race.ids.parent)
  })
  await expect(page.locator('section[aria-label="Run investigation"]')).toHaveCount(0)
  expect(pageErrors).toEqual([])
})
