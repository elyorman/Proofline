import { describe, expect, it } from 'vitest';
import { activityAt, applyDecisions, buildTimeline, clockAt, displayTime, elapsedAt, formatClock, scoreAt, teamStats, variantText, visibleCards, visibleCues, pitchPoint } from './replay';
import { cards, cues } from './fixtures';
import { catalogs, metricNumber, t } from './i18n';
import type { Event } from './types/event';
import type { Metric } from './types/insight-card';

const event = (type: string, minute: number, period: number, team = 'Northvale') => ({
  type, team, clock: { period, minute, second: 0 },
}) as Event;
const timelineWithEnds = (events: Event[]) => buildTimeline([
  ...events, event('period_end', 45, 1), event('period_end', 90, 2),
]);
const press = cards.find(c => c.moment_type === 'pressure_shift')!;
const cueFixture = { ...cues.find(c => c.template === 'pressure_shift_bar')!, show_at: {
  mode: 'immediate' as const, not_before: { period: 2 as const, minute: 63, second: 40 },
  not_after: { period: 2 as const, minute: 64, second: 25 },
} };

describe('replay boundaries', () => {
  const timeline = buildTimeline([
    event('period_start', 0, 1), event('goal', 20, 1), event('period_end', 47, 1),
    event('period_start', 45, 2), event('goal', 60, 2, 'Harbour City'), event('period_end', 93, 2),
  ]);
  it('scores only delivered goal events and restores scores after a rewind', () => {
    expect(scoreAt(timeline, 0, ['Harbour City', 'Northvale'])).toEqual([0, 0]);
    expect(scoreAt(timeline, 1200, ['Harbour City', 'Northvale'])).toEqual([0, 1]);
    expect(scoreAt(timeline, 4000, ['Harbour City', 'Northvale'])).toEqual([1, 1]);
    expect(scoreAt(timeline, 0, ['Harbour City', 'Northvale'])).toEqual([0, 0]);
    const built = timelineWithEnds([event('goal', 20, 1), { ...event('shot', 20, 1), outcome: 'goal' }]);
    expect(scoreAt(built, 1200, ['Northvale'])).toEqual([1]);
  });
  it('keeps stoppage separate and takes both half lengths from period_end', () => {
    expect(formatClock(clockAt(46 * 60, timeline.firstHalfSeconds))).toBe('45+1:00');
    expect(formatClock(clockAt(48 * 60, timeline.firstHalfSeconds))).toBe('46:00');
    const shortened = buildTimeline([event('period_end', 44, 1), event('period_end', 91, 2)]);
    expect(shortened.firstHalfSeconds).toBe(2640);
    expect(shortened.duration).toBe(2640 + 2760);
    expect(timeline.duration).toBe(47 * 60 + 48 * 60);
  });
  it('rejects missing/duplicate period ends and events after their end', () => {
    expect(() => buildTimeline([event('period_end', 45, 1)])).toThrow('Incomplete replay');
    expect(() => timelineWithEnds([event('period_end', 46, 1)])).toThrow('Incomplete replay');
    expect(() => timelineWithEnds([event('pass', 47, 1)])).toThrow('Event after period_end');
  });
  it('displays a verified card at detected_at until a publication time exists', () => {
    expect(press.timing.published_at).toBeNull();
    const at = elapsedAt(displayTime(press), 2820);
    expect(visibleCards([press], at - 1, 2820)).toEqual([]);
    expect(visibleCards([press], at, 2820)).toEqual([press]);
    const scheduled = { ...press, timing: { ...press.timing, published_at: { period: 2 as const, minute: 64, second: 0 } } };
    expect(displayTime(scheduled)).toEqual(scheduled.timing.published_at);
    expect(visibleCards([scheduled], at, 2820)).toEqual([]);
  });
  it('replaces a withdrawal in place without moving it above a newer card', () => {
    const before = visibleCards(cards, 67 * 60, 2700);
    const after = visibleCards(cards, 69 * 60, 2700);
    expect(after.map(c => c.id)).toEqual(before.map(c => c.id));
    expect(after[0].id).toBe(press.id);
    expect(after.find(c => c.id === 'ins-m01-055-01')?.status).toBe('withdrawn');
    expect(after.filter(c => c.id === 'ins-m01-055-01')).toHaveLength(1);
    expect(visibleCards(cards, 67 * 60, 2700)).toEqual(before);
    expect(visibleCards(cards, 0, 2700)).toEqual([]);
  });
  it('withholds unverified full-lane cards and unpublished proposals', () => {
    expect(visibleCards([{ ...press, verification: null }], 5000, 2700)).toEqual([]);
    expect(visibleCards([{ ...press, status: 'proposed' }], 5000, 2700)).toEqual([]);
  });
  it('gets narrative only from supplied variants', () => {
    expect(variantText(press, 'casual', 'es')).toBe(press.variants?.casual.es);
    expect(variantText({ ...press, claim: 'This claim must never be used', variants: {} }, 'casual', 'en')).toBeUndefined();
    expect(variantText(press, 'missing-audience', 'es')).toBe(press.variants?.casual.es);
  });
  it('expires overlay cues precisely and hides held/killed cues', () => {
    expect(visibleCues([cueFixture], 3827, 2700)).toHaveLength(1);
    expect(visibleCues([cueFixture], 3828, 2700)).toHaveLength(0);
    expect(visibleCues([{ ...cueFixture, status: 'held' }, { ...cueFixture, status: 'killed' }], 3820, 2700)).toEqual([]);
  });
  it('waits for an eligible dead ball inside the slot, including substitutions', () => {
    const cue = { ...cueFixture, show_at: { ...cueFixture.show_at, mode: 'next_dead_ball' as const } };
    const events = timelineWithEnds([event('card', 63, 2), event('substitution', 64, 2)]).events;
    expect(visibleCues([cue], 3820, 2700, events)).toEqual([]);
    expect(visibleCues([cue], 3840, 2700, events)).toHaveLength(1);
    expect(visibleCues([cue], 3848, 2700, events)).toEqual([]);
    expect(visibleCues([cue], 3820, 2700)).toEqual([]);
    expect(visibleCues([cue], 3900, 2700, timelineWithEnds([event('foul', 65, 2)]).events)).toEqual([]);
  });
  it('keeps producer decisions local, ignores future decisions and cannot undo a kill', () => {
    const cue = cueFixture;
    const held = { cueId: cue.cue_id, at: 3821, status: 'held' as const };
    const approved = { cueId: cue.cue_id, at: 3830, status: 'approved' as const };
    expect(applyDecisions([cue], [held], 3820, 2700)[0].status).toBe('approved');
    expect(visibleCues(applyDecisions([cue], [held], 3821, 2700), 3821, 2700)).toEqual([]);
    expect(visibleCues(applyDecisions([cue], [held, approved], 3830, 2700), 3830, 2700)).toHaveLength(1);
    expect(applyDecisions([cue], [{ ...held, status: 'killed' }, approved], 3830, 2700)[0].status).toBe('killed');
    expect(applyDecisions([cue], [{ ...approved, at: 3900 }], 4000, 2700)[0]).toBe(cue);
    expect(cue.status).toBe('approved');
  });
  it('allows a producer to stop an overlay after the approval slot closes', () => {
    const cue = { ...cueFixture, show_at: { ...cueFixture.show_at, not_before: { period: 2 as const, minute: 64, second: 24 } } };
    expect(visibleCues([cue], 3866, 2700)).toHaveLength(1);
    const result = applyDecisions([cue], [{ cueId: cue.cue_id, at: 3866, status: 'killed' }], 3866, 2700);
    expect(visibleCues(result, 3866, 2700)).toEqual([]);
  });
  it('uses delivered activity only, including at an exact bucket boundary', () => {
    const built = timelineWithEnds([event('carry', 5, 1), event('carry', 10, 1)]);
    expect(activityAt(built, 300, ['Northvale']).flatMap(b => b.values).reduce((a, b) => a + b, 0)).toBe(1);
    expect(activityAt(built, 600, ['Northvale']).flatMap(b => b.values).reduce((a, b) => a + b, 0)).toBe(2);
    expect(teamStats([], 'Northvale').accuracy).toBeNull();
    expect(teamStats([{ ...event('pass', 5, 1), outcome: 'complete' }, { ...event('pass', 6, 1), outcome: 'incomplete' }], 'Northvale')).toMatchObject({ passes: 2, accuracy: 0.5 });
  });
  it('mirrors both pitch axes for the other team', () => {
    expect(pitchPoint({ x: 20, y: 10 }, false)).toEqual({ x: 85, y: 58 });
  });
});

describe('catalogs and metric formatting', () => {
  it('keeps English and Spanish keys and placeholders equal', () => {
    expect(Object.keys(catalogs.en).sort()).toEqual(Object.keys(catalogs.es).sort());
    for (const key of Object.keys(catalogs.en)) {
      expect(t('es', key)).not.toBe('');
      expect(t('en', key).match(/\{\w+\}/g)).toEqual(t('es', key).match(/\{\w+\}/g));
    }
  });
  it('falls back to raw ids for missing catalog keys and unknown values', () => {
    expect(t('en', 'metric.new_metric')).toBe('new_metric');
    expect(t('es', 'status.new_status')).toBe('new_status');
    expect(t('en', 'missing-key')).toBe('missing-key');
    expect(metricNumber('en', 'pressure_rate', 'unknown')).toBe('unknown');
  });
  it.each([
    ['long_ball_share', .59, '59%'], ['channel_share_left', .25, '25%'],
    ['channel_share_centre', .5, '50%'], ['channel_share_right', .375, '38%'],
    ['sprint_speed', 31.25, '31.2 km/h'], ['pressure_rate', .8333333, '0.83'],
    ['sprint_count', 1.4, '1.40'], ['rhythm', 4, '4.00'],
  ])('formats %s with its metric units', (metric, value, expected) => {
    expect(metricNumber('en', metric, value)).toBe(expected);
  });
  it('localizes decimal separators while keeping every metric label available', () => {
    expect(metricNumber('es', 'pressure_rate', .83)).toBe('0,83');
    const metrics: Metric[] = ['ppda', 'press_intensity', 'pressure_rate', 'long_ball_share', 'field_tilt',
      'channel_share_left', 'channel_share_centre', 'channel_share_right', 'pass_accuracy',
      'pass_accuracy_under_pressure', 'pass_difficulty', 'xg', 'sprint_count', 'sprint_speed',
      'high_intensity_run_rate', 'momentum', 'control_chaos', 'rhythm', 'line_height', 'ball_speed',
      'shot_speed', 'possession_share', 'distance_covered'];
    for (const metric of metrics) {
      expect(Object.hasOwn(catalogs.en, `metric.${metric}`)).toBe(true);
      expect(Object.hasOwn(catalogs.es, `metric.${metric}`)).toBe(true);
    }
  });
});
