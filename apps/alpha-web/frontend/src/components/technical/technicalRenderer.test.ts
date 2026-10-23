import { afterEach, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => {
  class Model {
    change = { connect() {} }
    selected = { indices: [], change: { connect() {} } }
    constructor(attrs: object = {}) { Object.assign(this, attrs) }
    setv(attrs: object) { Object.assign(this, attrs) }
  }
  return {
    Model,
    pending: [] as { resolve: (value: unknown) => void; destroy: ReturnType<typeof vi.fn> }[],
  }
})
vi.mock('../bokehLifecycle', () => ({ showScientificPlot: () => new Promise(resolve => { state.pending.push({ resolve, destroy: vi.fn() }) }) }))
vi.mock('@bokeh/bokehjs/build/js/lib/api/figure', () => ({ figure: (attrs: object) => Object.assign(new state.Model(attrs), {
  axis: {}, grid: {}, xaxis: [{}], yaxis: [{}], xgrid: [{}], ygrid: [{}],
  segment: () => ({}), vbar: () => ({}), line: () => ({}), multi_line: () => ({}), scatter: () => ({}),
  on_event() {},
  add_layout() {}, add_tools() {},
}) }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/layouts/column', () => ({ Column: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/sources/column_data_source', () => ({ ColumnDataSource: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/sources/cds_view', () => ({ CDSView: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/filters/index_filter', () => ({ IndexFilter: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/ranges/range1d', () => ({ Range1d: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/tickers/fixed_ticker', () => ({ FixedTicker: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/grids/grid', () => ({ Grid: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/axes/linear_axis', () => ({ LinearAxis: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/formatters/printf_tick_formatter', () => ({ PrintfTickFormatter: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/annotations/span', () => ({ Span: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/annotations/label_set', () => ({ LabelSet: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/models/tools/inspectors/hover_tool', () => ({ HoverTool: state.Model }))
vi.mock('@bokeh/bokehjs/build/js/lib/core/bokeh_events', () => ({ MouseMove: {}, MouseLeave: {}, RangesUpdate: {}, LODStart: {}, LODEnd: {} }))

import { mountTechnicalChart } from './technicalRenderer'
import { technicalStyle } from './technicalTokens'
import { createChartLinkRegistry } from '../../shell/chartLinkRegistry'

afterEach(() => { state.pending.length = 0; vi.unstubAllGlobals() })

it('navigates only visible observations and maps a tap to the exact bar and linked UTC cursor', async () => {
  let frame: (() => void) | undefined
  vi.stubGlobal('requestAnimationFrame', (f: () => void) => { frame = f; return 1 })
  vi.stubGlobal('cancelAnimationFrame', () => {})
  vi.stubGlobal('ResizeObserver', class { observe() {}; disconnect() {} })
  const pointerHandlers: Record<string, EventListener> = {}
  const ownerDocument = { createElement: () => ({ ownerDocument, style: {}, dataset: {}, append() {}, removeAttribute() {}, remove() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 500, height: 300 }) }) }
  const node = {
    clientWidth: 500, clientHeight: 300, dataset: {}, ownerDocument,
    addEventListener(type: string, handler: EventListener) { pointerHandlers[type] = handler },
    removeEventListener(type: string) { delete pointerHandlers[type] },
  } as unknown as HTMLElement
  const bars = [0, 1, 2].map(i => ({ t: 1700000000 + i * 86400, o: 10 + i, h: 11 + i, l: 9 + i, c: 10.5 + i, v: 100 + i }))
  const onCursor = vi.fn()
  const registry = createChartLinkRegistry(); registry.configure(true, true)
  let linkedTime: number | null | undefined
  registry.register('peer', { range() {}, cursor(time) { linkedTime = time ?? null } })
  const mounted = mountTechnicalChart(node, { bars, style: technicalStyle('classic'), title: 'native', indicators: [], indicatorTimes: [], annotations: [] }, { panelId: 'panel', registry, onCursor })
  state.pending[0].resolve({ destroy: vi.fn(), view: {
    el: { remove() {} }, child_views: [{ canvas_view: { overlays_el: ownerDocument.createElement() },
      frame: { bbox: { left: 0, right: 500, top: 0, bottom: 300, width: 500, height: 300 }, x_scale: { compute: (x: number) => x, invert: (x: number) => x }, y_scale: { compute: (y: number) => y, invert: (y: number) => y } },
      repainted: { connect() {} }, invalidate_layout() {},
    }], invalidate_layout() {},
  } })
  const chart = await mounted
  try {
    chart.activate()
    chart.navigate('last')
    frame?.()
    expect(onCursor).toHaveBeenLastCalledWith(2)
    expect(linkedTime).toBe(bars[2].t)
    chart.navigate(-1)
    frame?.()
    expect(onCursor).toHaveBeenLastCalledWith(1)
    chart.navigate('first')
    frame?.()
    expect(onCursor).toHaveBeenLastCalledWith(0)
    chart.navigate(-1)
    frame?.()
    expect(onCursor).toHaveBeenLastCalledWith(0)

    const tap = { pointerId: 9, pointerType: 'touch', button: 0, clientX: 1.4, clientY: 10.25 } as PointerEvent
    pointerHandlers.pointerdown?.(tap)
    pointerHandlers.pointerup?.(tap)
    frame?.()
    expect(onCursor).toHaveBeenLastCalledWith(1)
    expect(linkedTime).toBe(bars[1].t)
    chart.navigate('clear')
    frame?.()
    expect(onCursor).toHaveBeenLastCalledWith(null)
    expect(linkedTime).toBeNull()
  } finally { chart.destroy() }
})

it.each([true, false])('stale price mount cannot take replacement links; old resolves first=%s', async oldFirst => {
  let frame: (() => void) | undefined
  vi.stubGlobal('requestAnimationFrame', (f: () => void) => { frame = f; return 1 })
  vi.stubGlobal('cancelAnimationFrame', () => {})
  vi.stubGlobal('ResizeObserver', class { observe() {}; disconnect() {} })
  const ownerDocument = { createElement: () => ({ ownerDocument, style: {}, dataset: {}, append() {}, removeAttribute() {}, remove() {} }) }
  const node = { clientWidth: 500, clientHeight: 300, dataset: {}, ownerDocument, addEventListener() {}, removeEventListener() {} } as unknown as HTMLElement
  const registry = createChartLinkRegistry(); registry.configure(true, true)
  const register = vi.spyOn(registry, 'register')
  const oldCursor = vi.fn(), newCursor = vi.fn()
  const bars = [0, 1, 2].map(i => ({ t: 1700000000 + i * 86400, o: 10, h: 11, l: 9, c: 10, v: 100 }))
  const composition = { bars, style: technicalStyle('classic'), title: 'native', indicators: [], indicatorTimes: [], annotations: [] }
  const old = mountTechnicalChart(node, composition, { panelId: 'panel', registry, onCursor: oldCursor })
  const next = mountTechnicalChart(node, composition, { panelId: 'panel', registry, onCursor: newCursor })
  const finish = (n: number) => state.pending[n].resolve({ destroy: state.pending[n].destroy, view: {
    el: { remove() {} }, child_views: [{ canvas_view: { overlays_el: ownerDocument.createElement() },
      frame: { bbox: { left: 0, right: 500, top: 0, bottom: 300, width: 500, height: 300 }, x_scale: { compute: (x: number) => x }, y_scale: { compute: (y: number) => y } },
      repainted: { connect() {} }, invalidate_layout() {},
    }], invalidate_layout() {},
  } })
  // The component activates only the mount whose effect is still live.
  const activate = (chart: Awaited<ReturnType<typeof mountTechnicalChart>>) => {
    if ('activate' in chart && typeof chart.activate === 'function') chart.activate()
  }
  if (oldFirst) { finish(0); (await old).destroy(); finish(1); activate(await next) }
  else { finish(1); activate(await next); finish(0); (await old).destroy() }
  const replacement = await next
  try {
    registry.publish('other', 'cursor', bars[1].t); frame?.()
    expect(newCursor).toHaveBeenCalledWith(1)
    expect(oldCursor).not.toHaveBeenCalled()
    expect(register).toHaveBeenCalledOnce()
    expect(state.pending[0].destroy).toHaveBeenCalledOnce()
    registry.publish('other', 'range', bars[0].t, bars[1].t); frame?.()
    expect(replacement.visibleUTC()).toEqual([bars[0].t, bars[1].t])
  } finally { replacement.destroy() }
  newCursor.mockClear()
  registry.publish('other', 'cursor', bars[2].t); frame?.()
  expect(newCursor).not.toHaveBeenCalled()
})
