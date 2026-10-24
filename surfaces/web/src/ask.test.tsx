import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { Ask, AnswerView, answerCard, questionLabel, recordedAnswer } from './Ask';
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
  it('shows narrator text, the plain premise, code measurements and How we know', () => {
    const html = render(<AnswerView answer={explained} data={data} elapsed={6000} />);
    expect(html).toContain(renderToStaticMarkup(<h3>{explained.text.en}</h3>));
    expect(html).toContain('Northvale has increased this measure: Long-ball share');
    expect(html).toContain('7.17 sd');
    expect(html).toContain('How we know');
    const spanish = render(<AnswerView answer={explained} data={data} elapsed={6000} />, 'es');
    expect(spanish).toContain(renderToStaticMarkup(<h3>{explained.text.es}</h3>));
    expect(spanish).toContain('Cómo lo sabemos');
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
    expect(answerCard(explained, 6000, 2700)).toBeDefined();
    expect(answerCard(explained, 0, 2700)).toBeUndefined();
    const rejected = structuredClone(explained);
    rejected.card!.verification!.status = 'rejected';
    expect(answerCard(rejected, 6000, 2700)).toBeUndefined();
    rejected.card = null;
    expect(answerCard(rejected, 6000, 2700)).toBeUndefined();
  });
});
