import { useId } from 'react';
import type { InsightCard } from './types/insight-card';
import { displayTime, formatClock, variantText } from './replay';
import { isStandInCard } from './fixtures';
import { Empty, Icon, SectionTitle, useText } from './ui';

export function useCardText() {
  const { locale } = useText();
  return (card: InsightCard, audience = 'casual') => variantText(card, audience, locale);
}

export function RejectedAlternatives({ card }: { card: InsightCard }) {
  const { text } = useText();
  if (!card.rejected_alternatives?.length) return null;
  return <section className="alternatives">
    <h3>{text('insights.alternative')}</h3>
    {card.rejected_alternatives.map((alternative, index) => <article className="alternative" key={`${alternative.hypothesis_id}-${index}`}>
      <strong>{alternative.taxonomy}</strong>
      <p>{alternative.reason}</p>
      <dl className="card-facts">
        <div><dt>{text('case.hypothesis')}</dt><dd><code>{alternative.hypothesis_id}</code></dd></div>
        <div><dt>{text('case.agent')}</dt><dd>{text(`case.role.${alternative.agent}`)}</dd></div>
        <div><dt>{text('case.rejectedBy')}</dt><dd>{text(`rejected_by.${alternative.rejected_by}`)}</dd></div>
        {alternative.team && <div><dt>{text('case.subject')}</dt><dd>{alternative.team}</dd></div>}
        {alternative.tool_call_id && <div><dt>{text('case.toolCall')}</dt><dd><code>{alternative.tool_call_id}</code></dd></div>}
      </dl>
    </article>)}
  </section>;
}

export function Evidence({ card }: { card: InsightCard }) {
  const { text, metric } = useText();
  return <div className="evidence-body">
    {!card.evidence?.length ? <p className="muted">{text('insights.noEvidence')}</p> : card.evidence.map((e, index) => <div className="evidence-metric" key={`${e.tool_call_id}-${index}`}>
      <div><strong>{text(`metric.${e.metric}`)}</strong><span>{e.subject}</span></div>
      <div className="before-after">
        <div><span>{text(`baseline.${e.baseline.window}`)}</span><strong>{metric(e.metric, e.baseline.value)}</strong></div>
        <Icon name="arrow" size={18} />
        <div><span>{text('insights.window')}</span><strong>{metric(e.metric, e.value)}</strong></div>
      </div>
      <p>{formatClock(e.window.start)}–{formatClock(e.window.end)} · {text('insights.sample', { count: e.n_events })}</p>
      <code className="evidence-tool">{e.tool_call_id}</code>
    </div>)}
    <RejectedAlternatives card={card} />
    {isStandInCard(card) && <p className="fixture-footnote">{text('fixture.detail')}</p>}
  </div>;
}

export function Insight({ card, onOpen, mode = 'casual' }: { card: InsightCard; onOpen?: (id: string) => void; mode?: string }) {
  const { text } = useText();
  const cardText = useCardText();
  const withdrawn = card.status === 'withdrawn';
  const keyEvent = card.lane === 'fast';
  const labelId = useId();
  const content = cardText(card, mode === 'data' ? 'analyst' : 'casual');
  const support = card.verification?.support_level;
  const at = displayTime(card);
  if (!at) return null;
  return <article className={`insight-card ${withdrawn ? 'withdrawn' : ''} ${keyEvent ? 'key-event' : ''}`} aria-labelledby={labelId}>
    <div className="insight-top">
      <span className="card-kind"><Icon name={withdrawn ? 'reset' : 'evidence'} size={15} />{text(isStandInCard(card) ? 'fixture.short' : 'record.backend')}</span>
      <time>{formatClock(at)}</time>
    </div>
    <p className="insight-team">{card.subject.team}<span> · {text('insights.revision', { number: card.revision ?? 1 })}</span></p>
    <h3 id={labelId}>{content ?? text('insights.noVariant')}</h3>
    <p className={`support ${withdrawn ? 'orange' : ''}`}><i />
      {withdrawn ? text('insights.withdrawn') : keyEvent ? text('insights.key')
        : text('insights.support', { level: support ? text(`support.${support}`) : text('value.unset') })}
    </p>
    <details className="insight-details" open={mode === 'data' ? true : undefined} key={mode}>
      <summary>{text('insights.evidence')}<Icon name="chevron" size={16} /></summary>
      <Evidence card={card} />
      {onOpen && <button className="text-button case-link" onClick={() => onOpen(card.id)}>{text('insights.open')}<Icon name="arrow" size={16} /></button>}
    </details>
  </article>;
}

export function Insights({ cards, onOpen, mode, full }: { cards: InsightCard[]; onOpen: (id: string) => void; mode: string; full: boolean }) {
  const { text } = useText();
  return <aside className="insights-column"><SectionTitle title={text(full ? 'recap' : 'insights')} sub={text(full ? 'recap.sub' : 'insights.sub')} />
    {cards.length ? cards.map(card => <Insight key={card.id} card={card} onOpen={onOpen} mode={mode} />)
      : <div className="panel"><Empty title={text('insights.empty')} body={text('insights.empty.sub')} /></div>}
  </aside>;
}
