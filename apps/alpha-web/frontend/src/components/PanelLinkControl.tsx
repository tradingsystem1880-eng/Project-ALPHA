import { LINK_GROUPS, type LinkGroup } from '../context/linked'
import type { PanelBindingMode } from '../context/panelLinkModel'
import type { PanelLinkedController } from '../context/usePanelLinked'

export function PanelLinkControl({ controller }: { controller: PanelLinkedController }) {
  const value = controller.binding.mode === 'pinned-to-group'
    ? `pinned:${controller.binding.group}`
    : controller.binding.mode

  return (
    <label className="panel-link-control" title="Choose which linked workstation context this panel follows">
      <span>LINK</span>
      <select
        aria-label="Panel link behavior"
        value={value}
        onChange={(event) => {
          const next = event.target.value
          if (next.startsWith('pinned:')) {
            controller.setBinding('pinned-to-group', next.slice(-1) as LinkGroup)
          } else {
            controller.setBinding(next as PanelBindingMode)
          }
        }}
      >
        <option value="follow-active">FOLLOW ACTIVE · {controller.linked.linkGroup}</option>
        {LINK_GROUPS.map((linkGroup) => (
          <option key={linkGroup} value={`pinned:${linkGroup}`}>PIN {linkGroup}</option>
        ))}
        <option value="unlinked-local">LOCAL</option>
      </select>
    </label>
  )
}
