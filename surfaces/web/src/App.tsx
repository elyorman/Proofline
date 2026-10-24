import { useEffect, useMemo, useState } from 'react';
import { Analyst } from './Analyst';
import { Broadcast } from './Broadcast';
import { Overlay } from './Overlay';
import { loadReplay, type ReplayData } from './data';
import { cards, cues, profile, amendments, caseFiles } from './fixtures';
import type { Locale } from './i18n';
import { Insights } from './Insights';
import { Activity, EventFeed, Pitch } from './Pitch';
import { clockAt, displayTime, elapsedAt, formatClock, scoreAt, teamStats, visibleCards, type ProducerDecision } from './replay';
import { Crest, Icon, LocaleContext, SectionTitle, ViewBoundary, useText } from './ui';

type Route = 'fan' | 'analyst' | 'broadcast' | 'overlay';
const pressureCard = cards.find(card => card.id === 'ins-m01-063-pressure_shift');
const flankCard = cards.find(card => card.moment_type === 'shape_change' && card.revision === 1);
const withdrawal = cards.find(card => card.status === 'withdrawn');
function routeAtHash(): Route {
  const route = location.hash.replace('#/', '');
  return route === 'analyst' || route === 'broadcast' || route === 'overlay' ? route : 'fan';
}

export default function App() {
  const [locale, setLocale] = useState<Locale>(profile.language === 'es' ? 'es' : 'en');
  return <LocaleContext.Provider value={locale}><Workspace locale={locale} setLocale={setLocale} /></LocaleContext.Provider>;
}

function Workspace({ locale, setLocale }: { locale: Locale; setLocale: (locale: Locale) => void }) {
  const { text, num } = useText();
  const [route, setRoute] = useState<Route>(routeAtHash);
  const [data, setData] = useState<ReplayData | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [mode, setMode] = useState(profile.mode === 'player_focus' ? 'player' : 'casual');
  const [favorite, setFavorite] = useState(profile.favorite_club ?? '');
  const [player, setPlayer] = useState(profile.favorite_players?.[0] ?? '');
  const [selected, setSelected] = useState(pressureCard?.id ?? '');
  const [decisions, setDecisions] = useState<ProducerDecision[]>([]);

  useEffect(() => {
    const handler = () => setRoute(routeAtHash());
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    loadReplay(controller.signal).then(replay => {
      if (controller.signal.aborted) return;
      setData(replay);
      setElapsed(pressureCard ? elapsedAt(displayTime(pressureCard), replay.timeline.firstHalfSeconds) : 0);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = `${text('brand.name')} · ${text(`nav.${route}`)}`;
  }, [locale, route, text]);

  useEffect(() => {
    if (!playing || !data) return;
    let last = performance.now();
    const id = window.setInterval(() => {
      const now = performance.now();
      const delta = (now - last) / 1000;
      last = now;
      setElapsed(previous => Math.min(data.timeline.duration, previous + delta * speed));
    }, 100);
    return () => window.clearInterval(id);
  }, [playing, speed, data]);

  useEffect(() => {
    if (data && elapsed >= data.timeline.duration) setPlaying(false);
  }, [elapsed, data]);

  const delivered = useMemo(() => data?.timeline.events.filter(e => e.at <= elapsed) ?? [], [data, elapsed]);
  if (!data) return <main className="load-screen"><div className="wordmark">{text('brand.wordmark')}<span>↗</span></div>
    {error ? <><h1>{text('error.title')}</h1><p>{text('error.body')}</p><button className="button primary" onClick={() => setAttempt(n => n + 1)}>{text('error.retry')}</button></> : <p role="status">{text('loading')}</p>}
  </main>;

  const firstHalf = data.timeline.firstHalfSeconds;
  const clock = clockAt(elapsed, firstHalf);
  const full = elapsed >= data.timeline.duration;
  const score = scoreAt(data.timeline, elapsed, data.teams.map(t => t.name));
  const currentCards = visibleCards(cards, elapsed, firstHalf);
  const publishedRevisions = cards.filter(c => elapsedAt(displayTime(c), firstHalf) <= elapsed);
  const stats = data.teams.map(team => teamStats(delivered.map(d => d.event), team.name));
  const roster = data.teams.find(team => team.name === favorite)?.players ?? data.teams[0].players;
  const openCase = (id: string) => { setSelected(id); location.hash = '/analyst'; };
  const seek = (at: number) => {
    const target = Math.max(0, Math.min(data.timeline.duration, at));
    setElapsed(target);
    setDecisions(previous => previous.filter(d => d.at <= target));
  };
  const jumps = [
    { key: 'start', at: 0 },
    { key: 'flank', at: flankCard ? elapsedAt(displayTime(flankCard), firstHalf) : 0 },
    { key: 'press', at: pressureCard ? elapsedAt(displayTime(pressureCard), firstHalf) : 0 },
    ...cues.filter(c => c.kind === 'withdrawal').slice(0, 1).map(cue => ({ key: 'overlay', at: elapsedAt(cue.show_at.not_before, firstHalf) })),
    { key: 'correction', at: withdrawal ? elapsedAt(displayTime(withdrawal), firstHalf) : 0 },
    { key: 'full', at: data.timeline.duration },
  ];
  return <div className="app-shell">
    <aside className="sidebar"><a href="#/fan" className="brand" aria-label={text('brand.name')}><span className="brand-icon"><i /><i /><i /></span><span className="wordmark">{text('brand.wordmark')}<span>↗</span></span></a><p className="brand-caption">{text('brand.caption')}</p>
      <span className="nav-label">{text('nav.workspace')}</span>
      <nav aria-label={text('nav.workspace')}>{(['fan', 'analyst', 'broadcast', 'overlay'] as const).map(name => <a href={`#/${name}`} key={name} aria-label={text(`nav.${name}`)} aria-current={route === name ? 'page' : undefined} className={route === name ? 'active' : ''}><Icon name={name} /><span>{text(`nav.${name}`)}</span>{route === name && <span className="nav-active-dot" />}</a>)}</nav>
      <div className="sidebar-bottom"><div className="proof-mark"><span /><span /><span /></div><p>{text('nav.about')}</p><span className="sidebar-replay"><i />{text('fixture')}</span></div>
    </aside>
    <div className="workspace"><header className="topbar"><div className="breadcrumb"><span>{text('brand.name')}</span><span>/</span><strong>{text(`nav.${route}`)}</strong></div><div className="topbar-actions"><span className="replay-badge"><i />{text('replay')}</span><label className="locale-picker"><Icon name="globe" size={17} /><span className="sr-only">{text('language')}</span><select value={locale} onChange={e => setLocale(e.target.value as Locale)}><option value="en">{text('locale.en')}</option><option value="es">{text('locale.es')}</option></select></label></div></header>
      <main className="main-content" id="main-content"><div className="page-intro"><div><p className="eyebrow">{text('league', { match: data.matchId })}</p><h1>{text(`page.${route}`)}</h1><p>{text(`page.${route}.sub`)}</p></div></div>
        <div className="fixture-notice"><Icon name="info" size={17} /><p><strong>{text('fixture')}.</strong> {text('fixture.notice')}</p></div>
        <section className="match-bar" aria-label={text('match')}><div className="match-team home"><Crest code={data.teams[0].code} /><div><span>{text('match.home')}</span><h2>{data.teams[0].name}</h2></div></div>
          <div className="match-score"><span className="match-phase">{text(full ? 'match.full' : clock.period === 1 ? 'match.half1' : 'match.half2')}</span><strong aria-label={text('match.score')}>{score[0]}<span>:</span>{score[1]}</strong><time>{full ? formatClock(data.timeline.events.at(-1)!.event.clock) : formatClock(clock)}</time></div>
          <div className="match-team away"><div><span>{text('match.away')}</span><h2>{data.teams[1].name}</h2></div><Crest code={data.teams[1].code} away /></div>
        </section>
        <section className="playback" aria-label={text('replay')}><div className="playback-main"><button className="play-button" aria-label={text(playing ? 'pause' : 'play')} onClick={() => { if (full) seek(0); setPlaying(!playing); }}><Icon name={playing ? 'pause' : 'play'} size={17} /></button><button className="icon-button" aria-label={text('reset')} onClick={() => { seek(0); setPlaying(false); setDecisions([]); }}><Icon name="reset" size={18} /></button><time>{formatClock(clock)}</time><input aria-label={text('seek')} aria-valuetext={formatClock(clock)} type="range" min="0" max={data.timeline.duration} step="1" value={elapsed} style={{ '--progress': `${elapsed / data.timeline.duration * 100}%` } as React.CSSProperties} onChange={e => seek(Number(e.target.value))} /><label className="speed-picker"><span className="sr-only">{text('speed')}</span><select value={speed} onChange={e => setSpeed(Number(e.target.value))}>{[1, 4, 16].map(s => <option key={s} value={s}>{s}×</option>)}</select></label></div>
          <div className="moment-jumps"><span>{text('jump')}</span>{jumps.map(jump => <button key={jump.key} className={Math.abs(elapsed - jump.at) < 8 ? 'current' : ''} onClick={() => { seek(jump.at); setPlaying(false); }}>{text(`jump.${jump.key}`, { clock: formatClock(clockAt(jump.at, firstHalf)) })}</button>)}</div>
        </section>
        {route === 'fan' && <ViewBoundary key={`fan:${locale}`}><div className="fan-toolbar"><div className="mode-selector" role="group" aria-label={text('mode')}>{['casual', 'data', 'player'].map(value => <button aria-pressed={mode === value} className={mode === value ? 'active' : ''} key={value} onClick={() => setMode(value)}>{text(`mode.${value}`)}</button>)}</div><label className="club-picker"><span>{text('favorite')}</span><select value={favorite} onChange={e => { setFavorite(e.target.value); setPlayer(data.teams.find(t => t.name === e.target.value)!.players[0].id); }}>{data.teams.map(team => <option key={team.code}>{team.name}</option>)}</select></label></div>
          {mode === 'player' && <div className="player-focus-bar"><label>{text('player')}<select value={player} onChange={e => setPlayer(e.target.value)}>{roster.map(p => <option key={p.id} value={p.id}>{p.name} · {p.id}</option>)}</select></label><strong>{text('player.events', { count: delivered.filter(({ event }) => event.player_id === player || event.pass_q?.receiver_id === player).length })}</strong></div>}
          <div className="fan-layout"><div className="match-column"><Pitch data={data} elapsed={elapsed} player={mode === 'player' ? player : undefined} /><Activity data={data} elapsed={elapsed} />
            <section className="panel stats-panel"><SectionTitle title={text('stats')} sub={text('stats.sub')} /><div className="stats-team-head"><span>{data.teams[0].code}</span><span>{data.teams[1].code}</span></div>{(['passes', 'accuracy', 'shots', 'pressures'] as const).map(key => <div className="stat-row" key={key}><strong>{stats[0][key] === null ? '—' : num(stats[0][key], key === 'accuracy')}</strong><span>{text(`stats.${key}`)}</span><strong>{stats[1][key] === null ? '—' : num(stats[1][key], key === 'accuracy')}</strong></div>)}</section>
            <EventFeed events={delivered} data={data} />
          </div><Insights cards={currentCards} onOpen={openCase} mode={mode} full={full} /></div>
        </ViewBoundary>}
        {route === 'analyst' && <ViewBoundary key={`analyst:${locale}`}><Analyst cards={currentCards} allRevisions={publishedRevisions} selected={selected} onSelect={setSelected} amendments={amendments} files={caseFiles.filter(f => elapsedAt(f.case.window.end, firstHalf) <= elapsed)} /></ViewBoundary>}
        {route === 'broadcast' && <ViewBoundary key={`broadcast:${locale}`}><Broadcast data={data} elapsed={elapsed} cues={cues} cards={cards} decisions={decisions} onDecide={decision => setDecisions(previous => [...previous, decision])} onReset={() => setDecisions([])} /></ViewBoundary>}
        {route === 'overlay' && <ViewBoundary key={`overlay:${locale}`}><Overlay data={data} elapsed={elapsed} cards={cards} cues={cues} decisions={decisions} /></ViewBoundary>}
        <footer className="workspace-footer"><span>{text('brand.name')}</span><p>{text('nav.about')}</p><span>{data.matchId} · {text('fixture')}</span></footer>
      </main>
    </div>
  </div>;
}
