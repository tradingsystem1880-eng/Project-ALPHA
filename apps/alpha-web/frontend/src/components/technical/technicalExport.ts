// Bokeh exports its canvases, but the technical chart's labels live in DOM overlays.
// Paint those same visible labels into the download rather than dropping the UTC axis.
import type { TechnicalStyle } from './technicalTokens'

export async function technicalPng(base: Blob, host: HTMLElement, layers: HTMLElement[], header: string[], style: TechnicalStyle): Promise<Blob> {
  await document.fonts.ready
  const image = await createImageBitmap(base)
  try {
    const bounds = host.getBoundingClientRect()
    const scale = image.width / bounds.width
    const canvas = document.createElement('canvas')
    canvas.width = image.width
    const context = canvas.getContext('2d')
    if (!context) throw new Error('PNG canvas unavailable')
    context.font = `${style.fontSize}px ${style.font}`
    const lines: string[] = []
    for (const text of header) {
      let line = ''
      for (const word of text.split(' ')) {
        const next = line ? `${line} ${word}` : word
        if (line && context.measureText(next).width > bounds.width - 12) { lines.push(line); line = word }
        else line = next
      }
      lines.push(line)
    }
    const headerHeight = lines.length ? lines.length * 15 + 8 : 0
    canvas.height = image.height + Math.ceil(headerHeight * scale)
    context.fillStyle = style.canvas
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, Math.ceil(headerHeight * scale))
    context.scale(scale, scale)
    context.font = `${style.fontSize}px ${style.font}`
    context.fillStyle = style.text
    context.textBaseline = 'middle'
    lines.forEach((line, index) => context.fillText(line, 6, 11 + index * 15))
    context.translate(-bounds.left, headerHeight - bounds.top)
    const paint = (element: HTMLElement) => {
      if (element.hidden) return
      const css = getComputedStyle(element), rect = element.getBoundingClientRect()
      if (css.display === 'none' || css.visibility === 'hidden') return
      context.fillStyle = css.backgroundColor
      context.fillRect(rect.left, rect.top, rect.width, rect.height)
      if (element.classList.contains('technical-gap')) {
        context.fillStyle = css.borderBottomColor
        context.beginPath(); context.moveTo(rect.left, rect.bottom)
        context.lineTo(rect.left + rect.width / 2, rect.top)
        context.lineTo(rect.right, rect.bottom); context.fill()
      } else {
        for (const [width, color, x, y, w, h] of [
          [css.borderTopWidth, css.borderTopColor, rect.left, rect.top, rect.width, parseFloat(css.borderTopWidth)],
          [css.borderBottomWidth, css.borderBottomColor, rect.left, rect.bottom - parseFloat(css.borderBottomWidth), rect.width, parseFloat(css.borderBottomWidth)],
          [css.borderLeftWidth, css.borderLeftColor, rect.left, rect.top, parseFloat(css.borderLeftWidth), rect.height],
          [css.borderRightWidth, css.borderRightColor, rect.right - parseFloat(css.borderRightWidth), rect.top, parseFloat(css.borderRightWidth), rect.height],
        ] as const) {
          if (parseFloat(width) > 0) { context.fillStyle = color; context.fillRect(x, y, w, h) }
        }
      }
      for (const child of element.childNodes) {
        if (child instanceof HTMLElement) paint(child)
        else if (child.nodeType === Node.TEXT_NODE && child.textContent?.trim()) {
          const range = document.createRange(); range.selectNodeContents(child)
          const textBounds = range.getBoundingClientRect()
          context.font = `${css.fontWeight} ${css.fontSize} ${css.fontFamily}`
          context.fillStyle = css.color
          context.fillText(child.textContent, textBounds.left, textBounds.top + textBounds.height / 2)
        }
      }
    }
    for (const layer of layers) paint(layer)
    return await new Promise<Blob>((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG encoding failed')), 'image/png'))
  } finally { image.close() }
}
