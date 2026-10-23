import { describe, expect, it } from 'vitest';
import { parseReplay } from './data';
import { scoreAt } from './replay';

const manifest = {
  match_id: 'm01',
  teams: {
    home: { name: 'Harbour City', code: 'HC', formation: '4-3-3', players: [{ player_id: 'HC-10', name: 'Test Player', role: 'forward', unit: 'attack' }] },
    away: { name: 'Northvale', code: 'NV', formation: '4-2-3-1', players: [] },
  },
};
const event = { match_id: 'm01', event_id: 'e1', type: 'period_start', team: 'Harbour City', clock: { period: 1, minute: 0, second: 0 } };
const complete = [event,
  { ...event, event_id: 'goal', type: 'goal', clock: { period: 1, minute: 20, second: 0 } },
  { ...event, event_id: 'e2', type: 'period_end', clock: { period: 1, minute: 47, second: 0 } },
  { ...event, event_id: 'e3', clock: { period: 2, minute: 45, second: 0 } },
  { ...event, event_id: 'e4', type: 'period_end', clock: { period: 2, minute: 90, second: 0 } },
].map(e => JSON.stringify(e)).join('\n');

describe('fixture loading', () => {
  it('loads the current meta.json shape without any runtime game-state fields', () => {
    const data = parseReplay(manifest, complete);
    expect(Object.keys(data).sort()).toEqual(['matchId', 'teams', 'timeline']);
    expect(data).not.toHaveProperty('seed');
    expect(data).not.toHaveProperty('score');
    expect(data.teams[0].players[0].id).toBe('HC-10');
    expect(data.timeline.firstHalfSeconds).toBe(2820);
    expect(scoreAt(data.timeline, 0, data.teams.map(t => t.name))).toEqual([0, 0]);
    expect(scoreAt(data.timeline, 1200, data.teams.map(t => t.name))).toEqual([1, 0]);
  });
  it('never reads legacy seed, score or period lengths, even when present', () => {
    const legacy = Object.defineProperties({ ...manifest }, Object.fromEntries(
      ['seed', 'score', 'period_lengths_s'].map(key => [key, { get() { throw new Error(`Read legacy ${key}`); } }]),
    ));
    const data = parseReplay(legacy, complete);
    expect(data.timeline.firstHalfSeconds).toBe(2820);
    expect(scoreAt(data.timeline, 0, data.teams.map(t => t.name))).toEqual([0, 0]);
  });
  it('refuses missing/corrupt fixtures rather than showing a plausible match', () => {
    expect(() => parseReplay({}, '')).toThrow('manifest');
    expect(() => parseReplay(manifest, '<!doctype html>')).toThrow();
    expect(() => parseReplay(manifest, '')).toThrow('Empty replay');
    expect(() => parseReplay(manifest, JSON.stringify({ ...event, match_id: 'other' }))).toThrow('event');
    expect(() => parseReplay(manifest, JSON.stringify({ ...event, clock: { period: 2, minute: 12, second: 0 } }))).toThrow('clock');
    expect(() => parseReplay(manifest, JSON.stringify({ ...event, clock: { period: 1, minute: 0, second: 75 } }))).toThrow('clock');
    expect(() => parseReplay(manifest, JSON.stringify({ ...event, type: 'unknown' }))).toThrow('event');
    expect(() => parseReplay(manifest, JSON.stringify({ ...event, outcome: 'unknown' }))).toThrow('outcome');
    expect(() => parseReplay(manifest, JSON.stringify({ ...event, start: { x: -1, y: 34 } }))).toThrow('position');
    expect(() => parseReplay(manifest, JSON.stringify(event))).toThrow('Incomplete replay');
  });
});
