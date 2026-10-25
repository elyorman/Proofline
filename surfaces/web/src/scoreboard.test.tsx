import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { Scoreboard, estimate, scoreboard } from './Scoreboard';
import { LocaleContext } from './ui';

const render = (locale: 'en' | 'es' = 'en') =>
  renderToStaticMarkup(<LocaleContext.Provider value={locale}><Scoreboard /></LocaleContext.Provider>);

describe('record-backed scoreboard', () => {
  it('shows every recorded estimate with its interval and n, computing none', () => {
    const html = render();
    for (const run of scoreboard.detector) {
      for (const metric of run.metrics.filter(m => ['planted_recall', 'cause_precision', 'decoy_restraint'].includes(m.name))) {
        expect(html).toContain(estimate('en', metric));
        expect(html).toContain(`n=${metric.n}`);
      }
    }
    for (const comparison of scoreboard.comparisons) {
      for (const d of comparison.differences) expect(html).toContain(estimate('en', d, true));
    }
  });
  it('formats a fraction as a percentage and a difference in points', () => {
    const e = { name: 'planted_recall', value: 0.357, ci_low: 0.207, ci_high: 0.542, n: 28 };
    expect(estimate('en', e)).toBe('35.7% [20.7, 54.2] · n=28');
    expect(estimate('en', { ...e, value: 0.036, ci_low: -0.143, ci_high: 0.214 }, true)).toBe('+3.6 pp [-14.3, +21.4] · n=28');
    expect(estimate('es', e)).toBe('35,7% [20,7, 54,2] · n=28');
  });
  it('labels systems and scoring in Spanish', () => {
    const html = render('es');
    expect(html).toContain('Tres agentes');
    expect(html).toContain('Reservado');
  });
});
