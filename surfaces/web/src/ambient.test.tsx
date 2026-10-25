import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { AmbientStrip, ControlGauge, LatestLine, MomentumStrip, Ticker } from './Ambient';
import { ambient } from './fixtures';
import { elapsedAt, knownAt } from './replay';
import { LocaleContext } from './ui';
import { number, type Locale } from './i18n';
import type { ReplayData } from './data';

// The Studio match: the first half ends at 47:03 and the second at 91:01.
const FIRST_HALF = 47 * 60 + 3;
const data: ReplayData = { matchId: 'm01', teams: [
  { name: 'Harbour City', code: 'HC', players: [] },
  { name: 'Northvale', code: 'NV', players: [] },
], timeline: { events: [], firstHalfSeconds: FIRST_HALF, duration: FIRST_HALF + 46 * 60 + 1 } };
const at = (minute: number) => elapsedAt({ period: 2, minute, second: 0 }, FIRST_HALF);
const render = (node: ReactNode, locale: Locale = 'en') =>
  renderToStaticMarkup(<LocaleContext.Provider value={locale}>{node}</LocaleContext.Provider>);

describe('ambient layer on the fan view', () => {
  it('is the exported feed of the Studio match', () => {
    expect(ambient.match_id).toBe('m01');
    expect([ambient.home, ambient.away]).toEqual(['Harbour City', 'Northvale']);
    expect(ambient.momentum.length).toBeGreaterThan(90);
    expect(ambient.ticker.some(line => line.kind === 'goal')).toBe(true);
  });
  it('draws only the momentum minutes already known at the clock', () => {
    const html = render(<MomentumStrip feed={ambient} data={data} elapsed={at(68)} />);
    const known = knownAt(ambient.momentum, at(68), FIRST_HALF);
    expect(known.length).toBeLessThan(ambient.momentum.length);
    expect(html.match(/class="bar-(home|away|level)"/g)).toHaveLength(known.length);
    const latest = known.at(-1)!;
    expect(html).toContain(`${latest.value > 0 ? 'HC' : 'NV'} +${number('en', Math.abs(latest.value))}`);
    expect(html).toContain('Match clock (min)');
    expect(html).toContain(`Shot ${ambient.rules.shot_threat} pts`);
  });
  it('reads the gauge from the last recorded window, with its anchors from the rules', () => {
    const reading = knownAt(ambient.control, at(63), FIRST_HALF).at(-1)!;
    expect(reading.at).toEqual({ period: 2, minute: 63, second: 0 });
    const html = render(<ControlGauge feed={ambient} data={data} elapsed={at(63)} />, 'es');
    expect(html).toContain(`left:${reading.chaos! * 100}%`);
    expect(html).toContain(`${number('es', reading.spell!)} acciones por posesión`);
    expect(html).toContain('58:00–63:00');
    expect(html).toContain(`${ambient.rules.control_spell} o más por posesión`);
    const thin = render(<ControlGauge feed={{ ...ambient, control: [{ ...reading, spell: null, chaos: null }] }} data={data} elapsed={at(63)} />);
    expect(thin).not.toContain('left:');
    expect(thin).toContain(`needs ${ambient.rules.control_min_actions} actions`);
  });
  it('shows ticker lines in the viewer language and never before their clock', () => {
    const future = ambient.ticker.find(line => line.kind === 'goal' && line.at.minute === 77)!;
    const past = knownAt(ambient.ticker, at(68), FIRST_HALF).at(-1)!;
    const english = render(<Ticker feed={ambient} data={data} elapsed={at(68)} />);
    const spanish = render(<Ticker feed={ambient} data={data} elapsed={at(68)} />, 'es');
    expect(english).toContain(renderToStaticMarkup(<p>{past.text.en}</p>));
    expect(spanish).toContain(renderToStaticMarkup(<p>{past.text.es}</p>));
    const goal = renderToStaticMarkup(<p>{future.text.en}</p>);
    expect(english).not.toContain(goal);
    expect(render(<Ticker feed={ambient} data={data} elapsed={at(80)} />)).toContain(goal);
    expect(render(<LatestLine feed={ambient} data={data} elapsed={0} />)).toContain('Kick-off');
    expect(render(<Ticker feed={{ ...ambient, ticker: [] }} data={data} elapsed={at(80)} />)).toContain('Match events will appear');
  });
  it('renders the whole strip at kick-off without values it does not have yet', () => {
    const html = render(<AmbientStrip feed={ambient} data={data} elapsed={0} />);
    expect(html).not.toContain('class="bar-');
    expect(html).toContain('Builds from the first minute.');
  });
});
