// The live API for typed questions (surfaces/api). The replay never depends on it: a question
// goes there only when no recording holds it, and every way it can say no has its own message.
import type { LiveJob } from './types/live-job';
import type { MatchClock } from './types/answer';

export const LIVE_API = ((import.meta.env.VITE_PROOFLINE_API as string | undefined) ?? '').replace(/\/$/, '');

export type LiveRefusal = 'unconfigured' | 'daily' | 'per_viewer' | 'running' | 'busy' | 'invalid' | 'unavailable';

export class LiveRefused extends Error {
  constructor(public readonly reason: LiveRefusal, public readonly retryAfterS?: number, public readonly detail?: string) {
    super(reason);
  }
}

type Fetch = typeof fetch;

async function call(path: string, init: RequestInit | undefined, api: string, fetcher: Fetch): Promise<LiveJob> {
  if (!api) throw new LiveRefused('unconfigured');
  let response: Response;
  try {
    response = await fetcher(`${api}${path}`, init);
  } catch {
    throw new LiveRefused('unavailable');
  }
  const body = await response.json().catch(() => ({}));
  if (response.ok) return body as LiveJob;
  const reason = (['daily', 'per_viewer', 'running', 'busy', 'invalid'] as const).find(r => r === body.error);
  throw new LiveRefused(reason ?? 'unavailable', body.retry_after_s, body.detail);
}

export function askLive(question: { match_id: string; asked_at: MatchClock; text: string; locale: string },
  { api = LIVE_API, fetcher = fetch }: { api?: string; fetcher?: Fetch } = {}): Promise<LiveJob> {
  return call('/api/questions', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(question),
  }, api, fetcher);
}

const MISSES = 4;  // failed polls in a row before the job is given up: a blip is ridden out

/** Polls a job until it is done or failed, reporting every new state. */
export async function followLive(job: LiveJob, onUpdate: (job: LiveJob) => void,
  { api = LIVE_API, fetcher = fetch, intervalMs = 1500, signal }: { api?: string; fetcher?: Fetch; intervalMs?: number; signal?: AbortSignal } = {},
): Promise<LiveJob> {
  let current = job;
  let misses = 0;
  while (current.status === 'queued' || current.status === 'running') {
    await new Promise(resolve => setTimeout(resolve, intervalMs));
    if (signal?.aborted) return current;
    try {
      current = await call(`/api/questions/${encodeURIComponent(current.job_id)}`, undefined, api, fetcher);
    } catch (error) {
      if (++misses > MISSES) throw error;
      continue;
    }
    misses = 0;
    onUpdate(current);
  }
  return current;
}

/** The viewer's one live question, kept outside any panel: changing route or tab must not lose
 * it while the API still counts it as theirs. */
export interface LiveState { job?: LiveJob; startedAt?: number }
let shared: LiveState = {};
const listeners = new Set<() => void>();
export const liveState = {
  get: (): LiveState => shared,
  set(next: LiveState) { shared = next; listeners.forEach(listener => listener()); },
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
};
