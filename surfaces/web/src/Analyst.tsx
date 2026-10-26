import { useState, type ReactNode } from 'react';
import type { InsightCard } from './types/insight-card';
import { Evidence, useCardText } from './Insights';
import { displayTime, formatClock } from './replay';
import { comparisonFiles, isStandInCard } from './fixtures';
import { Empty, Icon, SectionTitle, TabList, useText } from './ui';
import { InvestigationCompare } from './InvestigationCompare';
import type { CaseFile } from './types/case-file';
import { RevisionDiff } from './RevisionDiff';
import { Scoreboard } from './Scoreboard';
import type { EventAmendment } from './types/event-amendment';

const checks = ['recompute', 'baseline_check', 'sample_size_check', 'contradiction_check', 'number_check', 'semantic_check'] as const;

function Fact({ label, children }: { label: string; children?: ReactNode }) {
  const { text } = useText();
  return <div><dt>{text(label)}</dt><dd>{children ?? text('value.unset')}</dd></div>;
}

export function RevisionHistory({ card, snapshots }: { card: InsightCard; snapshots: InsightCard[] }) {
  const { text } = useText();
  const cardText = useCardText();
  const original = snapshots.find(c => c.id === card.id && (c.revision ?? 1) === 1)
    ?? ((card.revision ?? 1) === 1 ? card : undefined);
  const originalAt = original && displayTime(original);
  return <div className="revision-list">
    {original && originalAt && <article><span className="revision-dot" />
      <span className="eyebrow">{text('insights.revision', { number: 1 })} · {formatClock(originalAt)}</span>
      <p>{cardText(original)}</p><small className="status">{text(`status.${original.status}`)}</small>
    </article>}
    {card.revisions?.map(revision => {
      const snapshot = snapshots.find(c => c.id === card.id && c.revision === revision.revision);
      return <article key={revision.revision}><span className="revision-dot" />
        <span className="eyebrow">{text('insights.revision', { number: revision.revision })} · {formatClock(revision.at)}</span>
        <h3>{revision.reason}</h3>
        {snapshot && <p>{cardText(snapshot)}</p>}
        {revision.amendment_ids?.map(id => <code key={id}>{id}</code>)}
      </article>;
    })}
    {!card.revisions?.length && <p className="muted">{text('history.none')}</p>}
  </div>;
}

export function CaseOverview({ card }: { card: InsightCard }) {
  const { text, num } = useText();
  const investigation = card.investigation;
  return <>
    <SectionTitle title={text('case.propositions')} />
    <div className="proposition-list">{card.propositions.map(p => <article key={p.id}>
      <span className="eyebrow">{p.id} · {text(p.type === 'change' ? 'case.change' : 'case.attribution')}</span>
      <dl className="card-facts">
        {'metric' in p ? <>
          <Fact label="case.metric">{text(`metric.${p.metric}`)}</Fact>
          <Fact label="case.subject">{p.subject}</Fact>
          <Fact label="case.direction">{text(`direction.${p.direction}`)}</Fact>
          <Fact label="case.window">{formatClock(p.window.start)}–{formatClock(p.window.end)}</Fact>
          <Fact label="case.baseline">{text(`baseline.${p.baseline}`)}</Fact>
        </> : <>
          <Fact label="case.cause"><code>{p.cause}</code></Fact>
          <Fact label="case.effect">{p.effect}</Fact>
          <Fact label="case.role">{text(`role.${p.role}`)}</Fact>
          <Fact label="case.agent">{text(`case.role.${p.agent}`)}</Fact>
          <Fact label="case.hypothesis"><code>{p.hypothesis_id}</code></Fact>
        </>}
      </dl>
    </article>)}</div>
    <SectionTitle title={text('case.investigation')} />
    {investigation ? <>
      <div className="agent-grid">{investigation.agents.map((agent, index) => <div key={`${agent}-${index}`}>
        <span className="agent-number">{String(index + 1).padStart(2, '0')}</span>
        <strong>{text(`case.role.${agent}`)}</strong>
      </div>)}</div>
      <dl className="card-facts investigation-facts">
        <Fact label="case.predictions">{num(investigation.preregistered_predictions)}</Fact>
        <Fact label="case.budget">{num(investigation.tool_calls)} / {num(investigation.budget)}</Fact>
        <Fact label="case.crossExam">{investigation.cross_examination || text('value.unset')}</Fact>
        <Fact label="case.recovered">{text(investigation.recovered_from_checkpoint ? 'value.yes' : 'value.no')}</Fact>
      </dl>
    </> : <p className="muted">{text('case.noInvestigation')}</p>}
    <SectionTitle title={text('case.tools')} sub={text('case.tools.sub')} />
    <Evidence card={card} />
    <SectionTitle title={text('case.dependencies')} />
    <dl className="card-facts">
      <Fact label="case.dataVersion"><code>{card.depends_on.data_version}</code></Fact>
      <Fact label="case.evidenceSets">{card.depends_on.evidence_sets.map((id, index) => <code key={`${id}-${index}`}>{id}</code>)}</Fact>
    </dl>
    <div className="trace-box"><span>{text('case.trace')}</span><code>{card.provenance.trace_id}</code><small>{text('case.trace.note')}</small>
      {card.provenance.foundry_eval_run && <><span>{text('case.evalReference')}</span><code>{card.provenance.foundry_eval_run}</code></>}
    </div>
  </>;
}

export function VerificationPanel({ card }: { card: InsightCard }) {
  const { text } = useText();
  const verification = card.verification;
  if (!verification) return <p className="muted">{text('case.verifier.none')}</p>;
  return <>
    {isStandInCard(card) && <p className="notice-inline"><Icon name="info" size={18} />{text('fixture.detail')}</p>}
    <dl className="card-facts">
      <Fact label="case.verdict">{text(`status.${verification.status}`)}</Fact>
      <Fact label="case.support">{verification.support_level ? text(`support.${verification.support_level}`) : undefined}</Fact>
      <Fact label="case.language">{verification.language_level ? text(`language.${verification.language_level}`) : undefined}</Fact>
      <Fact label="case.verifier">{verification.verifier_model_family}</Fact>
      {verification.rejection_reason && <Fact label="case.rejection">{verification.rejection_reason}</Fact>}
    </dl>
    <ul className="check-list">{checks.map(check => <li key={check}>
      <span>{text(`check.${check}`)}</span>
      <span className={`status ${['failed', 'mismatch'].includes(verification[check]) ? 'warn' : ''}`}>{text(`status.${verification[check]}`)}</span>
    </li>)}</ul>
  </>;
}

export const CASE_TABS = ['investigation', 'overview', 'verification', 'history', 'evaluation', 'ask'] as const;
export type CaseTab = (typeof CASE_TABS)[number];

export function Analyst({ cards, allRevisions, selected, onSelect, amendments = [], files = [], tab: shown, onTab, ask }: {
  cards: InsightCard[]; allRevisions: InsightCard[]; selected: string; onSelect: (id: string) => void; amendments?: EventAmendment[]; files?: CaseFile[];
  tab?: CaseTab; onTab?: (tab: CaseTab) => void; ask?: ReactNode;
}) {
  const { text } = useText();
  const cardText = useCardText();
  const [own, setOwn] = useState<CaseTab>('investigation');
  const tab = shown ?? own;
  const setTab = onTab ?? setOwn;
  const file = files.find(f => f.case.case_id === selected || f.case.card_id === selected)
    ?? (!cards.some(c => c.id === selected) ? files.at(-1) : undefined);
  const card = file ? allRevisions.filter(c => c.case_id === file.case.case_id).at(-1)
    : cards.find(c => c.id === selected) ?? (!files.length ? cards[0] : undefined);
  const tabs = CASE_TABS.filter(name => name !== 'ask' || ask).map(name => name === 'ask'
    ? { id: name, className: 'tab-ask', label: <><Icon name="ask" size={14} />{text('ask.title')}</> }
    : { id: name, label: text(`case.${name}`) });
  return <div className="analyst-layout"><aside className="panel case-list"><SectionTitle title={text('case.list')} />
    <div className="case-rows">
      {files.slice().reverse().map(f => <button className={`case-row ${f === file ? 'selected' : ''}`} key={`${f.case.case_id}-${f.variant}`} onClick={() => onSelect(f.case.case_id)} aria-pressed={f === file}><span className="case-time">{formatClock(f.case.window.end)}</span><strong>{f.case.triggers[0].subject}</strong><span>{f.case.case_id}</span><small className="status">{text(`outcome.${f.ranking.outcome}`)}</small></button>)}
      {cards.length ? cards.filter(c => displayTime(c) && !files.some(f => f.case.case_id === c.case_id)).map(c => <button key={c.id} className={`case-row ${c.id === card?.id ? 'selected' : ''}`} onClick={() => onSelect(c.id)} aria-pressed={c.id === card?.id}>
        <span className="case-time">{formatClock(displayTime(c)!)}</span><strong>{c.subject.team}</strong><span>{cardText(c)}</span><small className={`status ${c.status === 'withdrawn' ? 'warn' : ''}`}>{text(`status.${c.status}`)}</small>
      </button>) : <p className="muted padded">{text('case.empty')}</p>}
    </div>
    <div className="live-box">{ask
      ? <button className="button primary" onClick={() => setTab('ask')}><Icon name="ask" size={14} />{text('ask.title')}</button>
      : <button disabled className="button"><Icon name="play" size={14} />{text('live')}</button>}<p>{text('live.unavailable')}</p></div>
  </aside><section className="panel case-content">
    <TabList tabs={tabs} selected={tab} onSelect={id => setTab(id as CaseTab)} label={text('case.overview')} />
    {tab !== 'ask' && <div className="case-body" key={tab} id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} tabIndex={0}>
      {tab === 'evaluation' ? <Scoreboard /> : tab === 'investigation' ? (file ? <InvestigationCompare key={file.case.case_id} file={file} card={card} candidates={comparisonFiles} onScoreboard={() => setTab('evaluation')} />
        : card ? <Empty title={text('inv.noFile')} /> : <Empty title={text('case.empty')} body={text('insights.empty.sub')} />) : !card ? <Empty title={text('case.empty')} /> : <>
        <div className="case-heading"><span className="eyebrow">{text(isStandInCard(card) ? 'fixture.short' : 'record.backend')} · {text('insights.revision', { number: card.revision ?? 1 })}</span>
          <h2>{cardText(card, 'analyst') ?? text('insights.noVariant')}</h2><code>{card.case_id}</code>
          <p className="case-outcome">{text('case.outcome')}: {text(`outcome.${card.case_outcome}`)}</p>
        </div>
        {tab === 'overview' && <CaseOverview card={card} />}
        {tab === 'verification' && <VerificationPanel card={card} />}
        {tab === 'history' && <><RevisionDiff card={card} snapshots={allRevisions} amendments={amendments} /><RevisionHistory card={card} snapshots={allRevisions} /></>}
      </>}
    </div>}
    {/* Ask stays mounted behind the other tabs, so a live question keeps running. */}
    {ask && <div className="case-body ask-body" id="panel-ask" role="tabpanel" aria-labelledby="tab-ask" tabIndex={0} hidden={tab !== 'ask'}>{ask}</div>}
  </section></div>;
}
