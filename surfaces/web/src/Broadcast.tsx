import type { Cue } from './types/cue';
import type { InsightCard } from './types/insight-card';
import type { ReplayData } from './data';
import { applyDecisions, cueStart, elapsedAt, formatClock, visibleCues, clockAt, type ProducerDecision } from './replay';
import { Pitch } from './Pitch';
import { Empty, SectionTitle, useText } from './ui';

export function Broadcast({ data, elapsed, cues, cards, decisions, onDecide, onReset }: {
  data: ReplayData; elapsed: number; cues: Cue[]; cards: InsightCard[];
  decisions: ProducerDecision[]; onDecide: (decision: ProducerDecision) => void; onReset: () => void;
}) {
  const { text } = useText();
  const firstHalf = data.timeline.firstHalfSeconds;
  const published = cues.filter(cue => cards.some(card => card.id === cue.insight_id
    && (card.revision ?? 1) === cue.insight_revision && card.timing.published_at
    && elapsedAt(card.timing.published_at, firstHalf) <= elapsed));
  const effective = applyDecisions(published, decisions, elapsed, firstHalf);
  const active = visibleCues(effective, elapsed, firstHalf, data.timeline.events);
  return <div className="broadcast-layout"><div>
    <SectionTitle title={text('broadcast.monitor')} sub={text('broadcast.monitor.sub')} />
    <div className="program-monitor"><Pitch data={data} elapsed={elapsed} />
      <div className={`broadcast-overlay ${active.length ? 'on-air' : ''}`} aria-live="polite">
        {active.length ? active.map(cue => <div key={cue.cue_id}><span className="overlay-brand">PROOFLINE <span> / {text('fixture.short')}</span></span><h2>{text(cue.kind === 'withdrawal' ? 'broadcast.correction' : 'broadcast.press')}</h2><p>{cue.fields.team}</p></div>)
          : <span className="off-air-label">{text('broadcast.offAir')}</span>}
      </div>
    </div><p className="monitor-note">{text('broadcast.waiting')}</p>
    <section className="panel producer-log"><SectionTitle title={text('broadcast.log')}><button className="text-button" onClick={onReset} disabled={!decisions.length}>{text('broadcast.reset')}</button></SectionTitle>
      {decisions.length ? <ol>{decisions.filter(d => d.at <= elapsed).slice().reverse().map((decision, i) => <li key={i}><span>{text('broadcast.log.entry', { clock: formatClock(clockAt(decision.at, firstHalf)), action: text(`status.${decision.status}`) })}</span><code>{decision.cueId}</code></li>)}</ol> : <p className="muted padded">{text('broadcast.log.empty')}</p>}
    </section>
  </div><section className="panel cue-queue"><SectionTitle title={text('broadcast.queue')} sub={text('broadcast.local')} />
    {!effective.length && <Empty title={text('broadcast.queue.empty')} />}
    {effective.slice().reverse().map(cue => {
      const start = cueStart(cue, firstHalf, data.timeline.events);
      const isOnAir = active.some(current => current.cue_id === cue.cue_id);
      const expired = !isOnAir && (elapsed > elapsedAt(cue.show_at.not_after, firstHalf)
        || (['approved', 'aired'].includes(cue.status ?? '') && start !== undefined && elapsed >= start + cue.duration_s));
      const terminal = cue.status === 'killed' || cue.status === 'cancelled' || expired;
      const status = cue.status === 'killed' ? 'killed' : expired ? 'expired' : cue.status ?? 'pending';
      return <article className="cue-card" key={cue.cue_id}>
        <div className="cue-top"><span className="eyebrow">{text('fixture.short')}</span><span className={`status ${status === 'killed' ? 'warn' : ''}`}>{text(`status.${status}`)}</span></div>
        <h3>{text(cue.kind === 'withdrawal' ? 'broadcast.correction' : 'broadcast.press')}</h3><p>{cue.fields.team}</p>
        <small>{text('broadcast.slot', { start: formatClock(cue.show_at.not_before), end: formatClock(cue.show_at.not_after), duration: cue.duration_s })}</small>
        <div className="cue-controls">{(['approved', 'held', 'killed'] as const).map((status, i) => <button key={status} className={i === 0 ? 'button primary' : 'button'} disabled={terminal || cue.status === status} onClick={() => onDecide({ cueId: cue.cue_id, at: elapsed, status })}>{text(['broadcast.approve', 'broadcast.hold', 'broadcast.kill'][i])}</button>)}</div>
      </article>;
    })}
  </section></div>;
}
