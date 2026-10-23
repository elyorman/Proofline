import type { Cue } from './types/cue';
import type { InsightCard } from './types/insight-card';
import type { ReplayData } from './data';
import { isStandInCue } from './fixtures';
import { applyDecisions, elapsedAt, visibleCards, visibleCues, type ProducerDecision } from './replay';
import { Pitch } from './Pitch';
import { useText } from './ui';

export function overlayTemplate(template: string) {
  switch (template) {
    case 'pressure_shift_bar': return 'pressure';
    case 'update_banner': return 'update';
    case 'withdrawal_banner': return 'withdrawal';
    default: return 'unknown';
  }
}

export function publishedCues(cues: Cue[], cards: InsightCard[], elapsed: number, firstHalf: number) {
  const published = visibleCards(cards, elapsed, firstHalf);
  return cues.filter(cue => !cue.insight_id && cue.kind === 'key_event'
    ? elapsedAt(cue.show_at.not_before, firstHalf) <= elapsed
    : published.some(card => card.id === cue.insight_id && (card.revision ?? 1) === cue.insight_revision));
}

export function CueGraphic({ cue }: { cue: Cue }) {
  const { text, metric } = useText();
  const template = overlayTemplate(cue.template);
  const field = (key: string) => String(cue.fields?.[key] ?? '');
  const name = field('metric') || 'pressure_rate';
  const label = field('stat_label');
  const labelText = label === name ? text(`metric.${name}`) : label;
  const before = cue.fields?.before;
  const after = cue.fields?.after;
  const scale = Math.max(1, typeof before === 'number' ? Math.abs(before) : 0, typeof after === 'number' ? Math.abs(after) : 0);
  const width = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
    ? `${Math.max(0, value) / scale * 100}%` : '0%';
  return <article className={`cue-graphic cue-${template}`} data-template={cue.template}>
    <span className="overlay-brand">{text('brand.name')}{isStandInCue(cue) && <span> / {text('fixture.short')}</span>}</span>
    {template === 'unknown' ? <p>{text('overlay.unsupported', { template: cue.template })}</p> : <>
      <h2>{field('headline') || text('value.unset')}</h2><p>{field('team')}</p>
      {template === 'pressure' ? <div className="pressure-comparison">
        <p>{labelText}</p>
        {[{ key: 'before', value: before }, { key: 'after', value: after }].map(item => <div className="pressure-row" key={item.key}>
          <span>{text(`overlay.${item.key}`)}</span>
          <div className="pressure-track"><i style={{ width: width(item.value) }} /></div>
          <strong>{metric(name, item.value)}</strong>
        </div>)}
      </div> : <div className="banner-fields">
        {['stat_label', 'body', 'text', 'message', 'reason'].filter(key => field(key)).map(key => <p key={key}>{field(key)}</p>)}
      </div>}
    </>}
  </article>;
}

export function ProgramOverlay({ cues }: { cues: Cue[] }) {
  const { text } = useText();
  return <div className={`broadcast-overlay ${cues.length ? 'on-air' : ''}`} aria-live="polite">
    {cues.length ? cues.map(cue => <CueGraphic cue={cue} key={cue.cue_id} />)
      : <span className="off-air-label">{text('broadcast.offAir')}</span>}
  </div>;
}

export function Overlay({ data, elapsed, cards, cues, decisions }: {
  data: ReplayData; elapsed: number; cards: InsightCard[]; cues: Cue[]; decisions: ProducerDecision[];
}) {
  const firstHalf = data.timeline.firstHalfSeconds;
  const effective = applyDecisions(publishedCues(cues, cards, elapsed, firstHalf), decisions, elapsed, firstHalf);
  const active = visibleCues(effective, elapsed, firstHalf, data.timeline.events);
  return <div className="overlay-view"><div className="program-monitor">
    <Pitch data={data} elapsed={elapsed} /><ProgramOverlay cues={active} />
  </div></div>;
}
