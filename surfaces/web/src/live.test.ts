import { describe, expect, it } from 'vitest';
import { askLive, followLive, LiveRefused } from './live';
import type { LiveJob } from './types/live-job';

const question = { question_id: 'live-1', match_id: 'm01', asked_at: { period: 2 as const, minute: 68, second: 0 }, text: 'Why now?', locale: 'en' as const };
const job = (status: LiveJob['status'], stages: LiveJob['stages'] = []): LiveJob => ({ job_id: 'live-1', question, status, stages, created_ms: 0 });
const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

describe('the live API client', () => {
  it('asks once and follows the job until it ends, reporting each new stage', async () => {
    const sent: RequestInit[] = [];
    const queue = [reply(200, job('running', [{ stage: 'framed', at_ms: 1 }])), reply(200, { ...job('failed'), error: 'Timeout' })];
    const fetcher = (async (_: string, init?: RequestInit) => { if (init) sent.push(init); return queue.shift()!; }) as typeof fetch;
    const started = await askLive({ match_id: 'm01', asked_at: question.asked_at, text: 'Why now?', locale: 'en' },
      { api: 'https://api.example', fetcher: (async (url: string, init?: RequestInit) => { sent.push(init!); expect(url).toBe('https://api.example/api/questions'); return reply(202, job('queued')); }) as typeof fetch });
    expect(started.status).toBe('queued');
    expect(JSON.parse(String(sent[0].body)).text).toBe('Why now?');
    const seen: string[] = [];
    const ended = await followLive(started, j => seen.push(j.status), { api: 'https://api.example', fetcher, intervalMs: 0 });
    expect(seen).toEqual(['running', 'failed']);
    expect(ended.error).toBe('Timeout');
  });

  it('turns every refusal into its own reason, and needs an API to ask at all', async () => {
    const refuse = (status: number, body: unknown) => askLive({ match_id: 'm01', asked_at: question.asked_at, text: 'Why?', locale: 'es' },
      { api: 'https://api.example', fetcher: (async () => reply(status, body)) as typeof fetch });
    await expect(refuse(429, { error: 'per_viewer', retry_after_s: 42 })).rejects.toMatchObject({ reason: 'per_viewer', retryAfterS: 42 });
    await expect(refuse(429, { error: 'daily' })).rejects.toMatchObject({ reason: 'daily' });
    await expect(refuse(429, { error: 'running' })).rejects.toMatchObject({ reason: 'running' });
    await expect(refuse(503, { error: 'busy' })).rejects.toMatchObject({ reason: 'busy' });
    await expect(refuse(500, {})).rejects.toMatchObject({ reason: 'unavailable' });
    const offline = askLive({ match_id: 'm01', asked_at: question.asked_at, text: 'Why?', locale: 'en' },
      { api: 'https://api.example', fetcher: (async () => { throw new TypeError('network'); }) as typeof fetch });
    await expect(offline).rejects.toMatchObject({ reason: 'unavailable' });
    await expect(askLive({ match_id: 'm01', asked_at: question.asked_at, text: 'Why?', locale: 'en' }, { api: '' }))
      .rejects.toBeInstanceOf(LiveRefused);
  });
});
