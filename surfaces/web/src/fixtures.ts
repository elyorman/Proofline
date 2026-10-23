// The committed ledger is validated against the Python contracts in test_web_replay.py.
// Its stand_ins index identifies authored placeholders without altering real card payloads.
import ledger from './fixtures/ledger.json';
import type { InsightCard } from './types/insight-card';
import type { Cue } from './types/cue';

export const cards = ledger.cards as unknown as InsightCard[];
export const cues = ledger.cues as unknown as Cue[];
export const isStandInCard = (card: Pick<InsightCard, 'id' | 'revision'>) =>
  ledger.stand_ins.cards.includes(`${card.id}@${card.revision ?? 1}`);
export const isStandInCue = (cue: Pick<Cue, 'cue_id'>) => ledger.stand_ins.cues.includes(cue.cue_id);
