/** Share axis work across chart engines; resizing and linked zooms never dispatch together. */
const resizes = new Set<() => void>(), ranges = new Set<() => void>()
let frame = 0, cooldown = 0, flushing = false
const flush = () => {
  frame = 0
  if (cooldown) cooldown--
  const queue = resizes.size && !cooldown ? resizes : ranges
  const next = queue.values().next().value
  if (next) {
    queue.delete(next); flushing = true
    try { next() } finally { flushing = false }
    if (queue === resizes) cooldown = 5
  }
  if (resizes.size || ranges.size) frame = requestAnimationFrame(flush)
  else cooldown = 0
}
const schedule = () => { if (!frame && !flushing) frame = requestAnimationFrame(flush) }
const cancelEmptyFrame = () => {
  if (!resizes.size && !ranges.size && frame) { cancelAnimationFrame(frame); frame = 0; cooldown = 0 }
}
export function scheduleChartResize(resize: () => void) { resizes.add(resize); schedule() }
export function cancelChartResize(resize: () => void) { resizes.delete(resize); cancelEmptyFrame() }
export function scheduleChartRange(range: () => void) { ranges.add(range); schedule() }
export function cancelChartRange(range: () => void) { ranges.delete(range); cancelEmptyFrame() }
