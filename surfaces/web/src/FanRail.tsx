import type { ReactNode } from 'react';
import { Icon, TabList, useText } from './ui';

export const RAIL_TABS = ['ask', 'earlier', 'feed', 'numbers'] as const;
export type RailTab = (typeof RAIL_TABS)[number];

/** The fan view's side rail: Ask Proofline first, then the earlier cards, the ticker and the
 * numbers. Every panel stays mounted, so a live question keeps running behind another tab. */
export function FanRail({ tab, onTab, panels, earlier, fresh }: {
  tab: RailTab; onTab: (tab: RailTab) => void; panels: Record<RailTab, ReactNode>; earlier: number; fresh: boolean;
}) {
  const { text, num } = useText();
  const label = (id: RailTab) => id === 'ask' ? <><Icon name="ask" size={15} />{text('ask.title')}</>
    : id === 'earlier' ? <>{text('rail.earlier')}{earlier > 0 && <span className="tab-count">{num(earlier)}</span>}
      {fresh && <i className="tab-dot" aria-hidden="true" />}</>
      : text(`rail.${id}`);
  return <section className="panel fan-rail" aria-label={text('rail.label')}>
    <TabList tabs={RAIL_TABS.map(id => ({ id, label: label(id), className: `rail-tab-${id}` }))} selected={tab}
      onSelect={id => onTab(id as RailTab)} label={text('rail.label')} prefix="rail-" className="rail-tabs" />
    {RAIL_TABS.map(id => <div key={id} className={`rail-panel rail-panel-${id}`} id={`rail-panel-${id}`} role="tabpanel"
      aria-labelledby={`rail-tab-${id}`} hidden={tab !== id} tabIndex={0}>{panels[id]}</div>)}
  </section>;
}
