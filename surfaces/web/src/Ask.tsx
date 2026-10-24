import { useId, useState, type FormEvent } from 'react';
import type { Answer } from './types/answer';
import type { ReplayData } from './data';
import { displayTime, elapsedAt, formatClock } from './replay';
import { t, type Locale } from './i18n';
import { Insight } from './Insights';
import { PersistenceView } from './Investigation';
import { SectionTitle, useText } from './ui';

export function questionLabel(answer: Answer, locale: Locale): string {
  const label = t(locale, `ask.question.${answer.question.question_id}`);
  return label === `question.${answer.question.question_id}` ? answer.question.text : label;
}

const normalized = (text: string) => text.normalize('NFKC').trim().replace(/\s+/g, ' ').toLocaleLowerCase();
export function recordedAnswer(query: string, answers: Answer[]): Answer | undefined {
  return answers.find(answer => [answer.question.text, questionLabel(answer, 'en'), questionLabel(answer, 'es')]
    .some(label => normalized(query) === normalized(label)));
}

export function answerCard(answer: Answer, elapsed: number, firstHalf: number) {
  const card = answer.card;
  if (answer.outcome !== 'explained' || !card || !['passed', 'corrected'].includes(card.verification?.status ?? '')
    || !['verified', 'scheduled', 'shown', 'revised'].includes(card.status ?? '')
    || elapsed < elapsedAt(answer.question.asked_at, firstHalf)
    || elapsed < elapsedAt(displayTime(card), firstHalf)) return undefined;
  return card;
}

export function AnswerView({ answer, data, elapsed }: { answer: Answer; data: ReplayData; elapsed: number }) {
  const { text, locale } = useText();
  const premise = answer.premise;
  const subject = premise ? data.teams.flatMap(team => team.players).find(p => p.id === premise.subject)?.name
    ?? (() => {
      const team = data.teams.find(team => premise.subject.startsWith(`${team.name}.`));
      return team ? text('ask.unitSubject', { team: team.name, unit: text(`unit.${premise.subject.slice(team.name.length + 1)}`) }) : premise.subject;
    })() : '';
  const card = answerCard(answer, elapsed, data.timeline.firstHalfSeconds);
  return <section className="recorded-answer" aria-live="polite">
    <span className="eyebrow">{text('ask.recordedAt', { clock: formatClock(answer.question.asked_at) })}</span>
    <span className="status">{text(`answer.${answer.outcome}`)}</span>
    <h3>{answer.text[locale] ?? answer.text.en}</h3>
    <h4>{text('ask.premise')}</h4>
    {premise ? <p>{text(`ask.premise.${premise.direction}`, { subject, metric: text(`metric.${premise.metric}`), clock: formatClock(premise.since) })}</p> : <p>{text('ask.noPremise')}</p>}
    {answer.premise_test && <PersistenceView item={answer.premise_test} />}
    {card && <Insight card={card} />}
  </section>;
}

export function Ask({ answers, data, elapsed, onSeek }: {
  answers: Answer[]; data: ReplayData; elapsed: number; onSeek: (at: number) => void;
}) {
  const { text, locale } = useText();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string>();
  const [unknown, setUnknown] = useState(false);
  const inputId = useId();
  const answer = answers.find(answer => answer.question.question_id === selected);
  const available = answer && elapsed >= elapsedAt(answer.question.asked_at, data.timeline.firstHalfSeconds);
  function choose(answer: Answer, label: string) {
    setQuery(label); setSelected(answer.question.question_id); setUnknown(false);
    onSeek(elapsedAt(answer.question.asked_at, data.timeline.firstHalfSeconds));
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const found = recordedAnswer(query, answers);
    if (found) choose(found, query);
    else { setSelected(undefined); setUnknown(true); }
  }
  return <section className="panel ask-panel">
    <SectionTitle title={text('ask.title')} sub={text('ask.replayOnly')} />
    <form onSubmit={submit} className="ask-form"><label htmlFor={inputId}>{text('ask.label')}</label>
      <div><input id={inputId} value={query} onChange={event => setQuery(event.target.value)} placeholder={text('ask.placeholder')} maxLength={300} required /><button className="button primary" type="submit">{text('ask.submit')}</button></div>
    </form>
    <div className="question-chips" aria-label={text('ask.suggestions')}>{answers.slice().sort((a, b) => a.question.question_id.localeCompare(b.question.question_id)).map(answer => <button key={`${answer.question.question_id}-${answer.variant}`} onClick={() => choose(answer, questionLabel(answer, locale))} aria-pressed={selected === answer.question.question_id}>
      {questionLabel(answer, locale)}<time>{formatClock(answer.question.asked_at)}</time>
    </button>)}</div>
    {unknown && <div className="unknown-question" role="status"><p>{text('ask.liveRequired')}</p><button className="button" disabled>{text('live')}</button></div>}
    {answer && available && <AnswerView answer={answer} data={data} elapsed={elapsed} />}
    {answer && !available && <p className="muted ask-time-note">{text('ask.future', { clock: formatClock(answer.question.asked_at) })}</p>}
  </section>;
}
