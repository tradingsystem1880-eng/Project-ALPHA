import { expect, it, vi } from 'vitest'
import { cancelChartResize, scheduleChartResize, cancelChartRange, scheduleChartRange } from './chartResize'
it('spreads simultaneous plot relayouts across frames and cancels disposed plots', () => {
  const frames: (() => void)[] = []
  vi.stubGlobal('requestAnimationFrame', (f: () => void) => { frames.push(f); return frames.length })
  const cancel = vi.fn(); vi.stubGlobal('cancelAnimationFrame', cancel)
  const plots = [vi.fn(), vi.fn(), vi.fn(), vi.fn()]
  plots.forEach(scheduleChartResize)
  scheduleChartResize(plots[0]) // Repeated observer notifications must not duplicate work.
  expect(frames).toHaveLength(1)
  frames[0]()
  expect(plots.map(p => p.mock.calls.length)).toEqual([1, 0, 0, 0])
  cancelChartResize(plots[1])
  for (let i = 1; i <= 4; i++) { frames[i](); expect(plots[2]).not.toHaveBeenCalled() }
  frames[5]()
  expect(plots.map(p => p.mock.calls.length)).toEqual([1, 0, 1, 0])
  cancelChartResize(plots[3])
  expect(cancel).toHaveBeenCalledWith(7)
  frames[6]() // A callback already dispatched while disposal occurred is harmless.
  expect(plots[3]).not.toHaveBeenCalled()
  vi.unstubAllGlobals()
})

it('never dispatches a linked range alongside resizing and coalesces self-scheduled work', () => {
  const frames: (() => void)[] = []
  vi.stubGlobal('requestAnimationFrame', (f: () => void) => { frames.push(f); return frames.length })
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  const resize = vi.fn(), range = vi.fn(() => scheduleChartRange(range))
  scheduleChartRange(range); scheduleChartResize(resize)
  frames[0](); expect(resize).toHaveBeenCalledOnce(); expect(range).not.toHaveBeenCalled()
  frames[1](); expect(range).toHaveBeenCalledOnce(); expect(frames).toHaveLength(3)
  cancelChartRange(range); cancelChartResize(resize); frames[2]()
  expect(range).toHaveBeenCalledOnce()
  vi.unstubAllGlobals()
})
