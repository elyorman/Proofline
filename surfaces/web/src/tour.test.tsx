import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { TOUR_STEPS, Tour, TourInvite, markTourSeen, placeCard, tourLink, tourSeen } from './Tour';
import { recordedAnswer } from './Ask';
import { answers } from './fixtures';
import { parseClock } from './replay';
import { catalogs, t, type Locale } from './i18n';
import { LocaleContext } from './ui';

const render = (node: ReactNode, locale: Locale = 'en') =>
  renderToStaticMarkup(<LocaleContext.Provider value={locale}>{node}</LocaleContext.Provider>);

describe('the guided tour', () => {
  it('walks the card, the correction, Ask, the investigation, the scoreboard and the pending cue', () => {
    expect(TOUR_STEPS.map(s => [s.id, s.route, s.clock])).toEqual([
      ['card', 'fan', '68:00'], ['correction', 'fan', '70:00'], ['ask', 'fan', '68:00'],
      ['investigation', 'analyst', '68:00'], ['scoreboard', 'analyst', '68:00'], ['cue', 'broadcast', '70:30'],
    ]);
    expect(TOUR_STEPS.map(s => s.rail ?? s.caseTab ?? null)).toEqual(['ask', 'earlier', 'ask', 'investigation', 'evaluation', null]);
    expect(TOUR_STEPS.filter(s => s.draft).map(s => s.id)).toEqual(['ask']);
    for (const step of TOUR_STEPS) {
      expect(parseClock(step.clock)?.period).toBe(2);  // a live question needs the second half
      expect(step.targets.length).toBeGreaterThan(0);
      for (const catalog of [catalogs.en, catalogs.es]) for (const part of ['title', 'body']) {
        expect(Object.hasOwn(catalog, `tour.${step.id}.${part}`)).toBe(true);
      }
    }
  });
  it('prefills a question no recording holds, whose premise the data plainly contradicts', () => {
    // At 68:00 Harbour City's defence sprints more than in the first half, not less.
    expect(TOUR_STEPS.find(step => step.draft)?.clock).toBe('68:00');
    for (const locale of ['en', 'es'] as const) {
      const draft = t(locale, 'tour.draft');
      expect(draft).toMatch(/Harbour City/);
      expect(recordedAnswer(draft, answers)).toBeUndefined();
    }
  });
  it('leaves each step as a deep link, keeping the language the link named', () => {
    expect(tourLink(TOUR_STEPS[1])).toBe('#/fan?t=70:00');
    expect(tourLink(TOUR_STEPS[5], 'es')).toBe('#/broadcast?t=70:30&lang=es');
  });
  it('remembers a dismissal, and survives storage that is missing or throws', () => {
    const items = new Map<string, string>();
    const store = { getItem: (k: string) => items.get(k) ?? null, setItem: (k: string, v: string) => { items.set(k, v); } };
    expect(tourSeen(store)).toBe(false);
    markTourSeen(store);
    expect(tourSeen(store)).toBe(true);
    const broken = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); } };
    expect(tourSeen(broken)).toBe(false);
    expect(() => markTourSeen(broken)).not.toThrow();
    expect(tourSeen(undefined)).toBe(false);
  });
  it('puts the step card beside the highlight, else below it, else inside it, always on screen', () => {
    const view = { width: 1440, height: 900 };
    const card = { width: 340, height: 200 };
    expect(placeCard({ top: 116, left: 898, width: 513, height: 466 }, card, view)).toEqual({ top: 116, left: 542 });
    // No room on the left: to the right, kept above the bottom edge.
    expect(placeCard({ top: 700, left: 100, width: 300, height: 100 }, card, view)).toEqual({ top: 684, left: 416 });
    expect(placeCard({ top: 100, left: 20, width: 1400, height: 300 }, card, view)).toEqual({ top: 416, left: 20 });
    expect(placeCard({ top: 20, left: 20, width: 1400, height: 860 }, card, view)).toEqual({ top: 664, left: 36 });
    expect(placeCard(undefined, card, view)).toEqual({ top: 684, left: 1084 });
  });
  it('is a labelled, non-modal dialog with Back, Next and Close, in both languages', () => {
    const first = render(<Tour step={0} onStep={() => {}} onClose={() => {}} />);
    expect(first).toContain('role="dialog" aria-modal="false"');
    expect(first).toContain('Guided tour · 1 of 6');
    expect(first).toContain('The 68&#x27; card');
    expect(first).toMatch(/<button type="button" class="button" disabled="">Back<\/button>/);
    expect(first).toContain('>Next</button>');
    expect(first).toContain('aria-label="Close the tour"');
    expect(first).toContain('aria-live="polite"');
    const last = render(<Tour step={5} onStep={() => {}} onClose={() => {}} />, 'es');
    expect(last).toContain('Recorrido guiado · 6 de 6');
    expect(last).toContain('>Terminar</button>');
    expect(last).not.toMatch(/disabled="">Atrás/);
  });
  it('invites a first-time visitor to start or dismiss', () => {
    const html = render(<TourInvite onStart={() => {}} onDismiss={() => {}} />, 'es');
    expect(html).toContain('Haz el recorrido');
    expect(html).toContain('Ahora no');
  });
});
