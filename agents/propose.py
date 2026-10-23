"""Turn a finding into a proposed Insight Card (spec §5): the primary cause's change and
attribution, any secondary attributions, the evidence each rests on, and the rejected
alternatives. The card goes to the Verifier; nothing here decides whether it is shown.
"""

import uuid

from agents import narrator
from agents.investigation import Tested, cause_team
from agents.single import Finding
from contracts.card import (
    AttributionProposition,
    Baseline,
    ChangeProposition,
    DependsOn,
    Evidence,
    InsightCard,
    Investigation,
    Provenance,
    RejectedAlternative,
    Subject,
    Timing,
)
from contracts.taxonomy import CardStatus, CaseOutcome
from state.subjects import resolve
from state.tools import Feed


def _evidence(t: Tested) -> Evidence:
    p = t.hypothesis.prediction
    return Evidence(
        metric=p.metric,
        subject=p.subject,
        window=p.window,
        value=t.during.value,
        baseline=Baseline(window=p.compare_to, value=t.before.baseline.value),
        n_events=t.during.n_events,
        tool_call_id=t.during.tool_call_id,
    )


def _attribution(t: Tested, pid: str, role: str) -> AttributionProposition:
    return AttributionProposition(
        id=pid,
        cause=t.hypothesis.taxonomy,
        effect="p1",
        role=role,
        hypothesis_id=t.hypothesis.hypothesis_id,
        agent=t.hypothesis.agent,
    )


def propose(finding: Finding, feed: Feed) -> InsightCard | None:
    """The card a finding supports, or None when the case closes without one."""
    ranking, case = finding.ranking, finding.case
    if ranking.outcome != CaseOutcome.EXPLAINED:
        return None
    primary = finding.tested_by_id(ranking.primary)
    secondary = [finding.tested_by_id(s) for s in ranking.secondary]
    p = primary.hypothesis.prediction
    change = ChangeProposition(
        id="p1",
        metric=p.metric,
        subject=p.subject,
        direction=p.direction,
        window=p.window,
        baseline=p.compare_to,
    )
    propositions = [change, _attribution(primary, "p2", "primary")]
    propositions += [_attribution(t, f"p{i}", "secondary") for i, t in enumerate(secondary, 3)]
    backing = [primary, *secondary]
    measured = list({t.test.tool_call_id: t for t in backing}.values())  # one line per call
    refuted = {e.hypothesis_id: e for e in finding.exams if e.result == "refuted"}
    rejected = [
        RejectedAlternative(
            hypothesis_id=t.hypothesis.hypothesis_id,
            taxonomy=t.hypothesis.taxonomy,
            agent=t.hypothesis.agent,
            team=cause_team(feed.meta, t.hypothesis),
            reason=refuted[t.hypothesis.hypothesis_id].reason
            if t.hypothesis.hypothesis_id in refuted
            else t.test.reason,
            rejected_by="cross_examination" if t.hypothesis.hypothesis_id in refuted else "test",
            tool_call_id=refuted[t.hypothesis.hypothesis_id].tool_call_id
            if t.hypothesis.hypothesis_id in refuted
            else t.test.tool_call_id,
        )
        for t in finding.tested
        if t not in backing and (not t.supported or t.hypothesis.hypothesis_id in refuted)
    ]
    who = resolve(feed.meta, p.subject)
    team = cause_team(feed.meta, primary.hypothesis)
    card = InsightCard(
        id=f"ins-{case.case_id.removeprefix('case-')}",
        match_id=case.match_id,
        case_id=case.case_id,
        case_outcome=CaseOutcome.EXPLAINED,
        moment_type=case.moment_type,
        status=CardStatus.PROPOSED,
        subject=Subject(team=team, players=[who.player_id] if who.player_id else []),
        timing=Timing(change_window=case.window, detected_at=case.window.end),
        propositions=propositions,
        claim="",
        evidence=[_evidence(t) for t in measured],
        depends_on=DependsOn(
            evidence_sets=[
                s for t in measured for s in (t.during.evidence_set_id, t.before.evidence_set_id)
            ],
            data_version=feed.data_version,
        ),
        rejected_alternatives=rejected,
        investigation=Investigation(
            agents=finding.agents,
            preregistered_predictions=len(finding.hypotheses),
            tool_calls=finding.tools.used,
            budget=case.tool_call_budget,
            cross_examination=f"{len(finding.exams)} counter-tests" if finding.exams else "",
        ),
        provenance=Provenance(trace_id=uuid.uuid4().hex),
    )
    return card.model_copy(update={"claim": narrator.claim(card, feed.meta)})
