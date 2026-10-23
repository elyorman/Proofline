import { useState } from 'react';
import type { InsightCard } from './types/insight-card';
import { Evidence, useCardText } from './Insights';
import { formatClock } from './replay';
import { Empty, Icon, SectionTitle, useText } from './ui';

const checks = ['recompute', 'baseline_check', 'sample_size_check', 'contradiction_check', 'number_check', 'semantic_check'] as const;

export function Analyst({ cards, allRevisions, selected, onSelect }: {
  cards: InsightCard[]; allRevisions: InsightCard[]; selected: string; onSelect: (id: string) => void;
}) {
  const { text } = useText();
  const cardText = useCardText();
  const [tab, setTab] = useState('overview');
  const card = cards.find(c => c.id === selected) ?? cards[0];
  const tabs = ['overview', 'verification', 'history', 'evaluation'];
  return <div className="analyst-layout"><aside className="panel case-list"><SectionTitle title={text('case.list')} />
    {cards.length ? cards.map(c => <button key={c.id} className={`case-row ${c.id === card?.id ? 'selected' : ''}`} onClick={() => onSelect(c.id)} aria-pressed={c.id === card?.id}>
      <span className="case-time">{formatClock(c.timing.published_at!)}</span><strong>{c.subject.team}</strong><span>{cardText(c)}</span><small className={`status ${c.status === 'withdrawn' ? 'warn' : ''}`}>{text(`status.${c.status}`)}</small>
    </button>) : <p className="muted padded">{text('case.empty')}</p>}
    <div className="live-box"><button disabled className="button"><Icon name="play" size={14} />{text('live')}</button><p>{text('live.unavailable')}</p></div>
  </aside><section className="panel case-content">
    <div className="tabs" role="tablist" aria-label={text('case.overview')}>{tabs.map(name => <button id={`tab-${name}`} aria-controls={`panel-${name}`} role="tab" aria-selected={tab === name} tabIndex={tab === name ? 0 : -1} key={name} onClick={() => setTab(name)} onKeyDown={event => {
      if (['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (tabs.indexOf(name) + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        setTab(tabs[index]); document.getElementById(`tab-${tabs[index]}`)?.focus();
      }
    }}>{text(`case.${name}`)}</button>)}</div>
    <div className="case-body" id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} tabIndex={0}>
      {tab === 'evaluation' ? <Empty title={text('case.evaluation.empty')} body={text('case.evaluation.text')} /> : !card ? <Empty title={text('case.empty')} /> : <>
        <div className="case-heading"><span className="eyebrow">{text('fixture.short')} · {text('insights.revision', { number: card.revision ?? 1 })}</span><h2>{cardText(card)}</h2><code>{card.case_id}</code></div>
        {tab === 'overview' && <>
          <SectionTitle title={text('case.agents')} />
          {card.investigation ? <div className="agent-grid">{card.investigation.agents.map((agent, i) => <div key={agent}><span className="agent-number">0{i + 1}</span><strong>{text(`case.role.${agent}`)}</strong><small>{text('fixture.short')}</small></div>)}</div> : <p className="muted">{text('case.noInvestigation')}</p>}
          <SectionTitle title={text('case.tools')} sub={text('case.tools.sub')} />
          <Evidence card={card} />
          {card.evidence?.map(e => <div className="reference-row" key={e.tool_call_id}><code>{e.tool_call_id}</code><span>{e.subject} · {e.metric}</span></div>)}
          <div className="trace-box"><span>{text('case.trace')}</span><code>{card.provenance.trace_id}</code><small>{text('case.trace.note')}</small></div>
        </>}
        {tab === 'verification' && <><p className="notice-inline"><Icon name="info" size={18} />{text('case.verifier.note')}</p>
          {card.verification ? <ul className="check-list">{checks.map(check => <li key={check}><span>{text(`check.${check}`)}</span><span className={`status ${['failed', 'mismatch'].includes(card.verification![check]) ? 'warn' : ''}`}>{text(`status.${card.verification![check]}`)}</span></li>)}</ul> : <p className="muted">{text('case.verifier.none')}</p>}
        </>}
        {tab === 'history' && <div className="revision-list">{allRevisions.filter(c => c.id === card.id && (c.revision ?? 1) <= (card.revision ?? 1)).map(c => <article key={c.revision}>
          <span className="revision-dot" /><span className="eyebrow">{text('insights.revision', { number: c.revision ?? 1 })} · {formatClock(c.timing.published_at!)}</span>
          <h3>{text(c.status === 'withdrawn' ? 'insights.correction' : 'insights.original')}</h3><p>{cardText(c)}</p>
          <small className="status">{text(`status.${c.status}`)}</small>
        </article>)}</div>}
      </>}
    </div>
  </section></div>;
}
