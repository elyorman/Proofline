import type { InsightCard } from './types/insight-card';
import type { EventAmendment } from './types/event-amendment';
import { formatClock } from './replay';
import { useText } from './ui';

export function RevisionDiff({ card, snapshots, amendments }: {
  card: InsightCard; snapshots: InsightCard[]; amendments: EventAmendment[];
}) {
  const { text, metric, num } = useText();
  const before = snapshots.find(c => c.id === card.id && c.revision === (card.revision ?? 1) - 1);
  if (!before) return null;
  const linked = amendments.filter(a => card.revisions?.some(r => r.amendment_ids?.includes(a.amendment_id)));
  return <section className="revision-diff">
    <h3>{text('revision.diff')}</h3>
    <p className="muted">{text(`status.${before.status}`)} → {text(`status.${card.status}`)}</p>
    <div className="table-scroll"><table><thead><tr><th>{text('case.metric')}</th><th>{text('overlay.before')}</th><th>{text('overlay.after')}</th></tr></thead><tbody>
      {card.evidence?.map((e, index) => {
        const previous = before.evidence?.find(p => p.metric === e.metric && p.subject === e.subject);
        return <tr key={`${e.tool_call_id}-${index}`}><th>{text(`metric.${e.metric}`)}<small>{e.subject}</small></th>
          <td>{previous ? metric(e.metric, previous.value) : text('value.unset')}</td><td>{metric(e.metric, e.value)}</td></tr>;
      })}
    </tbody></table></div>
    <p className="muted">{before.depends_on.data_version} → {card.depends_on.data_version}</p>
    {linked.map(amendment => <article key={amendment.amendment_id}>
      <h4>{text('revision.amendment')} <code>{amendment.amendment_id}</code> · {formatClock(amendment.at)}</h4>
      <p>{amendment.reason}</p>
      {amendment.shift && <p>{text('revision.shift', { x: num(amendment.shift.dx_m ?? 0), y: num(amendment.shift.dy_m ?? 0) })}</p>}
      {amendment.set && <pre>{JSON.stringify(amendment.set, null, 2)}</pre>}
      <details><summary>{text('revision.events')}</summary><ul className="event-id-list">{amendment.event_ids.map(id => <li key={id}><code>{id}</code></li>)}</ul></details>
    </article>)}
  </section>;
}
