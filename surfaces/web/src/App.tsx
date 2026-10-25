import { useEffect, useMemo, useState } from 'react';
import { Ask } from './Ask';
import { Analyst } from './Analyst';
import { AmbientStrip, Ticker } from './Ambient';
import { Broadcast } from './Broadcast';
import { Overlay } from './Overlay';
import { loadReplay, type ReplayData } from './data';
import { cards, cues, profile, amendments, caseFiles, answers, ambient } from './fixtures';
import type { Locale } from './i18n';
import { Insights } from './Insights';
import { MatchHeader } from './MatchHeader';
import { Activity, Pitch, involves } from './Pitch';
import { displayElapsed, displayTime, elapsedAt, linkedElapsed, parseLink, teamStats, visibleCards, type ProducerDecision, type Route } from './replay';
import { Icon, LocaleContext, SectionTitle, ViewBoundary, useText } from './ui';

const pressureCard = cards.find(card => card.id === 'ins-m01-063-pressure_shift');
const flankCard = cards.find(card => card.moment_type === 'shape_change' && card.revision === 1);
const withdrawal = cards.find(card => card.status === 'withdrawn');

export default function App() {
  const [locale, setLocale] = useState<Locale>(() => parseLink(location.hash).locale ?? (profile.language === 'es' ? 'es' : 'en'));
  return <LocaleContext.Provider value={locale}><Workspace setLocale={setLocale} /></LocaleContext.Provider>;
}

function Workspace({ setLocale }: { setLocale: (locale: Locale) => void }) {
  const { text, num, locale } = useText();
  const [route, setRoute] = useState<Route>(() => parseLink(location.hash).route);
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
    if (!data) return;
    // Deep links: `#/fan?t=70:00&lang=en` opens that route at that clock, paused.
    const follow = () => {
      const link = parseLink(location.hash);
      setRoute(link.route);
      if (link.locale) setLocale(link.locale);
      if (link.clock) {
        const target = linkedElapsed(link.clock, data.timeline);
        setElapsed(target);
        setPlaying(false);
        setDecisions(previous => previous.filter(d => d.at <= target));
      }
    };
    follow();
    window.addEventListener('hashchange', follow);
    return () => window.removeEventListener('hashchange', follow);
  }, [data, setLocale]);

  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    loadReplay(controller.signal).then(replay => {
      if (controller.signal.aborted) return;
      const start = pressureCard && displayTime(pressureCard);
      setElapsed(start ? elapsedAt(start, replay.timeline.firstHalfSeconds) : 0);
      setData(replay);
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
  const full = elapsed >= data.timeline.duration;
  const currentCards = visibleCards(cards, elapsed, firstHalf);
  const publishedRevisions = cards.filter(c => displayElapsed(c, firstHalf) <= elapsed);
  const stats = data.teams.map(team => teamStats(delivered.map(d => d.event), team.name));
  const roster = data.teams.find(team => team.name === favorite)?.players ?? data.teams[0].players;
  const openCase = (id: string) => { setSelected(id); location.hash = '/analyst'; };
  const seek = (at: number) => {
    const target = Math.max(0, Math.min(data.timeline.duration, at));
    setElapsed(target);
    setDecisions(previous => previous.filter(d => d.at <= target));
  };
  const jumpTo = (at: number) => { seek(at); setPlaying(false); };
  const jumps = [
    { key: 'start', at: 0 },
    { key: 'flank', at: flankCard ? displayElapsed(flankCard, firstHalf) : 0 },
    { key: 'press', at: pressureCard ? displayElapsed(pressureCard, firstHalf) : 0 },
    { key: 'correction', at: withdrawal ? displayElapsed(withdrawal, firstHalf) : 0 },
    ...cues.filter(c => c.kind === 'withdrawal').slice(0, 1).map(cue => ({ key: 'overlay', at: elapsedAt(cue.show_at.not_before, firstHalf) })),
    { key: 'full', at: data.timeline.duration },
  ].filter(jump => Number.isFinite(jump.at));
  const ask = <Ask answers={answers} data={data} elapsed={elapsed} onSeek={jumpTo} />;
  const modes = <div className="mode-selector" role="group" aria-label={text('mode')}>{['casual', 'data', 'player'].map(value =>
    <button aria-pressed={mode === value} className={mode === value ? 'active' : ''} key={value} onClick={() => setMode(value)}>{text(`mode.${value}`)}</button>)}</div>;
  const focusBar = mode === 'player' && <div className="focus-bar">
    <label><span>{text('favorite')}</span><select value={favorite} onChange={e => { setFavorite(e.target.value); setPlayer(data.teams.find(t => t.name === e.target.value)!.players[0].id); }}>{data.teams.map(team => <option key={team.code}>{team.name}</option>)}</select></label>
    <label><span>{text('player')}</span><select value={player} onChange={e => setPlayer(e.target.value)}>{roster.map(p => <option key={p.id} value={p.id}>{p.name} · {p.id}</option>)}</select></label>
    <strong>{text('player.events', { count: delivered.filter(({ event }) => involves(event, player)).length })}</strong>
  </div>;
  return <div className="app-shell">
    <aside className="sidebar"><a href="#/fan" className="brand" aria-label={text('brand.name')}><span className="brand-icon"><i /><i /><i /></span><span className="wordmark">{text('brand.wordmark')}<span>↗</span></span></a><p className="brand-caption">{text('brand.caption')}</p>
      <span className="nav-label">{text('nav.workspace')}</span>
      <nav aria-label={text('nav.workspace')}>{(['fan', 'analyst', 'broadcast', 'overlay'] as const).map(name => <a href={`#/${name}`} key={name} aria-label={text(`nav.${name}`)} aria-current={route === name ? 'page' : undefined} className={route === name ? 'active' : ''}><Icon name={name} /><span>{text(`nav.${name}`)}</span>{route === name && <span className="nav-active-dot" />}</a>)}</nav>
      <div className="sidebar-bottom"><div className="proof-mark"><span /><span /><span /></div><p>{text('nav.about')}</p><span className="sidebar-replay"><i />{text('fixture')}</span></div>
    </aside>
    <div className="workspace">
      <MatchHeader data={data} elapsed={elapsed} playing={playing} speed={speed} jumps={jumps}
        onToggle={() => { if (full) seek(0); setPlaying(!playing); }} onReset={() => { seek(0); setPlaying(false); setDecisions([]); }}
        onSeek={seek} onJump={jumpTo} onSpeed={setSpeed} onLocale={setLocale} />
      <main className={`main-content route-${route}`} id="main-content">
        {route !== 'fan' && <div className="page-title"><h1>{text(`nav.${route}`)}</h1><p>{text(`page.${route}.sub`)}</p></div>}
        {route === 'fan' && <ViewBoundary key="fan"><h1 className="sr-only">{text('nav.fan')}</h1><div className="fan-grid">
          <div className="fan-pitch"><Pitch data={data} elapsed={elapsed} player={mode === 'player' ? player : undefined} ambient={ambient} footer={focusBar}>{modes}</Pitch></div>
          <div className="fan-now"><Insights cards={currentCards} onOpen={openCase} mode={mode} full={full} elapsed={elapsed} firstHalf={firstHalf}
            viewer={{ club: favorite, player: mode === 'player' ? player : undefined, playerName: roster.find(p => p.id === player)?.name }} /></div>
          <div className="fan-ambient"><AmbientStrip feed={ambient} data={data} elapsed={elapsed} /></div>
          <div className="fan-more">
            {ask}
            <div className="fan-panels">
              <Ticker feed={ambient} data={data} elapsed={elapsed} />
              <section className="panel stats-panel"><SectionTitle title={text('stats')} sub={text('stats.sub')} /><div className="stats-team-head"><span>{data.teams[0].code}</span><span>{data.teams[1].code}</span></div>{(['passes', 'accuracy', 'shots', 'pressures'] as const).map(key => <div className="stat-row" key={key}><strong>{stats[0][key] === null ? '—' : num(stats[0][key], key === 'accuracy')}</strong><span>{text(`stats.${key}`)}</span><strong>{stats[1][key] === null ? '—' : num(stats[1][key], key === 'accuracy')}</strong></div>)}</section>
              <Activity data={data} elapsed={elapsed} />
            </div>
          </div>
        </div></ViewBoundary>}
        {route === 'analyst' && <ViewBoundary key="analyst"><Analyst cards={currentCards} allRevisions={publishedRevisions} selected={selected} onSelect={setSelected} amendments={amendments} files={caseFiles.filter(f => elapsedAt(f.case.window.end, firstHalf) <= elapsed)} /><div className="below-fold">{ask}</div></ViewBoundary>}
        {route === 'broadcast' && <ViewBoundary key="broadcast"><Broadcast data={data} elapsed={elapsed} cues={cues} cards={cards} decisions={decisions} ambient={ambient} onDecide={decision => setDecisions(previous => [...previous, decision])} onReset={() => setDecisions([])} /></ViewBoundary>}
        {route === 'overlay' && <ViewBoundary key="overlay"><Overlay data={data} elapsed={elapsed} cards={cards} cues={cues} decisions={decisions} ambient={ambient} /></ViewBoundary>}
        <footer className="workspace-footer"><span>{text('brand.name')}</span><p>{text('nav.about')}</p><span>{data.matchId} · {text('fixture')}</span></footer>
      </main>
    </div>
  </div>;
}
