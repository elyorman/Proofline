import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { Investigation, caseFunnel } from './Investigation';
import { caseFiles, cards } from './fixtures';
import { LocaleContext } from './ui';
import type { InsightCard } from './types/insight-card';

const hero = caseFiles.find(f => f.case.case_id === 'case-m01-063-pressure_shift')!;
const heroCard = cards.find(c => c.id === 'ins-m01-063-pressure_shift' && c.revision === 1)!;
const render = (file = hero, card?: InsightCard) => renderToStaticMarkup(<LocaleContext.Provider value="en"><Investigation file={file} card={card} /></LocaleContext.Provider>);

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
  it('sums the investigation up in a funnel tallied from the recorded file and its card', () => {
    expect(caseFunnel(hero, heroCard)).toEqual({
      agents: ['tactics', 'physical', 'game_state'], registered: 6, refused: 0, tested: 6, kept: 3, failed: 3,
      counter: { holds: 1, weakened: 2, refuted: 0, unrun: 2 }, outcome: 'explained',
      primary: { id: 'hyp-tactics-01', cause: 'tactical.press_intensity_up' }, verdict: 'passed', support: 'strong',
    });
    const html = render(hero, heroCard);
    expect(html).toContain('The investigation at a glance');
    expect(html).toContain('3 of 6');
    expect(html).toContain('Failed their own prediction: 3');
    expect(html).toContain('Refused or not measurable: 2');
    expect(html).toContain('<strong>Explained: Press stepped up</strong>');
    expect(html).toContain('Verifier: Passed · Strong');
    const spanish = renderToStaticMarkup(<LocaleContext.Provider value="es"><Investigation file={hero} card={heroCard} /></LocaleContext.Provider>);
    expect(spanish).toContain('3 de 6');
    expect(spanish).toContain('Verificador: Aprobado · Fuerte');
    expect(spanish).toContain('Presión intensificada');
  });
  it('reads every funnel count from the recorded verdicts, and the verdict only from this case\'s card', () => {
    const changed = structuredClone(hero);
    changed.tests[0].outcome = 'failed';
    (changed.cross_examinations[1] as { result?: string }).result = 'refuted';
    changed.refused = [{ agent: 'physical', cause: 'physical.unit_fatigue', metric: 'xg', subject: 'Harbour City', reason: 'not measurable' }];
    changed.unrun = [];
    changed.ranking = { ...changed.ranking, outcome: 'none', primary: null };
    expect(caseFunnel(changed)).toMatchObject({ kept: 2, failed: 4, refused: 1, counter: { holds: 0, weakened: 2, refuted: 1, unrun: 0 }, outcome: 'none' });
    expect(caseFunnel(changed)).not.toHaveProperty('primary');
    expect(caseFunnel(hero)).not.toHaveProperty('verdict');
    expect(caseFunnel(hero, cards.find(c => c.case_id !== hero.case.case_id && c.verification))).not.toHaveProperty('verdict');
    expect(render(hero)).not.toContain('Verifier:');
    const faded = caseFiles.find(f => f.agents.length === 0)!;
    expect(caseFunnel(faded)).toBeUndefined();
    expect(render(faded)).not.toContain('case-funnel');
  });
  it('shows faded cases without inventing an investigation and lists unrun reasons', () => {
    const faded = caseFiles.find(f => f.agents.length === 0)!;
    expect(render(faded)).toContain('Within ordinary play');
    expect(render(faded)).toContain('No agents were asked');
    expect(render(faded)).not.toContain('hypothesis-card');
    const unrun = structuredClone(hero);
    unrun.unrun = ['Recorded refusal from the orchestrator'];
    expect(render(unrun)).toContain(unrun.unrun[0]);
  });
});
