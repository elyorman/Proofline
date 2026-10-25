import { useId } from 'react';
import type { InsightCard } from './types/insight-card';
import { displayElapsed, displayTime, formatClock, latestCard, variantText } from './replay';
import { isStandInCard } from './fixtures';
import { Empty, Icon, useText } from './ui';

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

type Text = (key: string, values?: Record<string, string | number>) => string;
const UNITS = ['defence', 'midfield', 'attack'];

/** "Harbour City.attack" reads "Harbour City · attack"; teams and player ids stay as recorded. */
export function subjectLabel(subject: string, text: Text) {
  const dot = subject.lastIndexOf('.');
  const unit = subject.slice(dot + 1);
  return dot > 0 && UNITS.includes(unit) ? text('ask.unitSubject', { team: subject.slice(0, dot), unit: text(`unit.${unit}`) }) : subject;
}

/** Spec 12.1's "How we know" at a glance: two recorded numbers with baselines and what was ruled out. */
export function HowWeKnow({ card }: { card: InsightCard }) {
  const { text, metric } = useText();
  const evidence = (card.evidence ?? []).slice(0, 2);
  const ruledOut = [...new Set((card.rejected_alternatives ?? []).map(a => a.taxonomy))];
  if (!evidence.length && !ruledOut.length) return <p className="how-empty">{text('insights.noEvidence')}</p>;
  return <div className="how-summary">
    <div className="how-numbers">{evidence.map((e, index) => <div className="how-number" key={`${e.tool_call_id}-${index}`}>
      <span>{text('how.subject', { metric: text(`metric.${e.metric}`), subject: subjectLabel(e.subject, text) })}</span>
      <p><small>{text(`baseline.${e.baseline.window}`)}</small><b className="before">{metric(e.metric, e.baseline.value)}</b>
        <Icon name="arrow" size={14} /><b>{metric(e.metric, e.value)}</b></p>
      <small>{formatClock(e.window.start)}–{formatClock(e.window.end)} · {text('insights.sample', { count: e.n_events })}</small>
    </div>)}</div>
    {ruledOut.length > 0 && <p className="how-ruled"><span>{text('how.ruledOut')}</span>{ruledOut.map(cause => <em key={cause}>{text(`cause.${cause}`)}</em>)}</p>}
  </div>;
}

function statusLabel(card: InsightCard, text: Text) {
  if (card.status === 'withdrawn') return text('insights.withdrawn');
  if (card.lane === 'fast') return text('insights.key');
  const level = card.verification?.support_level;
  return text('insights.support', { level: level ? text(`support.${level}`) : text('value.unset') });
}

/** Whose story a card is, for this viewer: their club or the opposition, and their player if
 * the card's evidence is about them. Presentation only: the card's facts are the same for all. */
export interface Viewer { club?: string; player?: string; playerName?: string }

export function relevance(card: InsightCard, viewer: Viewer, text: Text): string[] {
  const out: string[] = [];
  if (viewer.club) out.push(text(card.subject.team === viewer.club ? 'relevance.club' : 'relevance.opponent'));
  const about = [...(card.subject.players ?? []), ...(card.evidence ?? []).map(e => e.subject)];
  if (viewer.player && about.includes(viewer.player)) out.push(text('relevance.player', { name: viewer.playerName ?? viewer.player }));
  return out;
}

function Relevance({ card, viewer }: { card: InsightCard; viewer?: Viewer }) {
  const { text } = useText();
  if (!viewer) return null;
  return <>{relevance(card, viewer, text).map(label => <span className="relevance" key={label}>{label}</span>)}</>;
}

export function NowCard({ card, onOpen, mode = 'casual', full = false, viewer }: { card: InsightCard; onOpen?: (id: string) => void; mode?: string; full?: boolean; viewer?: Viewer }) {
  const { text } = useText();
  const cardText = useCardText();
  const labelId = useId();
  const at = displayTime(card);
  if (!at) return null;
  const withdrawn = card.status === 'withdrawn';
  return <article className={`now-card ${withdrawn ? 'withdrawn' : ''} ${card.lane === 'fast' ? 'key-event' : ''}`} aria-labelledby={labelId}>
    <div className="now-top"><span className="now-label"><i />{text(full ? 'recap' : (card.revision ?? 1) > 1 ? 'now.revised' : 'now')}</span>
      <span className="card-kind"><Icon name={withdrawn ? 'reset' : 'evidence'} size={14} />{text(isStandInCard(card) ? 'fixture.short' : 'record.backend')}</span>
      <time>{formatClock(at)}</time></div>
    <p className="insight-team">{card.subject.team}<span> · {text('insights.revision', { number: card.revision ?? 1 })}</span><Relevance card={card} viewer={viewer} /></p>
    <h3 id={labelId}>{cardText(card, mode === 'data' ? 'analyst' : 'casual') ?? text('insights.noVariant')}</h3>
    <p className={`support ${withdrawn ? 'orange' : ''}`}><i />{statusLabel(card, text)}</p>
    <section className="how"><h4>{text('insights.evidence')}</h4><HowWeKnow card={card} /></section>
    <details className="insight-details" open={mode === 'data' ? true : undefined} key={mode}>
      <summary>{text('how.all')}<Icon name="chevron" size={16} /></summary>
      <Evidence card={card} />
    </details>
    {onOpen && <button className="text-button case-link" onClick={() => onOpen(card.id)}>{text('insights.open')}<Icon name="arrow" size={16} /></button>}
  </article>;
}

export function InsightRow({ card, onOpen, mode = 'casual', fresh = false, viewer }: { card: InsightCard; onOpen?: (id: string) => void; mode?: string; fresh?: boolean; viewer?: Viewer }) {
  const { text } = useText();
  const cardText = useCardText();
  const at = displayTime(card);
  if (!at) return null;
  const withdrawn = card.status === 'withdrawn';
  return <details className={`insight-row ${withdrawn ? 'withdrawn' : ''} ${fresh ? 'fresh' : ''}`}>
    <summary><time>{formatClock(at)}</time>
      <div><p className="insight-team">{card.subject.team}{(card.revision ?? 1) > 1 && <span> · {text('now.updated', { clock: formatClock(at) })}</span>}<Relevance card={card} viewer={viewer} /></p>
        <strong>{cardText(card, mode === 'data' ? 'analyst' : 'casual') ?? text('insights.noVariant')}</strong></div>
      <span className={`status ${withdrawn ? 'warn' : ''}`}>{statusLabel(card, text)}</span></summary>
    <div className="row-body"><HowWeKnow card={card} />
      <details className="insight-details"><summary>{text('how.all')}<Icon name="chevron" size={16} /></summary><Evidence card={card} /></details>
      {onOpen && <button className="text-button case-link" onClick={() => onOpen(card.id)}>{text('insights.open')}<Icon name="arrow" size={16} /></button>}
    </div>
  </details>;
}

const FRESH_SECONDS = 180;

export function Insights({ cards, onOpen, mode, full, elapsed = Infinity, firstHalf = 0, viewer }: {
  cards: InsightCard[]; onOpen: (id: string) => void; mode: string; full: boolean; elapsed?: number; firstHalf?: number; viewer?: Viewer;
}) {
  const { text } = useText();
  // The latest update leads, so a correction is seen; the rest keep visibleCards order.
  const now = latestCard(cards, firstHalf);
  const earlier = cards.filter(card => card !== now);
  return <aside className="insights-column">
    {now ? <NowCard card={now} onOpen={onOpen} mode={mode} full={full} viewer={viewer} />
      : <div className="panel now-empty"><Empty title={text('insights.empty')} body={text('insights.empty.sub')} /></div>}
    {earlier.length > 0 && <section className="earlier" aria-label={text('now.earlier')}><h3>{text('now.earlier')}</h3>
      {earlier.map(card => <InsightRow key={card.id} card={card} onOpen={onOpen} mode={mode} viewer={viewer}
        fresh={elapsed - displayElapsed(card, firstHalf) < FRESH_SECONDS} />)}
    </section>}
  </aside>;
}
