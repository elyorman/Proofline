import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import type { Cue } from './types/cue';
import { cards, cues } from './fixtures';
import { CueGraphic, overlayTemplate, publishedCues } from './Overlay';
import { LocaleContext } from './ui';
import type { Locale } from './i18n';

const press = cards.find(card => card.id === 'ins-m01-063-pressure_shift')!;
const cue = cues.find(cue => cue.insight_id === press.id)!;
const render = (node: ReactNode, locale: Locale = 'en') =>
  renderToStaticMarkup(<LocaleContext.Provider value={locale}>{node}</LocaleContext.Provider>);

describe('template-driven overlay', () => {
  it('renders the press bar from cue fields, including before/after values', () => {
    const html = render(<CueGraphic cue={cue} />);
    expect(overlayTemplate(cue.template)).toBe('pressure');
    expect(html).toContain('data-template="pressure_shift_bar"');
    expect(html).toContain(render(<h2>{cue.fields.headline}</h2>));
    expect(html).toContain(Number(cue.fields.before).toFixed(2));
    expect(html).toContain(Number(cue.fields.after).toFixed(2));
    expect(html.match(/class="pressure-track"/g)).toHaveLength(2);
  });
  it.each(['update_banner', 'withdrawal_banner'] as const)('renders %s by template regardless of cue kind', template => {
    const fields = { headline: 'Heading from the cue', team: 'Harbour City', reason: 'Reason from the cue' };
    const html = render(<CueGraphic cue={{ ...cue, kind: 'insight', template, fields }} />);
    expect(html).toContain(`data-template="${template}"`);
    expect(html).toContain(fields.headline);
    expect(html).toContain(fields.reason);
    expect(html).not.toContain('pressure-track');
  });
  it('shows an unknown template id instead of crashing', () => {
    expect(overlayTemplate('new_template')).toBe('unknown');
    expect(render(<CueGraphic cue={{ ...cue, template: 'new_template' as Cue['template'] }} />)).toContain('new_template');
  });
  it('makes a cue available when its real card has no published_at', () => {
    expect(publishedCues([cue], [press], 68 * 60 - 1, 2700)).toEqual([]);
    expect(publishedCues([cue], [press], 68 * 60, 2700)).toEqual([cue]);
  });
  it('withholds cues linked to unverified cards or superseded revisions', () => {
    expect(publishedCues([cue], [{ ...press, verification: null }], 68 * 60, 2700)).toEqual([]);
    const withdrawal = cards.find(card => card.status === 'withdrawn')!;
    const oldCue = { ...cue, insight_id: withdrawal.id, insight_revision: 1 };
    expect(publishedCues([oldCue], cards, 71 * 60, 2700)).toEqual([]);
  });
});
