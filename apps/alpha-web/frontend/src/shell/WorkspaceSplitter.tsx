import type { PointerEvent, KeyboardEvent } from 'react'
/** Pointer capture keeps a drag local; arrow keys resize by five percentage points. */
export function WorkspaceSplitter({ axis, value, onChange }: { axis: 'horizontal' | 'vertical'; value: number; onChange: (value: number) => void }) {
  const clamp = (n: number) => Math.max(0.15, Math.min(0.85, n))
  const move = (event: PointerEvent<HTMLDivElement>) => {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return
    const box = event.currentTarget.parentElement!.getBoundingClientRect()
    onChange(clamp(axis === 'vertical' ? (event.clientX - box.left) / box.width : (event.clientY - box.top) / box.height))
  }
  const key = (event: KeyboardEvent) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home'].includes(event.key)) return
    event.preventDefault(); onChange(event.key === 'Home' ? 0.5 : clamp(value + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 0.05 : -0.05)))
  }
  return <div className={`workspace-splitter splitter-${axis}`} role="separator" aria-label={`${axis} panel splitter`} aria-orientation={axis} aria-valuemin={15} aria-valuemax={85} aria-valuenow={Math.round(value * 100)} tabIndex={0} style={axis === 'vertical' ? { left: `${value * 100}%` } : { top: `${value * 100}%` }} onKeyDown={key} onPointerDown={event => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId) }} onPointerMove={move} onPointerUp={event => event.currentTarget.releasePointerCapture(event.pointerId)} />
}
