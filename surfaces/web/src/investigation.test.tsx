import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { Investigation } from './Investigation';
import { caseFiles } from './fixtures';
import { LocaleContext } from './ui';

const hero = caseFiles.find(f => f.case.case_id === 'case-m01-063-pressure_shift')!;
const render = (file = hero) => renderToStaticMarkup(<LocaleContext.Provider value="en"><Investigation file={file} /></LocaleContext.Provider>);

describe('recorded investigation', () => {
  it('shows the confirmation window and both-team readings from the file', () => {
    const html = render();
    expect(html).toContain('Detected at 63:00');
    expect(html).toContain('63:00–68:00');
    expect(html).toContain('3.03 sd');
    expect(html).toContain('Held');
    expect(html).toContain('Harbour City');
    expect(html).toContain('Northvale');
    expect(html).toContain('7.17');
  });
  it('shows each agent, pre-registered thresholds, code verdicts and refused proposals', () => {
    const html = render();
    expect(html.match(/class="specialist agent-/g)).toHaveLength(3);
    for (const h of hero.hypotheses) {
      expect(html).toContain(h.hypothesis_id);
      expect(html).toContain(h.taxonomy);
    }
    expect(html).toContain('At least');
    expect(html).toContain('Supported');
    expect(html).toContain('Failed');
    // A take may refuse nothing; a refused proposal is shown with its reason whenever there is one.
    const refused = structuredClone(hero);
    refused.refused = [{ agent: 'tactics', cause: 'tactical.press_intensity_up', metric: 'xg', subject: 'Harbour City', reason: 'xg is not measurable yet' }];
    expect(render(refused)).toContain(renderToStaticMarkup(<p>xg is not measurable yet</p>));
  });
  it('draws directed corollaries with the recorded result and does not recompute measured changes', () => {
    const html = render();
    expect(html.match(/class="challenge-edge"/g)).toHaveLength(hero.cross_examinations.length);
    expect(html).toContain('Corollary');
    expect(html).toContain('Weakened');
    const changed = structuredClone(hero);
    changed.cross_examinations[0].observed_change = 42.125;
    expect(render(changed)).toContain('42.13 sd');
    // Result remains the backend's recorded "weakened", even if a future record is surprising.
    expect(render(changed)).toContain('Weakened');
  });
  it('shows synthesis, checkpoint data, recovery and collapsed tool calls', () => {
    const html = render();
    expect(html).toContain(hero.ranking.why.replaceAll('&', '&amp;').replaceAll("'", '&#x27;'));
    expect(html).toContain('Synthesized');
    expect(html).toContain('<details class="tool-log">');
    expect(html).not.toContain('<details class="tool-log" open');
    const recovered = structuredClone(hero);
    recovered.case.recovered_from_checkpoint = true;
    recovered.case.checkpoints![0].agents_failed = ['physical'];
    expect(render(recovered)).toContain('Failed agents');
    expect(render(recovered)).toContain('Yes');
  });
  it('shows faded cases without inventing an investigation and lists unrun reasons', () => {
    const faded = caseFiles.find(f => f.agents.length === 0)!;
    expect(render(faded)).toContain('Faded');
    expect(render(faded)).toContain('No agents were asked');
    expect(render(faded)).not.toContain('hypothesis-card');
    const unrun = structuredClone(hero);
    unrun.unrun = ['Recorded refusal from the orchestrator'];
    expect(render(unrun)).toContain(unrun.unrun[0]);
  });
});
