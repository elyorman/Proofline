import { useId } from 'react';
import type { InsightCard } from './types/insight-card';
import { formatClock } from './replay';
import { Empty, Icon, SectionTitle, useText } from './ui';

export function useCardText() {
  const { locale } = useText();
  return (card: InsightCard, audience = 'casual') => card.variants?.[audience]?.[locale]
    ?? card.variants?.casual?.[locale] ?? card.claim;
}

export function Evidence({ card }: { card: InsightCard }) {
  const { text, num } = useText();
  return <div className="evidence-body">
    {!card.evidence?.length ? <p className="muted">{text('insights.noEvidence')}</p> : card.evidence.map((e, i) => <div className="evidence-metric" key={i}>
      <div><strong>{text(`metric.${e.metric}`)}</strong><span>{e.subject}</span></div>
      <div className="before-after"><div><span>{text('insights.baseline')}</span><strong>{num(e.baseline.value, e.metric !== 'pressure_rate')}</strong></div><Icon name="arrow" size={18} /><div><span>{text('insights.window')}</span><strong>{num(e.value, e.metric !== 'pressure_rate')}</strong></div></div>
      <p>{formatClock(e.window.start)}–{formatClock(e.window.end)} · {text('insights.sample', { count: e.n_events })}</p>
    </div>)}
    {!!card.rejected_alternatives?.length && <div className="alternative"><span>{text('insights.alternative')}</span><p>{text('insights.alternative.text')}</p></div>}
    <p className="fixture-footnote">{text('fixture.detail')}</p>
  </div>;
}

export function Insight({ card, onOpen, mode = 'casual' }: { card: InsightCard; onOpen: (id: string) => void; mode?: string }) {
  const { text } = useText();
  const cardText = useCardText();
  const withdrawn = card.status === 'withdrawn';
  const keyEvent = card.lane === 'fast';
  const labelId = useId();
  return <article className={`insight-card ${withdrawn ? 'withdrawn' : ''} ${keyEvent ? 'key-event' : ''}`} aria-labelledby={labelId}>
    <div className="insight-top"><span className="card-kind">{keyEvent ? <span>◆</span> : <Icon name={withdrawn ? 'reset' : 'evidence'} size={15} />}{text(withdrawn ? 'insights.withdrawn' : keyEvent ? 'insights.key' : 'fixture.short')}</span><time>{formatClock(card.timing.published_at!)}</time></div>
    <p className="insight-team">{card.subject.team}<span> · {text('insights.revision', { number: card.revision ?? 1 })}</span></p>
    <h3 id={labelId}>{cardText(card, mode === 'data' ? 'analyst' : 'casual')}</h3>
    {!keyEvent && <p className={`support ${withdrawn ? 'orange' : ''}`}><i />{text(withdrawn ? 'insights.updated' : 'insights.support')}</p>}
    <details className="insight-details" open={mode === 'data' ? true : undefined} key={mode}>
      <summary>{text('insights.evidence')}<Icon name="chevron" size={16} /></summary>
      <Evidence card={card} />
      <button className="text-button case-link" onClick={() => onOpen(card.id)}>{text('insights.open')}<Icon name="arrow" size={16} /></button>
    </details>
  </article>;
}

export function Insights({ cards, onOpen, mode, full }: { cards: InsightCard[]; onOpen: (id: string) => void; mode: string; full: boolean }) {
  const { text } = useText();
  return <aside className="insights-column"><SectionTitle title={text(full ? 'recap' : 'insights')} sub={text(full ? 'recap.sub' : 'insights.sub')} />
    {cards.length ? cards.map(card => <Insight key={`${card.id}-${card.revision}`} card={card} onOpen={onOpen} mode={mode} />)
      : <div className="panel"><Empty title={text('insights.empty')} body={text('insights.empty.sub')} /></div>}
  </aside>;
}
