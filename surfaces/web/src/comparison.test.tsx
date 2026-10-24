import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { Comparison, InvestigationCompare, sameMoment } from './InvestigationCompare';
import { caseFiles, comparisonFiles } from './fixtures';
import { LocaleContext } from './ui';

const hero = caseFiles.find(f => f.case.case_id === 'case-m01-063-pressure_shift')!;

describe('same-moment recorded comparison', () => {
  it('pairs only the matching moment, window and variants', () => {
    const pair = sameMoment(hero, comparisonFiles)!;
    expect(pair.map(f => f.variant)).toEqual(['A', 'B']);
    expect(pair[0].agents).toEqual(['tactics', 'physical', 'game_state']);
    expect(pair[1].agents).toEqual(['single']);
    expect(sameMoment(caseFiles[0], comparisonFiles)).toBeUndefined();
    expect(sameMoment(hero, [pair[0]])).toBeUndefined();
    const differentWindow = structuredClone(pair[1]);
    differentWindow.case.window.end.minute++;
    expect(sameMoment(hero, [pair[0], differentWindow])).toBeUndefined();
  });
  it('labels one recorded run, links to the scoreboard, and starts with Studio only', () => {
    const html = renderToStaticMarkup(<LocaleContext.Provider value="en"><InvestigationCompare file={hero} candidates={comparisonFiles} onScoreboard={() => {}} /></LocaleContext.Provider>);
    expect(html).toContain('one recorded A/B run');
    expect(html).toContain('Scoreboard');
    expect(html).not.toContain('class="investigation-comparison"');
    expect(html).not.toContain(' checked');
  });
  it('renders both files and their recorded code verdicts without ranking the approaches', () => {
    const pair = sameMoment(hero, comparisonFiles)!;
    const html = renderToStaticMarkup(<LocaleContext.Provider value="en"><Comparison pair={pair} /></LocaleContext.Provider>);
    expect(html).toContain('A · Three agents');
    expect(html).toContain('B · Single agent');
    expect(html.match(/class="specialist agent-/g)).toHaveLength(4);
    expect(html).toContain('hyp-single-01');
    expect(html).toContain('hyp-tactics-01');
    expect(html.match(/class="tool-log"/g)).toHaveLength(2);
  });
});
