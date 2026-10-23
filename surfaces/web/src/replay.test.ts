import { describe, expect, it } from 'vitest';
import { activityAt, applyDecisions, buildTimeline, clockAt, elapsedAt, formatClock, scoreAt, teamStats, visibleCards, visibleCues, pitchPoint } from './replay';
import { cards, cues } from './fixtures';
import { catalogs, number, t } from './i18n';
import type { Event } from './types/event';

const event = (type: string, minute: number, period: number, team = 'Northvale') => ({
  type, team, clock: { period, minute, second: 0 },
}) as Event;

const timelineWithEnds = (events: Event[]) => buildTimeline([
  ...events, event('period_end', 45, 1), event('period_end', 90, 2),
]);

describe('replay boundaries', () => {
  const timeline = buildTimeline([
    event('period_start', 0, 1), event('goal', 20, 1), event('period_end', 47, 1),
    event('period_start', 45, 2), event('goal', 60, 2, 'Harbour City'), event('period_end', 93, 2),
  ]);
  it('uses only delivered goals, including after a seek backwards', () => {
    expect(scoreAt(timeline, 0, ['Harbour City', 'Northvale'])).toEqual([0, 0]);
    expect(scoreAt(timeline, 1200, ['Harbour City', 'Northvale'])).toEqual([0, 1]);
    expect(scoreAt(timeline, 4000, ['Harbour City', 'Northvale'])).toEqual([1, 1]);
    expect(scoreAt(timeline, 0, ['Harbour City', 'Northvale'])).toEqual([0, 0]);
  });
  it('keeps first-half stoppage separate from the second half', () => {
    expect(formatClock(clockAt(46 * 60, timeline.firstHalfSeconds))).toBe('45+1:00');
    expect(formatClock(clockAt(48 * 60, timeline.firstHalfSeconds))).toBe('46:00');
  });
  it('takes both half lengths from their period_end events, including a shortened half', () => {
    const shortened = buildTimeline([event('period_end', 44, 1), event('period_end', 91, 2)]);
    expect(shortened.firstHalfSeconds).toBe(2640);
    expect(shortened.duration).toBe(2640 + 2760);
    expect(formatClock(clockAt(2640, shortened.firstHalfSeconds))).toBe('45:00');
    expect(timeline.duration).toBe(47 * 60 + 48 * 60);
  });
  it('rejects missing/duplicate period ends and events after the recorded end', () => {
    expect(() => buildTimeline([event('period_end', 45, 1)])).toThrow('Incomplete replay');
    expect(() => timelineWithEnds([event('period_end', 46, 1)])).toThrow('Incomplete replay');
    expect(() => timelineWithEnds([event('pass', 47, 1)])).toThrow('Event after period_end');
  });
  it('publishes cards at their recorded time and replaces withdrawn revisions', () => {
    expect(visibleCards(cards, 54 * 60, 2700)).toHaveLength(1); // the goal fixture
    const before = visibleCards(cards, 67 * 60, 2700);
    expect(before.find(c => c.id === 'ins-m01-055-01')?.revision).toBe(1);
    const after = visibleCards(cards, 69 * 60, 2700);
    expect(after.find(c => c.id === 'ins-m01-055-01')?.status).toBe('withdrawn');
    expect(after.filter(c => c.id === 'ins-m01-055-01')).toHaveLength(1);
    expect(visibleCards(cards, 63 * 60, 2700).some(c => c.id === 'ins-m01-063-01')).toBe(false);
  });
  it('expires overlay cues after their duration and respects their slots', () => {
    expect(visibleCues(cues, 63 * 60 + 40, 2700)).toHaveLength(1);
    expect(visibleCues(cues, 64 * 60, 2700)).toHaveLength(0);
  });
  it('mirrors both axes when the other team acts', () => {
    expect(pitchPoint({ x: 20, y: 10 }, false)).toEqual({ x: 85, y: 58 });
  });
  it('restores the original card when seeking backwards through a withdrawal', () => {
    const before = visibleCards(cards, 67 * 60, 2700);
    expect(visibleCards(cards, 69 * 60, 2700).find(c => c.id === 'ins-m01-055-01')?.revision).toBe(2);
    expect(visibleCards(cards, 67 * 60, 2700)).toEqual(before);
    expect(visibleCards(cards, 0, 2700)).toEqual([]);
  });
  it('withholds unverified full-lane cards and unpublished revisions', () => {
    const sample = cards.find(c => c.id === 'ins-m01-063-01')!;
    expect(visibleCards([{ ...sample, verification: null }], 5000, 2700)).toEqual([]);
    expect(visibleCards([{ ...sample, timing: { ...sample.timing, published_at: null } }], 5000, 2700)).toEqual([]);
    expect(visibleCards([{ ...sample, status: 'proposed' }], 5000, 2700)).toEqual([]);
  });
  it('uses the actual first-half duration for card publication', () => {
    const press = { period: 2, minute: 63, second: 40 } as const;
    const at = elapsedAt(press, 2820);
    expect(at).toBe(3940);
    expect(visibleCards(cards, at - 1, 2820).some(c => c.id === 'ins-m01-063-01')).toBe(false);
    expect(visibleCards(cards, at, 2820).some(c => c.id === 'ins-m01-063-01')).toBe(true);
  });
  it('sorts a copy of out-of-order input and does not double-count goal shots', () => {
    const events = [event('goal', 20, 1), { ...event('shot', 20, 1), outcome: 'goal' as const }, event('period_start', 0, 1)];
    const built = timelineWithEnds(events);
    expect(built.events[0].event.type).toBe('period_start');
    expect(events[0].type).toBe('goal');
    expect(scoreAt(built, 1200, ['Northvale'])).toEqual([1]);
  });
  it('expires exactly at the end of a cue duration and hides held/killed cues', () => {
    const cue = cues[0];
    expect(visibleCues([cue], 3827, 2700)).toHaveLength(1);
    expect(visibleCues([cue], 3828, 2700)).toHaveLength(0);
    expect(visibleCues([{ ...cue, status: 'held' }, { ...cue, status: 'killed' }], 3820, 2700)).toHaveLength(0);
  });
  it('waits for a dead ball inside the slot for an approved next-dead-ball cue', () => {
    const cue = { ...cues[0], show_at: { ...cues[0].show_at, mode: 'next_dead_ball' as const } };
    const events = timelineWithEnds([event('pass', 63, 2), event('foul', 64, 2)]).events;
    expect(visibleCues([cue], 3820, 2700, events)).toHaveLength(0);
    expect(visibleCues([cue], 3840, 2700, events)).toHaveLength(1);
    expect(visibleCues([cue], 3848, 2700, events)).toHaveLength(0);
    expect(visibleCues([cue], 3820, 2700)).toHaveLength(0);
    expect(visibleCues([cue], 3900, 2700, timelineWithEnds([event('foul', 65, 2)]).events)).toHaveLength(0);
  });
  it('keeps producer decisions local, ignores future decisions and cannot undo a kill', () => {
    const cue = cues[0];
    const held = { cueId: cue.cue_id, at: 3821, status: 'held' as const };
    const approved = { cueId: cue.cue_id, at: 3830, status: 'approved' as const };
    expect(applyDecisions([cue], [held], 3820, 2700)[0].status).toBe('approved');
    expect(visibleCues(applyDecisions([cue], [held], 3821, 2700), 3821, 2700)).toHaveLength(0);
    expect(visibleCues(applyDecisions([cue], [held, approved], 3830, 2700), 3830, 2700)).toHaveLength(1);
    expect(applyDecisions([cue], [{ ...held, status: 'killed' }, approved], 3830, 2700)[0].status).toBe('killed');
    expect(applyDecisions([cue], [{ ...approved, at: 3900 }], 4000, 2700)[0]).toBe(cue);
    expect(cue.status).toBe('approved');
  });
  it('allows a producer to stop an overlay after the approval slot has closed', () => {
    const cue = { ...cues[0], show_at: { ...cues[0].show_at,
      not_before: { period: 2 as const, minute: 64, second: 24 } } };
    expect(visibleCues([cue], 3866, 2700)).toHaveLength(1);
    const result = applyDecisions([cue], [{ cueId: cue.cue_id, at: 3866, status: 'killed' }], 3866, 2700);
    expect(visibleCues(result, 3866, 2700)).toHaveLength(0);
  });
  it('counts delivered actions without future leakage and returns no accuracy for an empty sample', () => {
    const built = timelineWithEnds([event('period_start', 0, 1), event('carry', 5, 1), event('carry', 10, 1)]);
    expect(activityAt(built, 300, ['Northvale']).flatMap(b => b.values).reduce((a, b) => a + b, 0)).toBe(1);
    expect(activityAt(built, 600, ['Northvale']).flatMap(b => b.values).reduce((a, b) => a + b, 0)).toBe(2);
    expect(teamStats([], 'Northvale').accuracy).toBeNull();
    expect(teamStats([{ ...event('pass', 5, 1), outcome: 'complete' }, { ...event('pass', 6, 1), outcome: 'incomplete' }], 'Northvale')).toMatchObject({ passes: 2, accuracy: 0.5 });
  });
});

describe('catalog', () => {
  it('has matching language keys and refuses a missing key', () => {
    expect(t('es', 'nav.fan')).toBe('Afición');
    expect(Object.keys(catalogs.en).sort()).toEqual(Object.keys(catalogs.es).sort());
    for (const key of Object.keys(catalogs.en)) {
      expect(t('es', key)).not.toBe('');
      expect(t('en', key).match(/\{\w+\}/g)).toEqual(t('es', key).match(/\{\w+\}/g));
    }
    expect(number('es', .83)).toBe('0,83');
    expect(t('es', 'player.events', { count: 7 })).toBe('7 intervenciones recibidas');
    expect(() => t('en', 'not-a-key')).toThrow('Missing translation');
  });
});
