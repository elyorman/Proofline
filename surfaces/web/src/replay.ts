import type { Event, MatchClock, Point } from './types/event';
import type { InsightCard } from './types/insight-card';
import type { Cue } from './types/cue';

export interface TimedEvent { event: Event; at: number }
export interface Timeline {
  events: TimedEvent[];
  firstHalfSeconds: number;
  duration: number;
}

export function elapsedAt(clock: MatchClock, firstHalfSeconds: number): number {
  return clock.period === 1 ? clock.minute * 60 + clock.second
    : firstHalfSeconds + (clock.minute - 45) * 60 + clock.second;
}

export function buildTimeline(events: Event[]): Timeline {
  if (!events.length) throw new Error('Empty replay');
  const periodSeconds = (clock: MatchClock) => (clock.minute - (clock.period === 1 ? 0 : 45)) * 60 + clock.second;
  const halfLengths = ([1, 2] as const).map(period => {
    const ends = events.filter(e => e.type === 'period_end' && e.clock.period === period);
    if (ends.length !== 1) throw new Error(`Incomplete replay: period ${period} needs one period_end event`);
    const length = periodSeconds(ends[0].clock);
    if (length <= 0) throw new Error('Invalid period_end clock');
    return length;
  });
  const firstHalfSeconds = halfLengths[0];
  if (events.some(e => periodSeconds(e.clock) > halfLengths[e.clock.period - 1])) {
    throw new Error('Event after period_end');
  }
  const timed = events.map(event => ({ event, at: elapsedAt(event.clock, firstHalfSeconds) }))
    .sort((a, b) => a.at - b.at);
  return { events: timed, firstHalfSeconds, duration: halfLengths[0] + halfLengths[1] };
}

export function clockAt(elapsed: number, firstHalfSeconds: number): MatchClock {
  const seconds = Math.max(0, Math.floor(elapsed));
  if (seconds < firstHalfSeconds) return { period: 1, minute: Math.floor(seconds / 60), second: seconds % 60 };
  const secondHalf = seconds - firstHalfSeconds;
  return { period: 2, minute: 45 + Math.floor(secondHalf / 60), second: secondHalf % 60 };
}

export function formatClock(clock: MatchClock): string {
  const base = clock.period === 1 ? 45 : 90;
  const minutes = clock.minute >= base ? `${base}+${clock.minute - base}` : String(clock.minute).padStart(2, '0');
  return `${minutes}:${String(clock.second).padStart(2, '0')}`;
}

/** Reads the clock's text forms: "70:00", "45+2:10", "90+3" or a bare minute, "63". */
export function parseClock(text: string): MatchClock | undefined {
  const m = /^(\d{1,3})(?:\+(\d{1,2}))?(?::(\d{2}))?$/.exec(text.trim());
  if (!m) return undefined;
  const base = Number(m[1]);
  const second = m[3] === undefined ? 0 : Number(m[3]);
  if (second > 59) return undefined;
  if (m[2] !== undefined) {
    if (base !== 45 && base !== 90) return undefined;
    return { period: base === 45 ? 1 : 2, minute: base + Number(m[2]), second };
  }
  return base > 130 ? undefined : { period: base < 45 ? 1 : 2, minute: base, second };
}

export type Route = 'fan' | 'analyst' | 'broadcast' | 'overlay';
export interface Link { route: Route; clock?: MatchClock; locale?: 'en' | 'es' }

/** A deep link: `#/analyst?t=68:00&lang=en`. Unknown routes open the fan view. */
export function parseLink(hash: string): Link {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const route = (['analyst', 'broadcast', 'overlay'] as const).find(name => name === path) ?? 'fan';
  const params = new URLSearchParams(query);
  const lang = params.get('lang');
  // A query string decodes '+' as a space; a clock never contains one, so "45+2:10" survives.
  const t = params.get('t')?.replaceAll(' ', '+');
  return {
    route,
    ...(t && parseClock(t) ? { clock: parseClock(t) } : {}),
    ...(lang === 'en' || lang === 'es' ? { locale: lang } : {}),
  };
}

/** Where a linked clock lands in this replay: a first-half clock never spills past half-time. */
export function linkedElapsed(clock: MatchClock, timeline: Timeline): number {
  const at = elapsedAt(clock, timeline.firstHalfSeconds);
  return Math.max(0, Math.min(clock.period === 1 ? timeline.firstHalfSeconds : timeline.duration, at));
}

/** Items already known at `elapsed`: the replay never shows a value before its clock. */
export function knownAt<T extends { at: MatchClock }>(items: T[], elapsed: number, firstHalfSeconds: number): T[] {
  return items.filter(item => elapsedAt(item.at, firstHalfSeconds) <= elapsed);
}

export function scoreAt(timeline: Timeline, elapsed: number, teams: string[]): number[] {
  return teams.map(team => timeline.events.filter(({ event, at }) =>
    at <= elapsed && event.type === 'goal' && event.team === team).length);
}

export function displayTime(card: InsightCard): MatchClock | undefined {
  return card.timing.published_at ?? card.timing.verified_at ?? undefined;
}

export function displayElapsed(card: InsightCard, firstHalfSeconds: number): number {
  const time = displayTime(card);
  return time ? elapsedAt(time, firstHalfSeconds) : Infinity;
}

export function variantText(card: InsightCard, audience: string, locale: string): string | undefined {
  // A missing translation may use another supplied variant, never a fabricated claim.
  return card.variants?.[audience]?.[locale] ?? card.variants?.casual?.[locale]
    ?? card.variants?.[audience]?.en ?? card.variants?.casual?.en;
}

export function visibleCards(cards: InsightCard[], elapsed: number, firstHalfSeconds: number): InsightCard[] {
  const latest = new Map<string, InsightCard>();
  const firstDisplay = new Map<string, number>();
  for (const card of cards) {
    if (!['verified', 'scheduled', 'shown', 'revised', 'withdrawn'].includes(card.status ?? '')) continue;
    const at = displayElapsed(card, firstHalfSeconds);
    if (!Number.isFinite(at)) continue;
    if (at > elapsed) continue;
    if (card.lane !== 'fast' && card.status !== 'withdrawn' && !['passed', 'corrected'].includes(card.verification?.status ?? '')) continue;
    if (card.status === 'withdrawn' && card.verification?.status !== 'rejected') continue;
    firstDisplay.set(card.id, Math.min(firstDisplay.get(card.id) ?? at, at));
    if ((latest.get(card.id)?.revision ?? 0) < (card.revision ?? 1)) latest.set(card.id, card);
  }
  return [...latest.values()].sort((a, b) =>
    firstDisplay.get(b.id)! - firstDisplay.get(a.id)!);
}

/** The card whose current revision was shown most recently. At the same moment a revision (a
 * card the viewer already read, settled or corrected) leads a new card; other ties keep `visibleCards` order. */
export function latestCard(cards: InsightCard[], firstHalfSeconds: number): InsightCard | undefined {
  return cards.reduce<InsightCard | undefined>((best, card) => {
    if (!best) return card;
    const [at, bestAt] = [displayElapsed(card, firstHalfSeconds), displayElapsed(best, firstHalfSeconds)];
    return at > bestAt || (at === bestAt && (card.revision ?? 1) > (best.revision ?? 1)) ? card : best;
  }, undefined);
}

const DEAD_BALL = new Set(['goal', 'foul', 'set_piece', 'substitution']);

export function cueStart(cue: Cue, firstHalfSeconds: number, events: TimedEvent[] = []): number | undefined {
  const start = elapsedAt(cue.show_at.not_before, firstHalfSeconds);
  const end = elapsedAt(cue.show_at.not_after, firstHalfSeconds);
  if (cue.show_at.mode === 'immediate' || cue.status === 'aired') return start;
  return events.find(({ event, at }) => at >= start && at <= end && DEAD_BALL.has(event.type))?.at;
}

export function visibleCues(cues: Cue[], elapsed: number, firstHalfSeconds: number, events?: TimedEvent[]): Cue[] {
  return cues.filter(cue => {
    if (!['approved', 'aired'].includes(cue.status ?? '')) return false;
    const start = cueStart(cue, firstHalfSeconds, events);
    return start !== undefined && elapsed >= start && elapsed < start + cue.duration_s
      && start <= elapsedAt(cue.show_at.not_after, firstHalfSeconds);
  });
}

export interface ProducerDecision {
  cueId: string;
  at: number;
  status: 'approved' | 'held' | 'killed';
}

export function applyDecisions(cues: Cue[], decisions: ProducerDecision[], elapsed: number, firstHalfSeconds: number): Cue[] {
  return cues.map(cue => {
    if (['killed', 'cancelled', 'expired'].includes(cue.status ?? '')) return cue;
    let result = cue;
    for (const decision of decisions) {
      if (decision.cueId !== cue.cue_id || decision.at > elapsed || result.status === 'killed') continue;
      // The slot limits new approvals. A producer can still stop an overlay
      // whose display began just before the slot closed.
      if (decision.status === 'approved' && decision.at > elapsedAt(cue.show_at.not_after, firstHalfSeconds)) continue;
      result = { ...result, status: decision.status, decided_by: 'producer',
        show_at: decision.status === 'approved'
          ? { ...cue.show_at, not_before: clockAt(Math.max(decision.at, elapsedAt(cue.show_at.not_before, firstHalfSeconds)), firstHalfSeconds) }
          : result.show_at };
    }
    return result;
  });
}

export function pitchPoint(point: Point, home: boolean): Point {
  return home ? point : { x: 105 - point.x, y: 68 - point.y };
}

export function teamStats(events: Event[], team: string) {
  const own = events.filter(e => e.team === team);
  const passes = own.filter(e => e.type === 'pass');
  return {
    passes: passes.length,
    accuracy: passes.length ? passes.filter(e => e.outcome === 'complete').length / passes.length : null,
    shots: own.filter(e => e.type === 'shot').length,
    pressures: own.filter(e => e.type === 'pressure').length,
  };
}

export const LEADER_STATS = ['sprint_distance', 'sprints', 'top_speed', 'passes', 'shots', 'pressures'] as const;
export interface Leader { stat: (typeof LEADER_STATS)[number]; player: string; team: string; value: number }

/** Who leads each player stat the feed carries, from the events delivered so far. The feed
 * has events and sprints but no tracking, so total distance run is not measured; sprint
 * distance is the nearest thing it records. Ties go to whoever reached the value first. */
export function leaders(events: Event[]): Leader[] {
  const totals = new Map<string, Map<string, { team: string; value: number }>>();
  const add = (stat: string, e: Event, value: number, best = false) => {
    if (!e.player_id || !Number.isFinite(value)) return;
    const table = totals.get(stat) ?? new Map();
    totals.set(stat, table);
    const row = table.get(e.player_id) ?? { team: e.team ?? '', value: 0 };
    row.value = best ? Math.max(row.value, value) : row.value + value;
    table.set(e.player_id, row);
  };
  for (const e of events) {
    const q = (e.qualifiers ?? {}) as Record<string, unknown>;
    if (e.type === 'sprint') {
      add('sprints', e, 1);
      add('sprint_distance', e, Number(q.distance_m ?? 0));
      add('top_speed', e, Number(q.speed_kmh ?? 0), true);
    }
    if (e.type === 'pass' && e.outcome === 'complete') add('passes', e, 1);
    if (e.type === 'shot') add('shots', e, 1);
    if (e.type === 'pressure') add('pressures', e, 1);
  }
  return LEADER_STATS.flatMap(stat => {
    let top: Leader | undefined;
    for (const [player, row] of totals.get(stat) ?? []) if (!top || row.value > top.value) top = { stat, player, team: row.team, value: row.value };
    return top ? [top] : [];
  });
}

export function activityAt(timeline: Timeline, elapsed: number, teams: string[]) {
  // Thirty-second buckets, current period only. No future events enter the chart.
  const period = clockAt(elapsed, timeline.firstHalfSeconds).period;
  const periodStart = period === 1 ? 0 : timeline.firstHalfSeconds;
  const end = periodStart + (Math.floor(Math.max(0, elapsed - periodStart) / 30) + 1) * 30;
  return Array.from({ length: 20 }, (_, i) => {
    const start = end - (20 - i) * 30;
    return { start, values: teams.map(team => start < periodStart ? 0 : timeline.events.filter(({ event, at }) =>
      at >= start && at < start + 30 && at <= elapsed && event.clock.period === period
      && event.team === team && ['pass', 'carry', 'dribble'].includes(event.type)).length) };
  });
}
