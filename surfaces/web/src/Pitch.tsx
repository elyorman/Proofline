import type { Event } from './types/event';
import type { ReplayData } from './data';
import { activityAt, clockAt, formatClock, pitchPoint, type TimedEvent } from './replay';
import { SectionTitle, useText } from './ui';

export function Pitch({ data, elapsed, player }: { data: ReplayData; elapsed: number; player?: string }) {
  const { text } = useText();
  const recent = data.timeline.events.filter(({ event, at }) => at <= elapsed && at >= elapsed - 25
    && event.start && (!player || event.player_id === player));
  const latest = recent.at(-1)?.event;
  const name = (event: Event) => data.teams.flatMap(team => team.players).find(p => p.id === event.player_id)?.name ?? event.team;
  const latestPoint = latest?.start ? pitchPoint(latest.start, latest.team === data.teams[0].name) : null;
  return <div className="pitch-panel">
    <div className="pitch-heading"><div><span className="eyebrow">{text('pitch')}</span><p>{text('pitch.caption')}</p></div><span className="pitch-indicator"><i />{text('replay')}</span></div>
    <svg className="pitch" viewBox="-7 -8 119 86" role="img" aria-label={text('pitch.aria')}>
      <defs><pattern id="grass" width="10.5" height="68" patternUnits="userSpaceOnUse"><rect width="5.25" height="68" fill="#ffffff" opacity=".018" /></pattern></defs>
      <rect x="0" y="0" width="105" height="68" fill="url(#grass)" />
      <g className="pitch-lines" fill="none" strokeWidth=".23">
        <rect width="105" height="68" rx=".2" /><path d="M52.5 0v68" /><circle cx="52.5" cy="34" r="9.15" />
        <path d="M0 13.84h16.5v40.32H0m105-40.32H88.5v40.32H105M0 24.84h5.5v18.32H0m105-18.32h-5.5v18.32h5.5" />
        <path d="M16.5 26.7a9.15 9.15 0 0 1 0 14.6m72-14.6a9.15 9.15 0 0 0 0 14.6M0 30.34h-2v7.32h2m105-7.32h2v7.32h-2" />
        <circle cx="11" cy="34" r=".3" /><circle cx="94" cy="34" r=".3" /><circle cx="52.5" cy="34" r=".4" />
      </g>
      {recent.slice(-12).map(({ event }, i) => {
        const home = event.team === data.teams[0].name;
        const start = pitchPoint(event.start!, home);
        const end = event.end ? pitchPoint(event.end, home) : null;
        const active = event === latest;
        return <g key={event.event_id} className={home ? 'home-event' : 'away-event'} opacity={active ? 1 : .18 + i * .035}>
          <title>{`${formatClock(event.clock)} · ${name(event)} · ${text(`event.${event.type}`)}`}</title>
          {event.type === 'pass' && end && <><line x1={start.x} y1={start.y} x2={end.x} y2={end.y} strokeWidth=".35" strokeDasharray="1.1 .8" /><circle cx={end.x} cy={end.y} r=".55" /></>}
          {event.type === 'shot' ? <path d={`M${start.x - 1.2} ${start.y - 1.2}l2.4 2.4m-2.4 0 2.4-2.4`} strokeWidth=".5" /> : <circle cx={start.x} cy={start.y} r={active ? 1.5 : .8} />}
          {active && <circle cx={start.x} cy={start.y} r="3.2" fill="none" strokeWidth=".25" opacity=".6" />}
        </g>;
      })}
      {latest && latestPoint && <g className="player-label" transform={`translate(${Math.max(14, Math.min(91, latestPoint.x))},${latestPoint.y < 10 ? latestPoint.y + 7 : latestPoint.y - 6})`}>
        <rect x="-15" y="-2.6" width="30" height="5.4" rx="1.4" /><text textAnchor="middle" dy=".9">{name(latest)}</text>
      </g>}
      {!recent.length && <text x="52.5" y="34" className="pitch-empty" textAnchor="middle">{text('pitch.empty')}</text>}
    </svg>
    <div className="pitch-bottom"><span><i className="team-dot home" />{text('pitch.homeDirection')}</span><span>{text('pitch.scale')}</span><span>{text('pitch.awayDirection')}<i className="team-dot away" /></span></div>
    <div className="pitch-caption">{latest ? <><span>{formatClock(latest.clock)}</span><strong>{name(latest)}</strong><span>{text(`event.${latest.type}`)}{latest.type === 'shot' ? ` · ${text(`outcome.${latest.outcome ?? 'na'}`)}` : ''}</span></> : text('pitch.note')}</div>
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

export function EventFeed({ events, data }: { events: TimedEvent[]; data: ReplayData }) {
  const { text } = useText();
  const feed = events.filter(({ event }) => ['goal', 'shot', 'card', 'substitution', 'set_piece'].includes(event.type)).slice(-5).reverse();
  return <section className="panel event-panel"><SectionTitle title={text('feed')} />
    {feed.length ? <ol className="event-feed">{feed.map(({ event }) => <li key={event.event_id}>
      <time>{formatClock(event.clock)}</time><span className={`event-mark ${event.team === data.teams[0].name ? 'home' : 'away'}`}>{event.type === 'goal' ? '◆' : '·'}</span>
      <div><strong>{text(`event.${event.type}`)}</strong><p>{event.team}{event.player_id && ` · ${data.teams.flatMap(t => t.players).find(p => p.id === event.player_id)?.name ?? event.player_id}`}</p></div>
    </li>)}</ol> : <p className="muted padded">{text('feed.empty')}</p>}
  </section>;
}
