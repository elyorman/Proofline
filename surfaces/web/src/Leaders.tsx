import type { ReplayData } from './data';
import { leaders, type Leader } from './replay';
import { SectionTitle, useText } from './ui';

const UNIT: Partial<Record<Leader['stat'], string>> = { sprint_distance: 'm', top_speed: 'km/h' };

/** The match's leaders up to a clock, from delivered events only: what a stats question can
 * be answered with when it is not a question about change. */
export function Leaders({ data, elapsed, compact = false }: { data: ReplayData; elapsed: number; compact?: boolean }) {
  const { text, num } = useText();
  const delivered = data.timeline.events.filter(({ at }) => at <= elapsed).map(({ event }) => event);
  const rows = leaders(delivered);
  const name = (id: string) => data.teams.flatMap(t => t.players).find(p => p.id === id)?.name ?? id;
  const code = (team: string) => data.teams.find(t => t.name === team)?.code ?? team;
  const body = <>
    <table className="leaders-table"><tbody>{rows.map(row => <tr key={row.stat}>
      <th scope="row">{text(`leaders.${row.stat}`)}</th>
      <td>{name(row.player)} <span className="muted">{code(row.team)}</span></td>
      <td className="leaders-value">{num(row.stat === 'top_speed' ? Math.round(row.value * 10) / 10 : Math.round(row.value))}{UNIT[row.stat] ? ` ${UNIT[row.stat]}` : ''}</td>
    </tr>)}</tbody></table>
    <p className="muted leaders-note">{text('leaders.note')}</p>
  </>;
  if (compact) return <section className="leaders compact"><h4>{text('leaders.title')}</h4>{body}</section>;
  return <section className="panel leaders"><SectionTitle title={text('leaders.title')} sub={text('leaders.sub')} />{body}</section>;
}
