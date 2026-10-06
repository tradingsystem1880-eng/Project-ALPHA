import { afterEach, describe, expect, it, vi } from 'vitest'
import { createChartLinkRegistry, logicalRangeForUTC } from './chartLinkRegistry'
afterEach(() => vi.unstubAllGlobals())
describe('workspace UTC linking', () => {
  it('late cleanup cannot unregister a replacement renderer', () => {
    let queued: (() => void)[] = []
    const frame = () => { const work = queued; queued = []; work.forEach(f => f()) }
    vi.stubGlobal('requestAnimationFrame', (f: () => void) => { queued.push(f); return queued.length })
    const registry = createChartLinkRegistry(); registry.configure(false, true)
    const old = registry.register('b', { range: vi.fn(), cursor: vi.fn() })
    const cursor = vi.fn(); registry.register('b', { range: vi.fn(), cursor })
    old(); registry.publish('a', 'cursor', 100); frame()
    expect(cursor).toHaveBeenCalledWith(100)
  })
  it('coalesces cursor traffic, isolates origin and suppresses synchronous feedback', () => {
    let queued: (() => void)[] = []
    const frame = () => { const work = queued; queued = []; work.forEach(f => f()) }
    vi.stubGlobal('requestAnimationFrame', (f: () => void) => { queued.push(f); return queued.length })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const registry = createChartLinkRegistry(); registry.configure(true, true)
    const origin = { cursor: vi.fn(), range: vi.fn() }
    const peer = { cursor: vi.fn(t => registry.publish('b', 'cursor', ...(t === null ? [] : [t]))), range: vi.fn((f, t) => registry.publish('b', 'range', f, t)) }
    registry.register('a', origin); const unregister = registry.register('b', peer)
    registry.publish('a', 'cursor', 100); registry.publish('a', 'cursor', 200); registry.publish('a', 'range', 100, 300)
    frame()
    expect(peer.cursor).toHaveBeenCalledExactlyOnceWith(200); expect(peer.range).toHaveBeenCalledExactlyOnceWith(100, 300)
    expect(origin.cursor).not.toHaveBeenCalled(); expect(origin.range).not.toHaveBeenCalled()
    registry.publish('a', 'cursor'); frame(); expect(peer.cursor).toHaveBeenLastCalledWith(null)
    unregister(); registry.publish('a', 'cursor', 500); frame(); expect(peer.cursor).toHaveBeenCalledTimes(2)
  })
  it('defaults to independent panels', () => {
    const raf = vi.fn(); vi.stubGlobal('requestAnimationFrame', raf)
    const registry = createChartLinkRegistry(); registry.publish('a', 'cursor', 1); expect(raf).not.toHaveBeenCalled()
  })
})

it('maps inclusive UTC endpoints without reading queued chart state', () => {
  expect(logicalRangeForUTC([100, 200, 300, 400], 200, 400)).toEqual({ from: 1.000001, to: 2.999999 })
  expect(logicalRangeForUTC([100, 200, 300], 150, 250)).toEqual({ from: .5, to: 1.5 })
  expect(logicalRangeForUTC([100, 200], 101, 199)).toBeNull()
  expect(logicalRangeForUTC([], 100, 200)).toBeNull()
  expect(logicalRangeForUTC([100, 200], 300, 400)).toBeNull()
  expect(logicalRangeForUTC([100, 200], 1, 10)).toBeNull()
  expect(logicalRangeForUTC([100, 200], 200, 100)).toBeNull()
})

it('spreads linked ranges across frames, keeps latest input and drops disabled work', () => {
  const frames: (() => void)[] = []
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  vi.stubGlobal('requestAnimationFrame', (f: () => void) => { frames.push(f); return frames.length })
  const registry = createChartLinkRegistry(); registry.configure(true, true)
  const peers = [vi.fn(), vi.fn(), vi.fn()]
  peers.forEach((range, i) => registry.register(String(i), { range, cursor: vi.fn() }))
  registry.publish('origin', 'range', 1, 2); frames[0]()
  expect(peers.map(p => p.mock.calls.length)).toEqual([1, 0, 0])
  registry.publish('origin', 'range', 3, 4); frames[1]()
  expect(peers[1]).toHaveBeenCalledExactlyOnceWith(3, 4)
  frames[2](); expect(peers[2]).toHaveBeenCalledExactlyOnceWith(3, 4)
  registry.configure(false, false); frames[3]()
  expect(peers[0]).toHaveBeenCalledExactlyOnceWith(1, 2)
})
