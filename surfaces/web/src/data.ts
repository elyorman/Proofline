import type { Event, EventType } from './types/event';
import { buildTimeline, type Timeline } from './replay';

export interface Player { id: string; name: string; role: string }
export interface Team { name: string; code: string; players: Player[] }
export interface ReplayData { matchId: string; teams: [Team, Team]; timeline: Timeline }

const eventTypes: EventType[] = [
  'pass', 'carry', 'dribble', 'shot', 'tackle', 'interception', 'clearance', 'pressure', 'duel',
  'foul', 'card', 'substitution', 'possession_change', 'set_piece', 'goal', 'sprint', 'period_start', 'period_end',
];
const outcomes = new Set(['complete', 'incomplete', 'won', 'lost', 'on_target', 'off_target', 'blocked', 'goal', 'na']);

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function parseReplay(manifest: unknown, jsonl: string): ReplayData {
  if (!object(manifest) || typeof manifest.match_id !== 'string' || !object(manifest.teams)
    || !object(manifest.teams.home) || !object(manifest.teams.away)) throw new Error('Invalid replay manifest');
  const teams = [manifest.teams.home, manifest.teams.away].map((team: unknown): Team => {
    if (!object(team) || typeof team.name !== 'string' || typeof team.code !== 'string'
      || !Array.isArray(team.players)) throw new Error('Invalid team');
    const players = team.players.map((player: unknown): Player => {
      if (!object(player) || typeof player.player_id !== 'string' || typeof player.name !== 'string'
        || typeof player.role !== 'string') throw new Error('Invalid player');
      return { id: player.player_id, name: player.name, role: player.role };
    });
    return { name: team.name, code: team.code, players };
  }) as [Team, Team];
  if (teams[0].name === teams[1].name) throw new Error('Duplicate team');
  const events: Event[] = jsonl.trim().split('\n').filter(Boolean).map(line => {
    const event: unknown = JSON.parse(line);
    if (!object(event) || event.match_id !== manifest.match_id || typeof event.event_id !== 'string'
      || typeof event.type !== 'string' || !eventTypes.includes(event.type as EventType)
      || typeof event.team !== 'string' || !object(event.clock)) {
      throw new Error('Invalid replay event');
    }
    const { period, minute, second } = event.clock;
    if ((period !== 1 && period !== 2) || !Number.isInteger(minute) || !Number.isInteger(second)
      || (minute as number) < (period === 2 ? 45 : 0) || (minute as number) > (period === 1 ? 60 : 130)
      || (second as number) < 0 || (second as number) > 59) throw new Error('Invalid event clock');
    if (event.outcome !== undefined && (typeof event.outcome !== 'string' || !outcomes.has(event.outcome))) {
      throw new Error('Invalid event outcome');
    }
    for (const point of [event.start, event.end]) {
      if (point === undefined || point === null) continue;
      if (!object(point) || typeof point.x !== 'number' || typeof point.y !== 'number'
        || !Number.isFinite(point.x) || !Number.isFinite(point.y) || point.x < 0 || point.x > 105
        || point.y < 0 || point.y > 68) throw new Error('Invalid event position');
    }
    // The exporter validates full Event contracts. This guards corrupt fixture files at load time.
    return event as unknown as Event;
  });
  return { matchId: manifest.match_id, teams, timeline: buildTimeline(events) };
}

export async function loadReplay(signal: AbortSignal): Promise<ReplayData> {
  const base = `${import.meta.env.BASE_URL}fixtures/m01/`;
  const [manifest, events] = await Promise.all([
    fetch(`${base}meta.json`, { signal }), fetch(`${base}events.jsonl`, { signal }),
  ]);
  if (!manifest.ok || !events.ok) throw new Error('Replay fixtures missing');
  return parseReplay(await manifest.json(), await events.text());
}
