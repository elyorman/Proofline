import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { Ask, AnswerView, LiveProgress, answerCard, formatElapsed, questionLabel, recordedAnswer } from './Ask';
import type { LiveJob } from './types/live-job';
import { answers } from './fixtures';
import { LocaleContext } from './ui';
import type { ReplayData } from './data';
import type { Locale } from './i18n';

const data: ReplayData = { matchId: 'm01', teams: [
  { name: 'Harbour City', code: 'HC', players: [] },
  { name: 'Northvale', code: 'NV', players: [{ id: 'NV-10', name: 'Ambrel', role: 'forward' }] },
], timeline: { events: [], firstHalfSeconds: 2700, duration: 5400 } };
const render = (element: React.ReactNode, locale: Locale = 'en') => renderToStaticMarkup(<LocaleContext.Provider value={locale}>{element}</LocaleContext.Provider>);
const explained = answers.find(a => a.question.question_id === 'q1')!;
const undated = (() => { const a = structuredClone(explained); a.card!.timing.verified_at = null; a.card!.timing.published_at = null; return a; })();

describe('recorded questions', () => {
  it('matches only recorded text or localized chips, without inventing answers', () => {
    for (const answer of answers) for (const locale of ['en', 'es'] as const) {
      expect(recordedAnswer(`  ${questionLabel(answer, locale).toUpperCase()}  `, answers)).toBe(answer);
    }
    expect(recordedAnswer('Why is the goalkeeper sprinting?', answers)).toBeUndefined();
    expect(recordedAnswer('', answers)).toBeUndefined();
  });
  it('shows all five localized suggestions with recorded times on both surfaces', () => {
    const html = render(<Ask answers={answers} data={data} elapsed={0} onSeek={() => {}} />, 'es');
    expect(html.match(/aria-pressed="false"/g)).toHaveLength(5);
    expect(html).toContain('¿Quién ganará el partido?');
    expect(html).toContain('68:00');
    expect(html).toContain('76:00');
    expect(html).not.toContain('recorded-answer');
  });
  it('keeps the recorded answer and premise visible while withholding its undated card', () => {
    const html = render(<AnswerView answer={undated} data={data} elapsed={6000} />);
    expect(html).toContain(renderToStaticMarkup(<h3>{explained.text.en}</h3>));
    expect(html).toContain('Northvale has increased this measure: Long-ball share');
    expect(html).toContain('7.17 sd');
    expect(html).not.toContain('insight-card');
    expect(html).toContain('no available recorded display time');
    const spanish = render(<AnswerView answer={undated} data={data} elapsed={6000} />, 'es');
    expect(spanish).toContain(renderToStaticMarkup(<h3>{explained.text.es}</h3>));
    expect(spanish).not.toContain('insight-card');
    expect(spanish).toContain('momento de presentación');
  });
  it('shows How we know when a verified answer card has a recorded display time', () => {
    const dated = structuredClone(explained);
    dated.card!.timing.verified_at = dated.question.asked_at;
    expect(render(<AnswerView answer={dated} data={data} elapsed={6000} />)).toContain('How we know');
    expect(render(<AnswerView answer={dated} data={data} elapsed={6000} />, 'es')).toContain('Cómo lo sabemos');
  });
  it('shows a failed premise without an explanation card, including named players', () => {
    for (const answer of answers.filter(a => a.outcome === 'premise_false')) {
      const html = render(<AnswerView answer={answer} data={data} elapsed={6000} />);
      expect(html).toContain('Premise did not hold');
      expect(html).toContain('Faded');
      expect(html).not.toContain('insight-card');
      if (answer.question.question_id === 'q4') expect(html).toContain('Ambrel');
    }
  });
  it('requires explained, verified and clock-available cards', () => {
    expect(answerCard(undated, 6000, 2700)).toBeUndefined();
    expect(answerCard(explained, 6000, 2700)).toBeDefined();  // recorded answers carry the minute asked
    const dated = structuredClone(explained);
    dated.card!.timing.verified_at = dated.question.asked_at;
    expect(answerCard(dated, 6000, 2700)).toBeDefined();
    dated.card!.timing.published_at = { period: 2, minute: 76, second: 0 };
    expect(answerCard(dated, 70 * 60, 2700)).toBeUndefined();
    expect(answerCard(explained, 0, 2700)).toBeUndefined();
    const rejected = structuredClone(dated);
    rejected.card!.verification!.status = 'rejected';
    expect(answerCard(rejected, 6000, 2700)).toBeUndefined();
    rejected.card = null;
    expect(answerCard(rejected, 6000, 2700)).toBeUndefined();
  });
});

describe('live questions', () => {
  const question = { question_id: 'live-1', match_id: 'm01', asked_at: { period: 2 as const, minute: 70, second: 0 }, text: 'Why is Ambrel tired?', locale: 'en' as const };
  const turnedAway = answers.find(a => a.outcome === 'premise_false')!;
  it('lists every stage while the agents work, marking those reached, in both languages', () => {
    const job: LiveJob = { job_id: 'live-1', question, status: 'running', created_ms: 0, trace_id: 'abc',
      stages: [{ stage: 'framed', at_ms: 1 }, { stage: 'premise', at_ms: 2, note: 'beyond 1.5 sd' }] };
    const html = render(<LiveProgress job={job} />);
    expect(html.match(/<li/g)).toHaveLength(7);
    expect(html.match(/class="reached"/g)).toHaveLength(2);
    expect(html).toContain('beyond 1.5 sd');
    expect(html).toContain('Trace abc');
    const spanish = render(<LiveProgress job={job} />, 'es');
    expect(spanish).toContain('El código ejecuta cada prueba');
    expect(spanish).not.toContain('beyond 1.5 sd');
  });
  it('says a live answer was asked live, and names the player its premise is about', () => {
    const ambrel = answers.find(a => a.premise?.subject === 'NV-10')!;
    const html = render(<AnswerView answer={ambrel} data={data} elapsed={6000} live />);
    expect(html).toContain('Asked live at');
    expect(html).toContain('<strong>Ambrel · ');
    expect(render(<AnswerView answer={ambrel} data={data} elapsed={6000} />)).toContain('Recorded at');
  });
  it('shows a declined question what Proofline can answer instead', () => {
    const declined = answers.find(a => a.outcome === 'unanswerable')!;
    expect(render(<AnswerView answer={declined} data={data} elapsed={6000} />)).toContain('Proofline explains what changed in the match and why');
    expect(render(<AnswerView answer={declined} data={data} elapsed={6000} />, 'es')).toContain('Proofline explica qué cambió');
    expect(render(<AnswerView answer={explained} data={data} elapsed={6000} />)).not.toContain('Proofline explains what changed');
    expect(render(<AnswerView answer={declined} data={data} elapsed={6000} />)).toContain('Match leaders so far');
  });
  it('times a queued or running question beside its stages, outside the live region, and stops when it settles', () => {
    const running: LiveJob = { job_id: 'live-1', question, status: 'running', created_ms: 0, stages: [{ stage: 'framed', at_ms: 1 }] };
    const html = render(<LiveProgress job={running} elapsedMs={42_400} />);
    expect(html).toContain('<span class="live-timer" role="timer" aria-live="off">0:42 · usually 1–3 min</span>');
    expect(html).toContain('<section class="live-progress" aria-live="polite">');
    expect(render(<LiveProgress job={{ ...running, status: 'queued' }} elapsedMs={125_000} />, 'es')).toContain('2:05 · suele tardar 1–3 min');
    expect(render(<LiveProgress job={{ ...running, status: 'done' }} elapsedMs={42_000} />)).not.toContain('live-timer');
    expect(render(<LiveProgress job={{ ...running, status: 'failed' }} elapsedMs={42_000} />)).not.toContain('live-timer');
    expect(render(<LiveProgress job={running} />)).not.toContain('live-timer');
    expect([0, 999, 59_999, 60_000, 3_601_000, -5].map(formatElapsed)).toEqual(['0:00', '0:00', '0:59', '1:00', '60:01', '0:00']);
  });
  it('stops at the premise when it is turned away', () => {
    const job: LiveJob = { job_id: 'live-1', question, status: 'done', created_ms: 0, answer: { ...turnedAway, question },
      stages: [{ stage: 'framed', at_ms: 1 }, { stage: 'premise', at_ms: 2 }] };
    const html = render(<LiveProgress job={job} />);
    expect(html.match(/<li/g)).toHaveLength(2);
    expect(html).toContain('Answered live');
  });
});
