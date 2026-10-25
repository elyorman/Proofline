import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { HowWeKnow, Insights, NowCard } from './Insights';
import { Pitch, placeLabels } from './Pitch';
import { ambient, cards } from './fixtures';
import { buildTimeline, displayTime, formatClock, visibleCards } from './replay';
import { LocaleContext } from './ui';
import { catalogs, metricNumber, type Locale } from './i18n';
import type { ReplayData } from './data';
import type { Event } from './types/event';
import type { AmbientFeed } from './types/ambient';

const render = (node: ReactNode, locale: Locale = 'en') =>
  renderToStaticMarkup(<LocaleContext.Provider value={locale}>{node}</LocaleContext.Provider>);
const ev = (id: string, type: string, team: string, player: string | null, second: number, extra: Partial<Event> = {}) => ({
  event_id: id, match_id: 'm01', type, team, player_id: player, clock: { period: 1, minute: 10, second },
  start: { x: 40 + second, y: 30 }, end: { x: 50 + second, y: 32 }, outcome: 'complete', ...extra,
}) as Event;
const events = [
  ev('h1', 'pass', 'Harbour City', 'HC-07', 5, { pass_q: { distance_m: 12, ball_speed_kmh: 50, pressure_on_passer: 0, receiver_id: 'HC-09' } }),
  ev('a1', 'sprint', 'Northvale', 'NV-10', 9, { qualifiers: { speed_kmh: 33.4, distance_m: 22 } }),
  ev('a2', 'pass', 'Northvale', 'NV-04', 14, { pass_q: { distance_m: 45, ball_speed_kmh: 70, pressure_on_passer: .8, receiver_id: 'NV-09' } }),
  { ...ev('end1', 'period_end', 'Harbour City', null, 0), clock: { period: 1, minute: 45, second: 0 }, start: null, end: null },
  { ...ev('end2', 'period_end', 'Harbour City', null, 0), clock: { period: 2, minute: 90, second: 0 }, start: null, end: null },
] as Event[];
const data: ReplayData = { matchId: 'm01', teams: [
  { name: 'Harbour City', code: 'HC', players: [{ id: 'HC-07', name: 'Gollan', role: 'CM' }] },
  { name: 'Northvale', code: 'NV', players: [{ id: 'NV-10', name: 'Ambrel', role: 'CAM' }, { id: 'NV-04', name: 'Sevrin', role: 'LCB' }] },
], timeline: buildTimeline(events) };
const feed: AmbientFeed = { ...ambient, speed_tags: [{ kind: 'sprint', event_id: 'a1', at: events[1].clock, team: 'Northvale', player_id: 'NV-10', speed_kmh: 33.4 }],
  pass_badges: [{ event_id: 'a2', at: events[2].clock, team: 'Northvale', player_id: 'NV-04', difficulty: 90, distance_m: 45, pressure_on_passer: .8 }] };
const ten = 10 * 60 + 15;

describe('the live pitch', () => {
  it('shows recent play by both teams and highlights the followed player', () => {
    const html = render(<Pitch data={data} elapsed={ten} player="NV-10" ambient={feed} />);
    expect(html).toContain('home-event');
    expect(html).toContain('away-event followed');
    expect(html).toContain('player-label followed');
    expect(html).toContain('Ambrel');
    expect(html).toContain('Sevrin');
    expect(html).toContain('Following Ambrel · on the ball now');
  });
  it('says when the followed player last touched the ball instead of emptying the pitch', () => {
    const html = render(<Pitch data={data} elapsed={ten + 60} player="NV-10" />, 'es');
    expect(html).toContain('Siguiendo a Ambrel · último balón a las 10:09');
    expect(render(<Pitch data={data} elapsed={ten} player="HC-99" />)).toContain('not on the ball yet');
    expect(render(<Pitch data={data} elapsed={ten} />)).toContain('away-event');
  });
  it('tags the sprint speed and the standout pass from the ambient feed', () => {
    const html = render(<Pitch data={data} elapsed={ten} ambient={feed} />, 'es');
    expect(html).toContain('33,4 km/h');
    expect(html).toContain('Dificultad 90');
    expect(render(<Pitch data={data} elapsed={ten} />)).not.toContain('km/h');
  });
  it('places labels so that none overlap', () => {
    const placed = placeLabels(['Ambrel', 'Sevrin', '33.4 km/h', 'Difficulty 90'].map((text, i) =>
      ({ id: String(i), kind: 'name', text, x: 50, y: 30 })));
    for (const a of placed) for (const b of placed) {
      if (a === b) continue;
      const apart = a.left + a.width <= b.left || b.left + b.width <= a.left || a.top + 5 <= b.top || b.top + 5 <= a.top;
      expect(apart).toBe(true);
    }
  });
});

describe('the current card', () => {
  const press = cards.find(card => card.id === 'ins-m01-063-pressure_shift' && card.revision === 1)!;
  it('leads with How we know: recorded numbers, baselines and what was ruled out', () => {
    const html = render(<NowCard card={press} onOpen={() => {}} />, 'es');
    expect(html).toContain('Ahora');
    expect(html).toContain('Cómo lo sabemos');
    expect(html).toContain(metricNumber('es', 'pressure_rate', press.evidence![0].baseline.value));
    expect(html).toContain(metricNumber('es', 'pressure_rate', press.evidence![0].value));
    expect(html).toContain('Harbour City · ataque');
    expect(html).toContain('Cansancio de una línea');
    expect(html).toContain('Proteger la ventaja');
    expect(html.match(/Cansancio de una línea/g)).toHaveLength(1);
  });
  it('names every taxonomy cause in both languages', () => {
    const causes = ['tactical.press_intensity_up', 'tactical.press_intensity_down', 'tactical.block_deeper',
      'tactical.block_higher', 'tactical.formation_change', 'tactical.flank_overload', 'physical.unit_fatigue',
      'physical.player_fatigue', 'physical.fresh_legs_substitution', 'game_state.protecting_lead',
      'game_state.chasing_result', 'game_state.numerical_change', 'other', 'none'];
    for (const cause of causes) for (const catalog of [catalogs.en, catalogs.es]) {
      expect(Object.hasOwn(catalog, `cause.${cause}`)).toBe(true);
    }
  });
  it('says a key event carries no causal claim', () => {
    const goal = cards.find(card => card.lane === 'fast')!;
    expect(render(<HowWeKnow card={goal} />)).toContain('no causal attribution');
  });
  it('puts the latest update first, so the 70:00 withdrawal is seen, and keeps the rest in order', () => {
    const elapsed = 70 * 60 + 30;
    const shown = visibleCards(cards, elapsed, 2700);
    const html = render(<Insights cards={shown} onOpen={() => {}} mode="casual" full={false} elapsed={elapsed} firstHalf={2700} />);
    const cut = html.indexOf('Earlier in the match');
    const [now, rows] = [html.slice(0, cut), html.slice(cut)];
    expect(now).toContain('now-card withdrawn');
    expect(now).toContain('>Updated<');
    const times = [...rows.matchAll(/<summary><time>([^<]+)<\/time>/g)].map(m => m[1]);
    expect(times).toEqual(shown.filter(card => card.status !== 'withdrawn').map(card => formatClock(displayTime(card)!)));
    expect(rows).toMatch(/insight-row\s+fresh/);
    const before = render(<Insights cards={visibleCards(cards, 69 * 60, 2700)} onOpen={() => {}} mode="casual" full={false} elapsed={69 * 60} firstHalf={2700} />);
    expect(before.split('Earlier in the match')[0]).toContain('now-card ');
    expect(before.split('Earlier in the match')[0]).toContain('>Now<');
    expect(before.split('Earlier in the match')[0]).toContain('68:00');
  });
});
