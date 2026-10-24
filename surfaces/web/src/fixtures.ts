// The committed ledger is validated against the Python contracts in test_web_replay.py.
// Its stand_ins index identifies authored placeholders without altering real card payloads.
import ledger from './fixtures/ledger.json';
import type { InsightCard } from './types/insight-card';
import type { Cue } from './types/cue';
import type { CaseFile } from './types/case-file';
import type { EventAmendment } from './types/event-amendment';
import type { Answer } from './types/answer';
import type { Profile } from './types/profile';

export interface CorrectionRecord { card_id: string; decision: 'withdraw' | 'revise'; revision: number; amendment_id: string }

export const cards = ledger.cards as unknown as InsightCard[];
export const cues = ledger.cues as unknown as Cue[];
export const answers = ledger.answers as unknown as Answer[];
export const comparisonFiles = ledger.comparison_case_files as unknown as CaseFile[];
export const caseFiles = ledger.case_files as unknown as CaseFile[];
export const amendments = ledger.amendments as unknown as EventAmendment[];
export const corrections = ledger.corrections as CorrectionRecord[];
export const profile = ledger.profile as Profile;
export const isStandInCard = (card: Pick<InsightCard, 'id' | 'revision'>) =>
  (ledger.stand_ins.cards as string[]).includes(`${card.id}@${card.revision ?? 1}`);
export const isStandInCue = (cue: Pick<Cue, 'cue_id'>) => (ledger.stand_ins.cues as string[]).includes(cue.cue_id);
