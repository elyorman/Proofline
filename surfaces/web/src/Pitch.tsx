import type { ReactNode } from 'react';
import type { Event } from './types/event';
import type { AmbientFeed } from './types/ambient';
import type { ReplayData } from './data';
import { activityAt, clockAt, formatClock, pitchPoint, type TimedEvent } from './replay';
import { SectionTitle, useText } from './ui';

export function ShotMarker({ outcome, x = 0, y = 0 }: { outcome: string; x?: number; y?: number }) {
  const { text } = useText();
  return <g className="shot-marker" transform={`translate(${x},${y})`} data-outcome={outcome}>
    <title>{text(`outcome.${outcome}`)}</title>
    {outcome === 'goal' ? <><circle r="1.8" /><circle r=".7" className="shot-centre" /></>
      : outcome === 'on_target' ? <><circle r="1.8" fill="none" strokeWidth=".4" /><path d="M-1 0h2M0-1v2" strokeWidth=".35" /></>
        : outcome === 'blocked' ? <rect x="-1.5" y="-1.5" width="3" height="3" fill="none" strokeWidth=".5" />
          : <path d="M-1.4-1.4l2.8 2.8m-2.8 0 2.8-2.8" strokeWidth=".5" />}
  </g>;
}

/** A player's own events and the passes aimed at them. */
export const involves = (event: Event, player: string) => event.player_id === player || event.pass_q?.receiver_id === player;
const RECENT_SECONDS = 25;

interface PitchLabel { id: string; kind: 'name' | 'followed' | 'sprint' | 'shot' | 'pass'; text: string; x: number; y: number }
interface Placed extends PitchLabel { left: number; top: number; width: number }

/** Puts each label above its point, or below it, so no two labels overlap. Presentation only. */
export function placeLabels(labels: PitchLabel[]): Placed[] {
  const placed: Placed[] = [];
  const height = 5;
  for (const label of labels) {
    const width = Math.max(12, label.text.length * 1.38 + 4);
    const left = Math.max(-5, Math.min(110 - width, label.x - width / 2));
    const tops = [label.y - 7.4, label.y + 2.6, label.y - 13, label.y + 8.2].filter(top => top > -6 && top < 69);
    const free = (top: number) => placed.every(other => left + width <= other.left || other.left + other.width <= left
      || top + height <= other.top || other.top + height <= top);
    placed.push({ ...label, left, width, top: tops.find(free) ?? tops[0] ?? label.y });
  }
  return placed;
}

export function Pitch({ data, elapsed, player, ambient, children, footer }: {
  data: ReplayData; elapsed: number; player?: string; ambient?: AmbientFeed; children?: ReactNode; footer?: ReactNode;
}) {
  const { text, num } = useText();
  // Recent play by both teams; a followed player is highlighted, never the only one shown.
  const recent = data.timeline.events.filter(({ event, at }) => at <= elapsed && at >= elapsed - RECENT_SECONDS && event.start).slice(-14);
  const latest = recent.at(-1)?.event;
  const focus = player ? recent.filter(({ event }) => involves(event, player)).at(-1)?.event : undefined;
  let lastTouch: TimedEvent | undefined;
  for (const item of player ? data.timeline.events : []) {
    if (item.at > elapsed) break;
    if (involves(item.event, player!)) lastTouch = item;
  }
  const players = data.teams.flatMap(team => team.players);
  const name = (event: Event) => players.find(p => p.id === event.player_id)?.name ?? event.team;
  const followed = player ? players.find(p => p.id === player)?.name ?? player : undefined;
  const speeds = new Map((ambient?.speed_tags ?? []).map(tag => [tag.event_id, tag]));
  const badges = new Map((ambient?.pass_badges ?? []).map(badge => [badge.event_id, badge]));
  const point = (event: Event, which: 'start' | 'end' = 'start') =>
    pitchPoint(event[which] ?? event.start!, event.team === data.teams[0].name);
  const names: PitchLabel[] = [latest, focus].filter((event, i, all): event is Event => !!event && all.indexOf(event) === i)
    .map(event => ({ id: `name-${event.event_id}`, kind: event === focus ? 'followed' : 'name', text: name(event), ...point(event) }));
  // Ambient tags for the two most recent tagged events, so the pitch stays readable.
  const tags: PitchLabel[] = recent.filter(({ event }) => speeds.has(event.event_id) || badges.has(event.event_id)).slice(-2).map(({ event }) => {
    const speed = speeds.get(event.event_id);
    const at = point(event, speed?.kind === 'shot' ? 'start' : 'end');
    return speed
      ? { id: event.event_id, kind: speed.kind, text: text('tag.speed', { speed: num(speed.speed_kmh) }), ...at }
      : { id: event.event_id, kind: 'pass', text: text('tag.difficulty', { value: badges.get(event.event_id)!.difficulty }), ...at };
  });
  return <div className={`pitch-panel ${player ? 'focus-mode' : ''}`}>
    <div className="pitch-heading"><div><span className="eyebrow">{text('pitch')}</span><p>{text('pitch.caption')}</p></div>{children}</div>
    <svg className="pitch" viewBox="-6 -5.5 117 81" role="img" aria-label={text('pitch.aria')}>
      <defs><pattern id="grass" width="10.5" height="68" patternUnits="userSpaceOnUse"><rect width="5.25" height="68" fill="#ffffff" opacity=".022" /></pattern></defs>
      <rect x="0" y="0" width="105" height="68" fill="url(#grass)" />
      <g className="pitch-lines" fill="none" strokeWidth=".23">
        <rect width="105" height="68" rx=".2" /><path d="M52.5 0v68" /><circle cx="52.5" cy="34" r="9.15" />
        <path d="M0 13.84h16.5v40.32H0m105-40.32H88.5v40.32H105M0 24.84h5.5v18.32H0m105-18.32h-5.5v18.32h5.5" />
        <path d="M16.5 26.7a9.15 9.15 0 0 1 0 14.6m72-14.6a9.15 9.15 0 0 0 0 14.6M0 30.34h-2v7.32h2m105-7.32h2v7.32h-2" />
        <circle cx="11" cy="34" r=".3" /><circle cx="94" cy="34" r=".3" /><circle cx="52.5" cy="34" r=".4" />
      </g>
      <text x="0" y="-1.9" className="pitch-direction home">{text('pitch.homeDirection', { team: data.teams[0].name })}</text>
      <text x="105" y="-1.9" textAnchor="end" className="pitch-direction away">{text('pitch.awayDirection', { team: data.teams[1].name })}</text>
      {recent.map(({ event }, i) => {
        const home = event.team === data.teams[0].name;
        const start = point(event);
        const end = event.end ? point(event, 'end') : null;
        const active = event === latest;
        const mine = !!player && involves(event, player);
        const opacity = active || mine ? 1 : (player ? .14 : .2) + i * (player ? .03 : .045);
        return <g key={event.event_id} className={`${home ? 'home-event' : 'away-event'} ${mine ? 'followed' : ''}`} opacity={opacity}>
          <title>{`${formatClock(event.clock)} · ${name(event)} · ${text(`event.${event.type}`)}`}</title>
          {(event.type === 'pass' || event.type === 'carry' || event.type === 'sprint') && end && <line x1={start.x} y1={start.y} x2={end.x} y2={end.y}
            strokeWidth={event.type === 'pass' ? .35 : .25} strokeDasharray={event.type === 'pass' ? '1.1 .8' : event.type === 'sprint' ? '.3 .6' : undefined} />}
          {event.type === 'pass' && end && <circle cx={end.x} cy={end.y} r=".55" />}
          {event.type === 'shot' ? <ShotMarker outcome={event.outcome ?? 'na'} x={start.x} y={start.y} /> : <circle cx={start.x} cy={start.y} r={active || event === focus ? 1.4 : mine ? 1.05 : .8} />}
          {(active || event === focus) && <circle cx={start.x} cy={start.y} r={event === focus ? 3.6 : 3} fill="none" strokeWidth={event === focus ? .45 : .25} opacity=".7" />}
        </g>;
      })}
      {placeLabels([...names, ...tags]).map(label => <g key={label.id} className={label.kind === 'name' || label.kind === 'followed' ? `player-label ${label.kind}` : `pitch-tag tag-${label.kind}`}
        transform={`translate(${label.left},${label.top})`}>
        <rect width={label.width} height="5" rx="1.3" /><text x={label.width / 2} y="3.5" textAnchor="middle">{label.text}</text>
      </g>)}
      {!recent.length && <text x="52.5" y="34" className="pitch-empty" textAnchor="middle">{text('pitch.empty')}</text>}
      <g className="pitch-legend">{['goal', 'on_target', 'off_target', 'blocked'].map((outcome, i) => <g key={outcome} transform={`translate(${i * 17},72.4)`}>
        <g transform="scale(.6)"><ShotMarker outcome={outcome} /></g><text x="1.8" y=".8">{text(`outcome.${outcome}`)}</text>
      </g>)}<text x="105" y="73.2" textAnchor="end">{text('pitch.scale')}</text></g>
    </svg>
    <div className="pitch-caption">
      {latest ? <p><time>{formatClock(latest.clock)}</time><strong>{name(latest)}</strong><span>{text(`event.${latest.type}`)}{latest.type === 'shot' ? ` · ${text(`outcome.${latest.outcome ?? 'na'}`)}` : ''}</span></p>
        : <p>{text('pitch.note')}</p>}
      {followed && <p className="pitch-following"><i />{text('pitch.following', { player: followed })} · {focus ? text('pitch.focusNow')
        : lastTouch ? text('pitch.lastTouch', { clock: formatClock(lastTouch.event.clock) }) : text('pitch.notYet')}</p>}
    </div>
    {footer}
  </div>;
}

export function Activity({ data, elapsed }: { data: ReplayData; elapsed: number }) {
  const { text, num } = useText();
  const series = activityAt(data.timeline, elapsed, data.teams.map(t => t.name));
  const max = Math.max(4, ...series.flatMap(s => s.values));
  const labels = [0, 10, 19];
  return <section className="panel activity-panel"><SectionTitle title={text('activity')} sub={text('activity.sub')}>
    <div className="chart-legend">{data.teams.map((team, i) => <span key={team.code}><i className={`team-dot ${i ? 'away' : 'home'}`} />{team.code}</span>)}</div>
  </SectionTitle>
    <div className="chart-y-label">{text('activity.axis')}</div>
    <svg className="activity-chart" viewBox="0 0 620 130" role="img" aria-label={text('activity.aria')}>
      {[0, .5, 1].map(f => <g key={f}><line x1="30" y1={55 - f * 48} x2="610" y2={55 - f * 48} className="chart-grid" /><text x="20" y={58 - f * 48} textAnchor="end">{num(max * f)}</text></g>)}
      <line x1="30" y1="59" x2="610" y2="59" className="chart-axis" />
      {series.map((s, i) => <g key={i}><title>{`${formatClock(clockAt(Math.max(0, s.start), data.timeline.firstHalfSeconds))} · ${data.teams[0].code}: ${s.values[0]} · ${data.teams[1].code}: ${s.values[1]}`}</title>
        <rect x={36 + i * 28.7} y={55 - s.values[0] / max * 48} width="10" height={s.values[0] / max * 48} rx="2" className="bar-home" />
        <rect x={48 + i * 28.7} y={55 - s.values[1] / max * 48} width="10" height={s.values[1] / max * 48} rx="2" className="bar-away" />
      </g>)}
      {labels.map(i => <text x={46 + i * 28.7} y="82" key={i} textAnchor="middle">{series[i].start >= 0 ? formatClock(clockAt(series[i].start, data.timeline.firstHalfSeconds)) : '—'}</text>)}
      <text x="320" y="110" textAnchor="middle">{text('match.minute')}</text>
    </svg>
  </section>;
}
