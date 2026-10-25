import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import type { Answer } from './types/answer';
import type { LiveJob } from './types/live-job';
import type { ReplayData } from './data';
import { askLive, followLive, LIVE_API, LiveRefused } from './live';
import { clockAt, displayElapsed, elapsedAt, formatClock } from './replay';
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
    || !Number.isFinite(displayElapsed(card, firstHalf))
    || elapsed < displayElapsed(card, firstHalf)) return undefined;
  return card;
}

export function AnswerView({ answer, data, elapsed, live = false }: { answer: Answer; data: ReplayData; elapsed: number; live?: boolean }) {
  const { text, locale } = useText();
  const premise = answer.premise;
  const subject = premise ? data.teams.flatMap(team => team.players).find(p => p.id === premise.subject)?.name
    ?? (() => {
      const team = data.teams.find(team => premise.subject.startsWith(`${team.name}.`));
      return team ? text('ask.unitSubject', { team: team.name, unit: text(`unit.${premise.subject.slice(team.name.length + 1)}`) }) : premise.subject;
    })() : '';
  const card = answerCard(answer, elapsed, data.timeline.firstHalfSeconds);
  return <section className="recorded-answer" aria-live="polite">
    <span className="eyebrow">{text(live ? 'ask.live.answeredAt' : 'ask.recordedAt', { clock: formatClock(answer.question.asked_at) })}</span>
    <span className="status">{text(`answer.${answer.outcome}`)}</span>
    <h3>{answer.text[locale] ?? answer.text.en}</h3>
    <h4>{text('ask.premise')}</h4>
    {premise ? <p>{text(`ask.premise.${premise.direction}`, { subject, metric: text(`metric.${premise.metric}`), clock: formatClock(premise.since) })}</p> : <p>{text('ask.noPremise')}</p>}
    {answer.premise_test && <PersistenceView item={answer.premise_test} label={premise && answer.premise_test.subject === premise.subject ? subject : undefined} />}
    {card && <Insight card={card} />}
    {answer.outcome === 'explained' && answer.card && !card && <p className="muted ask-time-note">{text('ask.cardUnavailable')}</p>}
  </section>;
}

const STAGES = ['framed', 'premise', 'preregistered', 'tested', 'cross_examined', 'synthesized', 'verified'] as const;

/** A live question's stages as the API reports them; a premise turned away stops after two. */
export function LiveProgress({ job }: { job: LiveJob }) {
  const { text, locale } = useText();
  const settled = job.status === 'done' || job.status === 'failed';
  const stages = job.stages ?? [];
  const shown = settled && job.answer?.outcome !== 'explained' ? STAGES.filter(s => stages.some(r => r.stage === s)) : STAGES;
  return <section className="live-progress" aria-live="polite">
    <span className="eyebrow">{text('ask.live.asking', { clock: formatClock(job.question.asked_at), question: job.question.text })}</span>
    <span className={`status live-${job.status}`}>{text(`ask.live.status.${job.status}`)}</span>
    <ol>{shown.map(stage => {
      const reached = stages.find(s => s.stage === stage);
      // Notes are the backend's own English; in Spanish the stage names carry the meaning.
      return <li key={stage} className={reached ? 'reached' : ''}><span>{text(`ask.live.stage.${stage}`)}</span>{locale === 'en' && reached?.note && <small>{reached.note}</small>}</li>;
    })}</ol>
    {!settled && <p className="muted">{text('ask.live.slow')}</p>}
    {job.trace_id && <p className="muted live-trace">{text('ask.live.trace', { id: job.trace_id })}</p>}
  </section>;
}

type LiveProblem = { reason: string; values: Record<string, string | number> };

export function Ask({ answers, data, elapsed, onSeek }: {
  answers: Answer[]; data: ReplayData; elapsed: number; onSeek: (at: number) => void;
}) {
  const { text, locale } = useText();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string>();
  const [unknown, setUnknown] = useState(false);
  const [live, setLive] = useState<LiveJob>();
  const [problem, setProblem] = useState<LiveProblem>();
  const following = useRef<AbortController | undefined>(undefined);
  useEffect(() => () => following.current?.abort(), []);
  const inputId = useId();
  const answer = answers.find(answer => answer.question.question_id === selected);
  const available = answer && elapsed >= elapsedAt(answer.question.asked_at, data.timeline.firstHalfSeconds);
  function choose(answer: Answer, label: string) {
    setQuery(label); setSelected(answer.question.question_id); setUnknown(false); setLive(undefined); setProblem(undefined);
    onSeek(elapsedAt(answer.question.asked_at, data.timeline.firstHalfSeconds));
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const found = recordedAnswer(query, answers);
    if (found) { choose(found, query); return; }
    setSelected(undefined); setLive(undefined); setProblem(undefined);
    if (!LIVE_API) { setUnknown(true); return; }
    setUnknown(false);
    const asked = clockAt(elapsed, data.timeline.firstHalfSeconds);
    if (asked.period !== 2) { setProblem({ reason: 'first_half', values: {} }); return; }
    following.current?.abort();
    const control = new AbortController();
    following.current = control;
    askLive({ match_id: data.matchId, asked_at: asked, text: query.trim(), locale })
      .then(job => { setLive(job); return followLive(job, setLive, { signal: control.signal }); })
      .catch(error => setProblem(error instanceof LiveRefused && error.reason !== 'unconfigured'
        ? { reason: error.reason, values: { seconds: error.retryAfterS ?? 60, detail: error.detail ?? '' } }
        : { reason: 'unavailable', values: {} }));
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
    {problem && <div className="unknown-question" role="status"><p>{text(`ask.live.error.${problem.reason}`, problem.values)}</p></div>}
    {live && <LiveProgress job={live} />}
    {live?.status === 'done' && live.answer && <AnswerView answer={live.answer as Answer} data={data} live elapsed={Math.max(elapsed, elapsedAt(live.question.asked_at, data.timeline.firstHalfSeconds))} />}
    {answer && available && <AnswerView answer={answer} data={data} elapsed={elapsed} />}
    {answer && !available && <p className="muted ask-time-note">{text('ask.future', { clock: formatClock(answer.question.asked_at) })}</p>}
  </section>;
}
