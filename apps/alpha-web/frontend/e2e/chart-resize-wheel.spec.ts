import { expect, test } from '@playwright/test'
import { preparePage } from './support/workstationHarness'

interface ResizeOrdering {
  pendingResize: () => number
  flushResize: () => void
  release: () => Promise<void>
  wheelDelivered: () => number
}

test('one wheel zoom survives a resize restoration pending in the same draw', async ({ page }) => {
  const candles = { 'XRP/USDT': Array.from({ length: 500 }, (_, i) => ({ t: 1700000000 + i * 86400, o: 100 + i, h: 102 + i, l: 99 + i, c: 101 + i, v: 1000 })) }
  await preparePage(page, { candles })
  await page.goto('/#page=data&pane=PriceChart')
  await page.getByLabel('Plot renderer').selectOption('market')
  const host = page.locator('.price-host')
  await expect.poll(() => host.getAttribute('data-visible-range')).not.toBeNull()
  await host.hover()
  // Let the initial draw complete before controlling only the resize/gesture ordering.
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())))
  const initial = JSON.parse((await host.getAttribute('data-visible-range'))!) as { from: number; to: number }
  const initialSpan = initial.to - initial.from
  await host.evaluate(node => {
    const nativeFrame = window.requestAnimationFrame.bind(window)
    const nativeTimeout = window.setTimeout.bind(window)
    const frames: FrameRequestCallback[] = [], timers: (() => void)[] = []
    let delivered = 0
    node.addEventListener('wheel', event => { if (event.isTrusted) delivered++ }, { capture: true })
    window.requestAnimationFrame = callback => { frames.push(callback); return frames.length }
    window.setTimeout = ((handler: TimerHandler, delay?: number, ...args: unknown[]) => {
      if (delay === 80 && typeof handler === 'function') { timers.push(() => handler(...args)); return -timers.length }
      return nativeTimeout(handler, delay, ...args)
    }) as typeof window.setTimeout
    ;(window as unknown as { resizeOrdering: ResizeOrdering }).resizeOrdering = {
      pendingResize: () => timers.length,
      flushResize: () => {
        const resize = timers.shift(); if (!resize) throw new Error('ResizeObserver did not schedule chart resize'); resize()
        const chart = node.querySelector<HTMLElement>('.tv-lightweight-charts')!
        let count = 0
        while (Math.abs(chart.clientHeight - node.clientHeight) > 1) { const frame = frames.shift(); if (!frame || ++count > 30) throw new Error('Chart resize did not run'); frame(performance.now()) }
        if (!count) throw new Error('Resize callback did not run before the gesture')
      },
      wheelDelivered: () => delivered,
      release: () => new Promise<void>(resolve => { window.requestAnimationFrame = nativeFrame; window.setTimeout = nativeTimeout; for (const frame of frames.splice(0)) nativeFrame(frame); nativeFrame(() => nativeFrame(() => resolve())) }),
    }
    const height = node.clientHeight
    ;(node as HTMLElement).style.flex = 'none'
    ;(node as HTMLElement).style.height = `${height - 34}px`
  })
  await expect.poll(() => page.evaluate(() => (window as unknown as { resizeOrdering: ResizeOrdering }).resizeOrdering.pendingResize())).toBeGreaterThan(0)
  await page.evaluate(() => (window as unknown as { resizeOrdering: ResizeOrdering }).resizeOrdering.flushResize())
  // Exactly one trusted gesture occurs after resize scheduling and before its queued draw.
  await page.mouse.wheel(0, -600)
  await expect.poll(() => page.evaluate(() => (window as unknown as { resizeOrdering: ResizeOrdering }).resizeOrdering.wheelDelivered())).toBe(1)
  await page.evaluate(() => (window as unknown as { resizeOrdering: ResizeOrdering }).resizeOrdering.release())
  await expect.poll(async () => { const range = JSON.parse((await host.getAttribute('data-visible-range'))!) as { from: number; to: number }; return range.to - range.from }).toBeLessThan(initialSpan - 20)
})
