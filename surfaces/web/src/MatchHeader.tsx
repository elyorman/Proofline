import type { CSSProperties, Ref } from 'react';
import type { ReplayData } from './data';
import type { Locale } from './i18n';
import { clockAt, formatClock, scoreAt } from './replay';
import { Crest, Icon, useText } from './ui';

export interface Jump { key: string; at: number }

/** Score, clock, the replay timeline and its moment chips: the one clock every route shares. */
export function MatchHeader({ data, elapsed, playing, speed, jumps, onToggle, onReset, onSeek, onJump, onSpeed, onLocale, onTour, tourRef }: {
  data: ReplayData; elapsed: number; playing: boolean; speed: number; jumps: Jump[];
  onToggle: () => void; onReset: () => void; onSeek: (at: number) => void; onJump: (at: number) => void; onSpeed: (speed: number) => void; onLocale: (locale: Locale) => void;
  onTour?: () => void; tourRef?: Ref<HTMLButtonElement>;
}) {
  const { text, locale } = useText();
  const { firstHalfSeconds: firstHalf, duration } = data.timeline;
  const full = elapsed >= duration;
  const clock = clockAt(elapsed, firstHalf);
  const score = scoreAt(data.timeline, elapsed, data.teams.map(team => team.name));
  const shown = full ? formatClock(data.timeline.events.at(-1)!.event.clock) : formatClock(clock);
  const percent = (at: number) => `${at / duration * 100}%`;
  return <header className="match-header" aria-label={text('match')}>
    <div className="scorebug">
      <div className="scoreline">
        <div className="scorebug-team home"><Crest code={data.teams[0].code} small /><strong>{data.teams[0].name}</strong></div>
        <div className="scorebug-score" aria-label={`${text('match.score')}: ${score[0]}–${score[1]}`}><b>{score[0]}</b><span>:</span><b>{score[1]}</b></div>
        <div className="scorebug-team away"><strong>{data.teams[1].name}</strong><Crest code={data.teams[1].code} away small /></div>
      </div>
      <div className="scorebug-clock"><time>{shown}</time><span>{text(full ? 'match.full' : clock.period === 1 ? 'match.half1' : 'match.half2')}</span></div>
      <div className="header-tools">
        {onTour && <button type="button" className="tour-button" ref={tourRef} onClick={onTour}><Icon name="tour" size={15} />{text('tour.start')}</button>}
        <span className="replay-badge" title={text('fixture.notice')}><i />{text('replay.badge')}<span className="badge-detail"> · {text('replay.noModels')}</span></span>
        <label className="locale-picker"><Icon name="globe" size={16} /><span className="sr-only">{text('language')}</span>
          <select value={locale} onChange={e => onLocale(e.target.value as Locale)}><option value="en">{text('locale.en')}</option><option value="es">{text('locale.es')}</option></select></label>
      </div>
    </div>
    <div className="timeline" aria-label={text('replay')}>
      <div className="timeline-controls">
        <button className="play-button" aria-label={text(playing ? 'pause' : 'play')} onClick={onToggle}><Icon name={playing ? 'pause' : 'play'} size={16} /></button>
        <button className="icon-button" aria-label={text('reset')} onClick={onReset}><Icon name="reset" size={17} /></button>
        <div className="timeline-track">
          <input aria-label={text('seek')} aria-valuetext={formatClock(clock)} type="range" min="0" max={duration} step="1" value={elapsed}
            style={{ '--progress': percent(elapsed) } as CSSProperties} onChange={e => onSeek(Number(e.target.value))} />
          {jumps.filter(jump => jump.at > 0 && jump.at < duration).map(jump => <i key={jump.key} className="timeline-mark" style={{ left: percent(jump.at) }} />)}
        </div>
        <label className="speed-picker"><span className="sr-only">{text('speed')}</span>
          <select value={speed} onChange={e => onSpeed(Number(e.target.value))}>{[1, 4, 16].map(s => <option key={s} value={s}>{s}×</option>)}</select></label>
      </div>
      <div className="moment-jumps"><span>{text('jump')}</span>{jumps.map(jump => <button key={jump.key} className={Math.abs(elapsed - jump.at) < 8 ? 'current' : ''}
        onClick={() => onJump(jump.at)}>{text(`jump.${jump.key}`, { clock: formatClock(clockAt(jump.at, firstHalf)) })}</button>)}</div>
    </div>
  </header>;
}
