import { describe, expect, it } from 'vitest';
import { leaders } from './replay';
import type { Event } from './types/event';

const ev = (type: string, player: string, team: string, extra: Partial<Event> = {}): Event => ({
  event_id: `${player}-${Math.random()}`, version: 1, match_id: 'm01', clock: { period: 2, minute: 60, second: 0 },
  wall_clock_ms: 0, type, team, player_id: player, outcome: 'na', ...extra,
} as Event);

describe('match leaders', () => {
  it('counts each player stat from delivered events, and takes the best sprint for speed', () => {
    const rows = leaders([
      ev('sprint', 'NV-10', 'Northvale', { qualifiers: { speed_kmh: 33.4, distance_m: 30 } }),
      ev('sprint', 'NV-10', 'Northvale', { qualifiers: { speed_kmh: 30.1, distance_m: 25 } }),
      ev('sprint', 'HC-09', 'Harbour City', { qualifiers: { speed_kmh: 34.2, distance_m: 40 } }),
      ev('pass', 'HC-06', 'Harbour City', { outcome: 'complete' }),
      ev('pass', 'HC-06', 'Harbour City', { outcome: 'incomplete' }),
      ev('shot', 'NV-09', 'Northvale', { outcome: 'on_target' }),
    ]);
    const by = Object.fromEntries(rows.map(r => [r.stat, r]));
    expect(by.sprint_distance).toMatchObject({ player: 'NV-10', value: 55 });
    expect(by.sprints).toMatchObject({ player: 'NV-10', value: 2 });
    expect(by.top_speed).toMatchObject({ player: 'HC-09', value: 34.2 });
    expect(by.passes).toMatchObject({ player: 'HC-06', value: 1 });
    expect(by.shots).toMatchObject({ player: 'NV-09', team: 'Northvale' });
    expect(by.pressures).toBeUndefined();  // a stat nobody has yet is left out
  });
  it('has nothing to say before any events', () => {
    expect(leaders([])).toEqual([]);
  });
});
