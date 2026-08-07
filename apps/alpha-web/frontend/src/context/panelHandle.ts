/**
 * The narrow slice of a panel host that a panel actually needs.
 *
 * Panels used to be typed against `IDockviewPanelProps`, which bound every one of them to
 * a docking library they only used for three methods. Declaring the real requirement here
 * lets a panel live inside a plain screen, a split view, or anything else, and keeps the
 * shell free to change without touching 20-odd components.
 */

export interface PanelParameterHandle {
  getParameters(): Record<string, unknown>
  updateParameters(parameters: Record<string, unknown>): void
  onDidParametersChange(listener: (parameters: unknown) => void): { dispose(): void }
}

export interface PanelHandleProps {
  params?: unknown
  api: PanelParameterHandle
}
