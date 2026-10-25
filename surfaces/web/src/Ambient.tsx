// The ambient layer, formatted. Every value is computed by ambient/ and exported with the
// clock from which it is known; this file only gates by that clock and draws.
import type { AmbientFeed, TickerLine } from './types/ambient';
import type { ReplayData } from './data';
import { elapsedAt, formatClock, knownAt } from './replay';
import { SectionTitle, useText } from './ui';

// The strip is drawn at about its displayed size so its 9px labels stay readable.
const PLOT_LEFT = 24;
const PLOT_RIGHT = 328;
const MID = 30;
const AMPLITUDE = 21;

function side(line: TickerLine, data: ReplayData) {
  return !line.team ? 'neutral' : line.team === data.teams[0].name ? 'home' : 'away';
}

export function MomentumStrip({ feed, data, elapsed }: { feed: AmbientFeed; data: ReplayData; elapsed: number }) {
  const { text, num } = useText();
  const { firstHalfSeconds: firstHalf, duration } = data.timeline;
  const points = knownAt(feed.momentum, elapsed, firstHalf);
  const latest = points.at(-1);
  const [home, away] = data.teams;
  const x = (seconds: number) => PLOT_LEFT + Math.min(seconds, duration) / duration * (PLOT_RIGHT - PLOT_LEFT);
  const width = Math.max(1, 60 / duration * (PLOT_RIGHT - PLOT_LEFT) - 1.4);
  const lead = !latest || latest.value === 0 ? text('momentum.level') : text('momentum.lead', {
    team: latest.value > 0 ? home.code : away.code, value: num(Math.abs(latest.value)),
  });
  const ticks = [
    { label: "0'", at: 0 },
    { label: "45'", at: firstHalf },
    { label: "90'", at: elapsedAt({ period: 2, minute: 90, second: 0 }, firstHalf) },
  ];
  return <section className="pulse-card momentum-card">
    <header><div><h3>{text('metric.momentum')}</h3><p>{text('momentum.sub')}</p></div>
      <strong className={!latest || latest.value === 0 ? '' : latest.value > 0 ? 'home' : 'away'}>{lead}</strong></header>
    <svg className="momentum-strip" viewBox="0 0 360 80" role="img" aria-label={text('momentum.aria', { home: home.name, away: away.name })}>
      {[[MID - AMPLITUDE, '+1'], [MID, '0'], [MID + AMPLITUDE, '−1']].map(([y, label]) => <g key={label}>
        <line x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={y} y2={y} className={label === '0' ? 'axis' : 'grid'} />
        <text x={PLOT_LEFT - 4} y={Number(y) + 3} textAnchor="end">{label}</text>
      </g>)}
      <text x={PLOT_RIGHT + 6} y={MID - AMPLITUDE + 7} className="team-label home">▲ {home.code}</text>
      <text x={PLOT_RIGHT + 6} y={MID + AMPLITUDE} className="team-label away">▼ {away.code}</text>
      <line x1={x(firstHalf)} x2={x(firstHalf)} y1={MID - AMPLITUDE - 4} y2={MID + AMPLITUDE + 4} className="divider" />
      {points.map(point => {
        const start = x(elapsedAt({ period: point.period, minute: point.minute, second: 0 }, firstHalf));
        const height = Math.abs(point.value) * AMPLITUDE;
        return <rect key={`${point.period}-${point.minute}`} x={start} width={width} y={point.value > 0 ? MID - height : MID}
          height={Math.max(height, .6)} rx=".6" className={point.value > 0 ? 'bar-home' : point.value < 0 ? 'bar-away' : 'bar-level'}>
          <title>{`${formatClock(point.at)} · ${num(point.value)}`}</title>
        </rect>;
      })}
      <line x1={x(elapsed)} x2={x(elapsed)} y1={MID - AMPLITUDE - 6} y2={MID + AMPLITUDE + 6} className="cursor" />
      {ticks.map(tick => <text key={tick.label} x={x(tick.at)} y={MID + AMPLITUDE + 13} textAnchor="middle">{tick.label}</text>)}
      <text x={(PLOT_LEFT + PLOT_RIGHT) / 2} y="78" textAnchor="middle" className="axis-title">{text('match.minute')}</text>
    </svg>
    {!points.length && <p className="pulse-rule">{text('momentum.empty')}</p>}
    <p className="pulse-rule">{text('momentum.rule', {
      shot: num(feed.rules.shot_threat), entry: num(feed.rules.entry_threat), halfLife: num(feed.rules.momentum_half_life_min),
    })}</p>
  </section>;
}

export function ControlGauge({ feed, data, elapsed }: { feed: AmbientFeed; data: ReplayData; elapsed: number }) {
  const { text, num } = useText();
  const { rules } = feed;
  const reading = knownAt(feed.control, elapsed, data.timeline.firstHalfSeconds).at(-1);
  const chaos = reading?.chaos ?? null;
  return <section className="pulse-card gauge-card">
    <header><div><h3>{text('metric.control_chaos')}</h3><p>{text('control.sub', { minutes: rules.control_window_min })}</p></div></header>
    <div className="gauge-track" role="meter" aria-label={text('control.aria')} aria-valuemin={0} aria-valuemax={1}
      aria-valuenow={chaos ?? undefined} aria-valuetext={reading?.spell != null ? text('control.reading', { spell: num(reading.spell) }) : undefined}>
      {chaos !== null && <i style={{ left: `${chaos * 100}%` }} />}
    </div>
    <div className="gauge-scale">
      <span><b>{text('control.control')}</b>{text('control.scale.control', { spell: num(rules.control_spell) })}</span>
      <span><b>{text('control.chaos')}</b>{text('control.scale.chaos', { spell: num(rules.chaos_spell) })}</span>
    </div>
    {reading?.spell != null ? <p className="gauge-reading"><strong>{text('control.reading', { spell: num(reading.spell) })}</strong>
      <span>{text('control.window', { start: formatClock(reading.since), end: formatClock(reading.at) })}</span></p>
      : <p className="pulse-rule">{reading ? text('control.thin', { count: rules.control_min_actions }) : text('momentum.empty')}</p>}
  </section>;
}

export function LatestLine({ feed, data, elapsed }: { feed: AmbientFeed; data: ReplayData; elapsed: number }) {
  const { text, locale } = useText();
  const line = knownAt(feed.ticker, elapsed, data.timeline.firstHalfSeconds).at(-1);
  if (!line) return null;
  return <p className={`latest-line ${side(line, data)}`} aria-live="polite">
    <span>{text('ticker.latest')}</span><time>{formatClock(line.at)}</time><strong>{line.text[locale]}</strong>
  </p>;
}

export function AmbientStrip({ feed, data, elapsed }: { feed: AmbientFeed; data: ReplayData; elapsed: number }) {
  return <section className="panel pulse">
    <LatestLine feed={feed} data={data} elapsed={elapsed} />
    <div className="pulse-grid">
      <MomentumStrip feed={feed} data={data} elapsed={elapsed} />
      <ControlGauge feed={feed} data={data} elapsed={elapsed} />
    </div>
  </section>;
}

export function Ticker({ feed, data, elapsed, limit = 6 }: { feed: AmbientFeed; data: ReplayData; elapsed: number; limit?: number }) {
  const { text, locale } = useText();
  const lines = knownAt(feed.ticker, elapsed, data.timeline.firstHalfSeconds).slice(-limit).reverse();
  return <section className="panel ticker-panel"><SectionTitle title={text('feed')} />
    {lines.length ? <ol className="ticker">{lines.map(line => <li key={`${line.event_id}-${line.kind}`} className={`ticker-${line.kind}`}>
      <time>{formatClock(line.at)}</time><span className={`event-mark ${side(line, data)}`}>{line.kind === 'goal' ? '◆' : ''}</span>
      <p>{line.text[locale]}</p>
    </li>)}</ol> : <p className="muted padded">{text('feed.empty')}</p>}
  </section>;
}
