import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { FanRail } from './FanRail';
import { Analyst } from './Analyst';
import { cards, caseFiles } from './fixtures';
import { visibleCards } from './replay';
import { LocaleContext } from './ui';
import type { Locale } from './i18n';

const render = (node: ReactNode, locale: Locale = 'en') =>
  renderToStaticMarkup(<LocaleContext.Provider value={locale}>{node}</LocaleContext.Provider>);
const panels = { ask: <p>ask-body</p>, earlier: <p>earlier-body</p>, feed: <p>feed-body</p>, numbers: <p>numbers-body</p> };

describe('the fan rail', () => {
  it('puts Ask Proofline first and keeps every panel mounted, showing only the chosen one', () => {
    const html = render(<FanRail tab="earlier" onTab={() => {}} panels={panels} earlier={4} fresh />);
    const tabs = [...html.matchAll(/id="rail-tab-(\w+)"/g)].map(m => m[1]);
    expect(tabs).toEqual(['ask', 'earlier', 'feed', 'numbers']);
    expect(html).toContain('aria-selected="true" tabindex="0" class="rail-tab-earlier"');
    for (const name of ['ask', 'earlier', 'feed', 'numbers']) expect(html).toContain(`${name}-body`);
    expect(html.match(/role="tabpanel"[^>]*hidden=""/g)).toHaveLength(3);
    expect(html).toMatch(/id="rail-panel-earlier" role="tabpanel" aria-labelledby="rail-tab-earlier" tabindex="0">/);
    expect(html).toContain('<span class="tab-count">4</span>');
    expect(html).toContain('tab-dot');
    const spanish = render(<FanRail tab="ask" onTab={() => {}} panels={panels} earlier={0} fresh={false} />, 'es');
    expect(spanish).toContain('Pregunta a Proofline');
    expect(spanish).not.toContain('tab-count');
    expect(spanish).not.toContain('tab-dot');
  });
});

describe('the console', () => {
  const shown = visibleCards(cards, 2700 + 23 * 60, 2700);  // 68:00
  it('offers Ask Proofline as a tab whose panel stays mounted behind the others', () => {
    const html = render(<Analyst cards={shown} allRevisions={shown} selected="ins-m01-063-pressure_shift" onSelect={() => {}}
      files={caseFiles.slice(0, 1)} tab="investigation" ask={<p>ask-body</p>} />);
    expect(html).toContain('id="tab-ask"');
    expect(html).toMatch(/id="panel-ask" role="tabpanel" aria-labelledby="tab-ask" tabindex="0" hidden="">/);
    expect(html).toContain('ask-body');
    expect(html).toContain('id="panel-investigation"');
    const asking = render(<Analyst cards={shown} allRevisions={shown} selected="" onSelect={() => {}} tab="ask" ask={<p>ask-body</p>} />);
    expect(asking).not.toContain('id="panel-investigation"');
    expect(asking).toMatch(/id="panel-ask" role="tabpanel" aria-labelledby="tab-ask" tabindex="0">/);
  });
  it('keeps the disabled Run live button when no Ask is given', () => {
    const html = render(<Analyst cards={shown} allRevisions={shown} selected="" onSelect={() => {}} />);
    expect(html).not.toContain('id="tab-ask"');
    expect(html).toMatch(/<button disabled="" class="button">.*Run live<\/button>/);
  });
});
