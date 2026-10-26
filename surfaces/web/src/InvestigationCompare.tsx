import { useState } from 'react';
import type { CaseFile } from './types/case-file';
import type { InsightCard } from './types/insight-card';
import { Investigation } from './Investigation';
import { useText } from './ui';

export function sameMoment(file: CaseFile, candidates: CaseFile[]): [CaseFile, CaseFile] | undefined {
  const matches = candidates.filter(candidate => candidate.case.case_id === file.case.case_id
    && candidate.case.match_id === file.case.match_id
    && JSON.stringify(candidate.case.window) === JSON.stringify(file.case.window)
    && JSON.stringify(candidate.case.detected_at) === JSON.stringify(file.case.detected_at));
  const a = matches.find(f => f.variant === 'A');
  const b = matches.find(f => f.variant === 'B');
  return a && b ? [a, b] : undefined;
}

/** The card is the shown take's own; only that take's column carries its Verifier verdict. */
export function Comparison({ pair, card, variant }: { pair: [CaseFile, CaseFile]; card?: InsightCard; variant?: CaseFile['variant'] }) {
  const { text } = useText();
  return <div className="investigation-comparison">
    {pair.map(file => <section className="comparison-take" key={file.variant}>
      <h2 className="comparison-label">{text(`compare.${file.variant}`)}</h2>
      <Investigation file={file} card={file.variant === variant ? card : undefined} />
    </section>)}
  </div>;
}

export function InvestigationCompare({ file, candidates, onScoreboard, card }: {
  file: CaseFile; candidates: CaseFile[]; onScoreboard: () => void; card?: InsightCard;
}) {
  const { text } = useText();
  const [compare, setCompare] = useState(false);
  const pair = sameMoment(file, candidates);
  return <>
    {pair && <div className="comparison-toolbar"><label><input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} />{text('compare.toggle')}</label>
      <p>{text('compare.recorded')}</p><a href="#/analyst" onClick={event => { event.preventDefault(); onScoreboard(); }}>{text('compare.scoreboard')} →</a>
    </div>}
    {compare && pair ? <Comparison pair={pair} card={card} variant={file.variant} /> : <Investigation file={file} card={card} />}
  </>;
}
