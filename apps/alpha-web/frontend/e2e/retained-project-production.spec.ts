import { expect, test, type Page, type Request, type Response } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { once } from 'node:events'
import { resolve } from 'node:path'

let fixture: ChildProcess
let endpoint = ''
let projects: Record<string, string>
let ids: Record<string, string>
const root = resolve(process.cwd(), '../../..')

test.beforeAll(async () => {
  let errors = ''
  fixture = spawn(process.env.ALPHA_TEST_PYTHON ?? resolve(root, '.venv/bin/python'),
    [resolve(root, 'tests/fixtures/retained_coverage_web_fixture.py'), 'serve-projects'],
    {cwd:root,env:process.env,stdio:['ignore','pipe','pipe']})
  fixture.stderr!.on('data', data => { errors += String(data) })
  const ready = await new Promise<{port:number;projects:Record<string,string>;ids:Record<string,string>}>((accept,reject) => {
    let body = ''
    const timer = setTimeout(() => reject(new Error(`Project fixture unavailable: ${errors}`)),15000)
    fixture.once('error',reject)
    fixture.once('exit', code => {clearTimeout(timer);reject(new Error(`Fixture exited ${code}: ${errors}`))})
    fixture.stdout!.on('data', data => {
      body += String(data)
      if(body.includes('\n')){clearTimeout(timer);accept(JSON.parse(body.split('\n')[0]))}
    })
  })
  endpoint = `http://localhost:${ready.port}`;projects=ready.projects;ids=ready.ids
  const metadata = await (await fetch(endpoint+'/__fixture/retained-coverage')).json()
  expect(metadata).toMatchObject({synthetic:true,projects,ids})
  for(const route of ['/api/projects?limit=50&offset=0','/api/research/cases?limit=50&offset=0',
    `/api/research/cases/${projects.A}`,`/api/research/cases/${projects.B}`]) {
    const response=await fetch(endpoint+route)
    expect(response.ok, await response.text()).toBe(true)
  }
})

test.afterAll(async()=>{
  if(fixture?.exitCode===null){fixture.kill('SIGTERM');await once(fixture,'exit')}
})

async function grid(page: Page, cap='1000000') {
  await page.getByLabel('Coverage start (ISO UTC)',{exact:true}).fill('2024-01-01T00:00:00Z')
  await page.getByLabel('Coverage end exclusive (ISO UTC)',{exact:true}).fill('2024-01-05T00:00:00Z')
  await page.getByLabel('Closure cutoff as_of (ISO UTC)',{exact:true}).fill('2024-01-05T00:00:00Z')
  await page.getByLabel('Maximum artifact hash bytes',{exact:true}).fill(cap)
}

// Bootstrap proves the browser's initial inventory responses completed. It is not a
// revision barrier; the visible loading and option assertions still check UI readiness.
async function openProjectPage(page: Page, selectCrypto: boolean) {
  await new Promise<void>((resolveReady, reject) => {
    const pending = new Set(['/api/projects', '/api/research/cases'].map(path =>
      `${endpoint}${path}?limit=50&offset=0`))
    const captured = new Set<string>()
    let active = true
    let navigated = false
    const finish = (error?: Error) => {
      if (!active || (!error && (!navigated || pending.size))) return
      active = false
      clearTimeout(timer)
      page.off('response', onResponse)
      page.off('requestfailed', onRequestFailed)
      page.off('close', onClose)
      if (error) reject(error)
      else resolveReady()
    }
    const onResponse = (response: Response) => {
      const url = response.url()
      if (!active || response.request().method() !== 'GET' || !pending.has(url) || captured.has(url)) return
      captured.add(url)
      if (!response.ok()) {
        finish(new Error(`Project bootstrap HTTP ${response.status()}: ${url}`))
        return
      }
      void response.finished().then(error => {
        if (!active) return
        if (error) finish(new Error(`Project bootstrap response failed: ${url}: ${error.message}`))
        else { pending.delete(url); finish() }
      }).catch(error => finish(new Error(`Project bootstrap response failed: ${url}: ${String(error)}`)))
    }
    const onRequestFailed = (request: Request) => {
      if (request.method() === 'GET' && pending.has(request.url())) {
        finish(new Error(`Project bootstrap request failed: ${request.url()}: ${request.failure()?.errorText}`))
      }
    }
    const onClose = () => finish(new Error('Page closed during project inventory bootstrap'))
    const timer = setTimeout(() => finish(new Error('Initial project inventory bootstrap exceeded 15000ms')), 15_000)
    page.on('response', onResponse)
    page.on('requestfailed', onRequestFailed)
    page.on('close', onClose)
    void (async () => {
      await page.goto(endpoint)
      if (!active) return
      if (selectCrypto) await page.getByLabel('Market profile').selectOption('crypto')
      if (!active) return
      navigated = true
      finish()
    })().catch(error => finish(new Error(`Project bootstrap navigation/profile failed: ${String(error)}`)))
  })
}

test('ready synthetic project selection and retained quality journey clear project and manifest results',async({page},info)=>{
  test.setTimeout(90000)
  await openProjectPage(page, true)
  const picker=page.getByLabel('Project context',{exact:true})
  await expect(page.getByText('Loading projects…',{exact:true})).toHaveCount(0)
  await expect(picker.getByRole('option',{name:'Synthetic coverage A',exact:true})).toHaveCount(1)
  await expect(picker.getByRole('option',{name:'Synthetic coverage B',exact:true})).toHaveCount(1)
  await expect(page.getByRole('button',{name:'Project inventory failed',exact:true})).toHaveCount(0)
  await picker.selectOption(projects.A)
  await page.goto(endpoint+'/#page=data&pane=FundingData')
  await expect(picker).toHaveValue(projects.A)
  const center=page.getByRole('region',{name:'Crypto Data Center'})
  await center.getByRole('tab',{name:'CEX History',exact:true}).click()
  await center.locator('.crypto-dataset:visible').filter({has:page.getByText('BTCUSDT',{exact:true})})
    .getByRole('button',{name:'Quality',exact:true}).click()
  const panel=page.getByRole('region',{name:'Retained daily bar coverage'})
  const before=await(await fetch(endpoint+'/__fixture/retained-coverage')).json()
  const projectsBefore=await(await fetch(endpoint+'/api/projects?limit=50&offset=0')).json()
  await grid(page)
  await panel.getByRole('button',{name:'Inspect retained grid',exact:true}).click()
  await expect(panel.getByText('2 covered / 4 expected slots · 2 missing slots.')).toBeVisible()
  await expect(page.getByText('DATA EXPLORER UNAVAILABLE',{exact:true})).toHaveCount(0)
  await panel.getByRole('table',{name:'Missing declared daily intervals'}).scrollIntoViewIfNeeded()
  await page.screenshot({path:info.outputPath('ready-project-retained-gaps.png')})
  await picker.selectOption(projects.B)
  await expect(panel.getByLabel('Retained grid result')).toHaveCount(0)
  // Existing App pane key remounts the whole view; reselecting a manifest is explicit.
  await expect(panel).toHaveCount(0)
  await center.getByRole('tab',{name:'CEX History',exact:true}).click()
  await center.locator('.crypto-dataset:visible').filter({has:page.getByText('BTCUSDT',{exact:true})})
    .getByRole('button',{name:'Quality',exact:true}).click()
  await expect(panel.getByLabel('Coverage start (ISO UTC)',{exact:true})).toHaveValue('')
  await expect(panel.getByLabel('Maximum artifact hash bytes',{exact:true})).toHaveValue('')
  await grid(page,'1')
  await panel.getByRole('button',{name:'Inspect retained grid',exact:true}).click()
  await expect(panel.getByText(/Retained evidence unavailable or unverifiable/)).toBeVisible()
  const eth=center.locator('.crypto-dataset:visible').filter({has:page.getByText('ETHUSDT',{exact:true})})
  await eth.getByRole('button',{name:'Quality',exact:true}).click()
  await expect(panel.getByText(/Retained evidence unavailable or unverifiable/)).toHaveCount(0)
  await expect(panel.getByLabel('Coverage start (ISO UTC)',{exact:true})).toHaveValue('')
  const after=await(await fetch(endpoint+'/__fixture/retained-coverage')).json()
  expect(after.retained_fingerprint).toEqual(before.retained_fingerprint)
  const projectsAfter=await(await fetch(endpoint+'/api/projects?limit=50&offset=0')).json()
  expect(projectsAfter).toEqual(projectsBefore)
  expect(after.commands.every((args:string[])=>!args.includes('acquire')&&!args.includes('check')&&!args.includes('capture'))).toBe(true)
})


test('real project inventory errors finish loading and retry recovers the supported synthetic store', async({page})=>{
  test.setTimeout(90000)
  await openProjectPage(page, false)
  const picker=page.getByLabel('Project context',{exact:true})
  await expect(page.getByText('Loading projects…',{exact:true})).toHaveCount(0)
  await expect(picker.getByRole('option',{name:'Synthetic coverage A',exact:true})).toHaveCount(1)
  const fault=await page.request.post(endpoint+'/__fixture/project-inventory?unavailable=true')
  expect(fault.ok()).toBe(true)
  expect((await fault.json()).project_inventory_unavailable).toBe(true)
  expect((await page.request.get(endpoint+'/api/projects?limit=50&offset=0')).status()).toBe(422)
  // Default profile is already crypto; force a real supported refresh and finish in crypto.
  await page.getByLabel('Market profile').selectOption('equities')
  await page.getByLabel('Market profile').selectOption('crypto')
  const error=page.getByRole('button',{name:'Project inventory failed',exact:true})
  await expect(error).toBeVisible()
  await expect(page.getByText('Loading projects…',{exact:true})).toHaveCount(0)
  const restore=await page.request.post(endpoint+'/__fixture/project-inventory?unavailable=false')
  expect(restore.ok()).toBe(true)
  await error.click()
  await page.getByRole('button',{name:'Retry project inventory',exact:true}).click()
  await expect(picker.getByRole('option',{name:'Synthetic coverage A',exact:true})).toHaveCount(1)
  await expect(picker.getByRole('option',{name:'Synthetic coverage B',exact:true})).toHaveCount(1)
  await expect(page.getByText('Loading projects…',{exact:true})).toHaveCount(0)
  await expect(error).toHaveCount(0)
})
