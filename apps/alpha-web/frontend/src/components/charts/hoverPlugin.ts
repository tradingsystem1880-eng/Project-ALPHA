// Shared uPlot hover readout: a floating legend (top-right) showing each series' value at the
// cursor, plus the x timestamp. Charts across the workstation get one consistent hover UX.

import type uPlot from 'uplot'

import { fmtTime } from '../../util/format'

export interface HoverSeries {
  /** Which series index (1-based, matching uPlot data rows) to show. */
  idx: number
  label: string
  color: string
  format?: (v: number) => string
}

export function hoverPlugin(series: HoverSeries[], xIsTime = true): uPlot.Plugin {
  let el: HTMLDivElement | null = null

  return {
    hooks: {
      init: (u: uPlot) => {
        el = document.createElement('div')
        el.className = 'chart-hover'
        el.style.display = 'none'
        u.over.appendChild(el)
        u.over.addEventListener('mouseleave', () => {
          if (el) el.style.display = 'none'
        })
      },
      setCursor: (u: uPlot) => {
        if (!el) return
        const { idx } = u.cursor
        if (idx == null) {
          el.style.display = 'none'
          return
        }
        const x = u.data[0][idx]
        if (x == null) {
          el.style.display = 'none'
          return
        }
        const rows = series
          .map((s) => {
            const v = u.data[s.idx]?.[idx]
            if (typeof v !== 'number' || !Number.isFinite(v)) return null
            const text = s.format ? s.format(v) : v.toFixed(3)
            return `<span class="hover-row"><i style="background:${s.color}"></i>${s.label} <b>${text}</b></span>`
          })
          .filter(Boolean)
        if (!rows.length) {
          el.style.display = 'none'
          return
        }
        const xText = xIsTime ? fmtTime(x).slice(0, 10) : String(x)
        el.innerHTML = `<span class="hover-x">${xText}</span>${rows.join('')}`
        el.style.display = 'flex'
      },
      destroy: () => {
        el = null
      },
    },
  }
}
