import { expect, test, type Page, type Route } from '@playwright/test'
import { preparePage } from './support/workstationHarness'

const INITIAL_SYMBOL = 'XRP/USDT'
const A_SYMBOL = 'WORKSPACE_A_ONLY'
const B_SYMBOL = 'WORKSPACE_B_ONLY'
const NORMAL_SYMBOL = 'WORKSPACE_NORMAL_CONTROL'

type Reply = { status: number; body: unknown }
type WorkspaceHandler = (slug: string, route: Route) => Promise<void>

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function workspaceDoc(slug: string, symbol: string) {
  return { slug, name: `Workspace ${slug.toUpperCase()}`, linked_context: { symbol } }
}

async function installWorkspaceApi(page: Page, handleWorkspace: WorkspaceHandler): Promise<void> {
  await page.route('**/api/workspaces**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'GET' && path === '/api/workspaces') {
      await route.fulfill({ json: [
        { slug: 'a', name: 'Workspace A' },
        { slug: 'b', name: 'Workspace B' },
        { slug: 'normal', name: 'Workspace NORMAL' },
        { slug: 'failure', name: 'Workspace FAILURE' },
      ] })
      return
    }
    const match = path.match(/^\/api\/workspaces\/([^/]+)$/)
    if (route.request().method() === 'GET' && match) {
      await handleWorkspace(decodeURIComponent(match[1]), route)
      return
    }
    await route.fulfill({ status: 404, json: { message: 'Unexpected workspace request' } })
  })
}

async function openSavedWorkspaces(page: Page): Promise<void> {
  await page.evaluate(() => { window.location.hash = '#page=settings&pane=Workspaces' })
  await expect(page.locator('.workspace-list')).toBeVisible()
}

async function navigateOverview(page: Page): Promise<void> {
  await page.evaluate(() => { window.location.hash = '#page=overview' })
  await expect(page.locator('.workspace-list')).toHaveCount(0)
}

async function settleRenderedResponse(page: Page): Promise<void> {
  await page.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  }))
}

function currentContext(page: Page) {
  return page.locator('.workspace-current')
}

async function fulfill(route: Route, reply: Reply): Promise<void> {
  await route.fulfill({ status: reply.status, json: reply.body })
}

test('a delayed older workspace success cannot replace the faster newer selection', async ({ page }) => {
  const aStarted = deferred<void>()
  const aReply = deferred<Reply>()
  const aDelivered = deferred<void>()

  await preparePage(page)
  await installWorkspaceApi(page, async (slug, route) => {
    if (slug === 'a') {
      aStarted.resolve()
      await fulfill(route, await aReply.promise)
      aDelivered.resolve()
      return
    }
    await fulfill(route, { status: 200, body: workspaceDoc(slug, B_SYMBOL) })
  })
  await openSavedWorkspaces(page)

  await page.getByRole('button', { name: 'Workspace A', exact: true }).click()
  await aStarted.promise
  await page.getByRole('button', { name: 'Workspace B', exact: true }).click()
  await expect(currentContext(page)).toContainText(B_SYMBOL)

  const aResponse = page.waitForResponse((response) => response.url().endsWith('/api/workspaces/a'))
  aReply.resolve({ status: 200, body: workspaceDoc('a', A_SYMBOL) })
  await Promise.all([aDelivered.promise, aResponse])
  await settleRenderedResponse(page)
  await expect(currentContext(page)).toContainText(B_SYMBOL)
  await expect(currentContext(page)).not.toContainText(A_SYMBOL)
})

test('a delayed older workspace error cannot replace the newer selection or report a stale error', async ({ page }) => {
  const aStarted = deferred<void>()
  const aReply = deferred<Reply>()
  const aDelivered = deferred<void>()

  await preparePage(page)
  await installWorkspaceApi(page, async (slug, route) => {
    if (slug === 'a') {
      aStarted.resolve()
      await fulfill(route, await aReply.promise)
      aDelivered.resolve()
      return
    }
    await fulfill(route, { status: 200, body: workspaceDoc(slug, B_SYMBOL) })
  })
  await openSavedWorkspaces(page)

  await page.getByRole('button', { name: 'Workspace A', exact: true }).click()
  await aStarted.promise
  await page.getByRole('button', { name: 'Workspace B', exact: true }).click()
  await expect(currentContext(page)).toContainText(B_SYMBOL)

  const aResponse = page.waitForResponse((response) => response.url().endsWith('/api/workspaces/a'))
  aReply.resolve({ status: 503, body: { message: 'Synthetic stale workspace failure' } })
  await Promise.all([aDelivered.promise, aResponse])
  await settleRenderedResponse(page)
  await expect(currentContext(page)).toContainText(B_SYMBOL)
  await expect(page.locator('.workspace-error')).toHaveCount(0)
})

test('a pending workspace load cannot restore context after navigation unmounts the panel', async ({ page }) => {
  const aStarted = deferred<void>()
  const aReply = deferred<Reply>()
  const aDelivered = deferred<void>()

  await preparePage(page)
  await installWorkspaceApi(page, async (slug, route) => {
    if (slug === 'a') {
      aStarted.resolve()
      await fulfill(route, await aReply.promise)
      aDelivered.resolve()
      return
    }
    await fulfill(route, { status: 200, body: workspaceDoc(slug, B_SYMBOL) })
  })
  await openSavedWorkspaces(page)

  await page.getByRole('button', { name: 'Workspace A', exact: true }).click()
  await aStarted.promise
  await navigateOverview(page)

  const aResponse = page.waitForResponse((response) => response.url().endsWith('/api/workspaces/a'))
  aReply.resolve({ status: 200, body: workspaceDoc('a', A_SYMBOL) })
  await Promise.all([aDelivered.promise, aResponse])
  await settleRenderedResponse(page)

  await openSavedWorkspaces(page)
  await expect(currentContext(page)).toContainText(INITIAL_SYMBOL)
  await expect(currentContext(page)).not.toContainText(A_SYMBOL)
})

test('normal workspace loads restore context and current load errors stay visible', async ({ page }) => {
  await preparePage(page)
  await installWorkspaceApi(page, async (slug, route) => {
    if (slug === 'failure') {
      await fulfill(route, { status: 503, body: { message: 'Synthetic workspace service unavailable' } })
      return
    }
    await fulfill(route, { status: 200, body: workspaceDoc(slug, NORMAL_SYMBOL) })
  })
  await openSavedWorkspaces(page)

  await page.getByRole('button', { name: 'Workspace NORMAL', exact: true }).click()
  await expect(currentContext(page)).toContainText(NORMAL_SYMBOL)
  await page.getByRole('button', { name: 'Workspace FAILURE', exact: true }).click()
  await expect(page.locator('.workspace-error')).toContainText('Synthetic workspace service unavailable')
  await expect(currentContext(page)).toContainText(NORMAL_SYMBOL)
})
