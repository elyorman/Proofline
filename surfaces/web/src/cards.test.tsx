import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import type { Metric } from './types/insight-card';
import { cards } from './fixtures';
import { CaseOverview, RevisionHistory, VerificationPanel } from './Analyst';
import { Evidence, Insight } from './Insights';
import { RevisionDiff } from './RevisionDiff';
import { amendments } from './fixtures';
import { ShotMarker } from './Pitch';
import { LocaleContext } from './ui';
import { metricNumber, t, type Locale } from './i18n';

const press = cards.find(card => card.id === 'ins-m01-063-pressure_shift')!;
const render = (node: ReactNode, locale: Locale = 'en') =>
  renderToStaticMarkup(<LocaleContext.Provider value={locale}>{node}</LocaleContext.Provider>);

describe('faithful card rendering', () => {
  it('shows the actual Spanish variant, recorded support and recorded rejection reasons', () => {
    const html = render(<Insight card={press} onOpen={() => {}} />, 'es');
    expect(html).toContain(press.variants!.casual.es);
    expect(html).toContain(t('es', `support.${press.verification!.support_level}`));
    const evidence = press.evidence!.find(e => e.metric === 'pressure_rate')!;
    expect(html).toContain(metricNumber('es', evidence.metric, evidence.value));
    for (const alternative of press.rejected_alternatives!) {
      expect(html).toContain(render(<p>{alternative.reason}</p>));
      expect(html).toContain(alternative.taxonomy);
    }
    expect(html).not.toContain('Fatigue is the sample alternative');
    expect(html).not.toContain('Moderate support');
  });
  it('follows each evidence baseline and renders duplicate tool-call references safely', () => {
    const evidence = press.evidence![0];
    const updated = { ...press, evidence: [
      { ...evidence, baseline: { ...evidence.baseline, window: 'match_so_far' as const } },
      { ...evidence, metric: 'sprint_speed' as const, value: 31.25 },
    ] };
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const html = render(<Evidence card={updated} />);
      expect(html).toContain('Match so far');
      expect(html).toContain('31.2 km/h');
      expect(html.split(evidence.tool_call_id)).toHaveLength(3);
      expect(error).not.toHaveBeenCalled();
    } finally { error.mockRestore(); }
  });
  it('shows changes, attribution roles/agents and the whole investigation summary', () => {
    const html = render(<CaseOverview card={press} />);
    for (const proposition of press.propositions) {
      expect(html).toContain(proposition.id);
      if ('cause' in proposition) {
        expect(html).toContain(proposition.cause);
        expect(html).toContain(proposition.hypothesis_id);
      }
    }
    expect(html).toContain('Primary');
    expect(html).toContain('Secondary');
    expect(html).toContain('Tactics');
    expect(html).toContain('Game state');
    expect(html).toContain('Physical');
    expect(html).toContain(`${press.investigation!.tool_calls} / ${press.investigation!.budget}`);
    expect(html).toContain(press.investigation!.cross_examination!.replaceAll("'", '&#x27;'));
    expect(html).toContain(press.provenance.trace_id);
    expect(render(<CaseOverview card={{ ...press, investigation: { ...press.investigation!, recovered_from_checkpoint: true } }} />)).toContain('Yes');
  });
  it('shows every verification check, support and language level', () => {
    const html = render(<VerificationPanel card={press} />);
    expect(html.match(/<li>/g)).toHaveLength(6);
    expect(html).toContain(t('en', `support.${press.verification!.support_level}`));
    expect(html).toContain(t('en', `language.${press.verification!.language_level}`));
    expect(html).toContain(press.verification!.verifier_model_family);
    expect(html).not.toContain('have not been executed');
  });
  it('renders each recorded revision reason instead of a fixed correction sentence', () => {
    const withdrawn = cards.find(card => card.status === 'withdrawn')!;
    const reason = 'Provider re-attributed a block of events';
    const updated = { ...withdrawn, revisions: withdrawn.revisions!.map(r => ({ ...r, reason })) };
    const html = render(<RevisionHistory card={updated} snapshots={cards} />);
    expect(html).toContain(reason);
    expect(html).toContain('Revision 1');
    expect(html).toContain('Revision 2');
  });
  it('keeps the view readable when a metric id is unknown', () => {
    const updated = { ...press, evidence: [{ ...press.evidence![0], metric: 'new_metric' as Metric }] };
    expect(render(<Evidence card={updated} />)).toContain('new_metric');
  });
});

describe('shot outcomes', () => {
  it('draws distinguishable markers for goal, on-target, off-target and blocked shots', () => {
    const markers = ['goal', 'on_target', 'off_target', 'blocked'].map(outcome => render(<svg><ShotMarker outcome={outcome} /></svg>));
    expect(new Set(markers).size).toBe(4);
    expect(markers[0]).toContain('shot-centre');
    expect(markers[1]).toContain('On target');
    expect(markers[2]).toContain('Off target');
    expect(markers[3]).toContain('<rect');
  });
});

describe('Studio correction gate', () => {
  it('shows the actual evidence change, amendment and affected events', () => {
    const card = cards.find(c => c.status === 'withdrawn')!;
    const html = render(<RevisionDiff card={card} snapshots={cards} amendments={amendments} />);
    expect(html).toContain(amendments[0].amendment_id);
    expect(html).toContain(amendments[0].event_ids[0]);
    expect(html).toContain(amendments[0].reason);
    expect(html).toContain('Withdrawn');
    expect(html).toContain('Published');
  });
});
