"""Turn a finding into a proposed Insight Card (spec §5): the primary cause's change and
attribution, any secondary attributions, the evidence each rests on, and the rejected
alternatives. The card goes to the Verifier; nothing here decides whether it is shown.
"""

import uuid
from collections.abc import Callable

from agents import narrator
from agents.cross_exam import kind_of
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
from contracts.prediction import Prediction
from contracts.taxonomy import CardStatus, CaseOutcome
from contracts.tool_result import ToolResult
from state.subjects import resolve
from state.tools import Feed


def _evidence(p: Prediction, during: ToolResult, before: ToolResult) -> Evidence:
    return Evidence(
        metric=p.metric,
        subject=p.subject,
        window=p.window,
        value=during.value,
        baseline=Baseline(window=p.compare_to, value=before.baseline.value),
        n_events=during.n_events,
        tool_call_id=during.tool_call_id,
    )


def _change(pid: str, p: Prediction) -> ChangeProposition:
    return ChangeProposition(
        id=pid,
        metric=p.metric,
        subject=p.subject,
        direction=p.direction,
        window=p.window,
        baseline=p.compare_to,
    )


def _cross_examination(finding: Finding) -> str:
    """Who tested whom, how, and what came of it, in one line per test."""
    by_id = {h.hypothesis_id: h for h in finding.hypotheses}
    return "; ".join(
        f"{e.challenger} {kind_of(e)} on {by_id[e.hypothesis_id].agent}'s "
        f"{by_id[e.hypothesis_id].taxonomy.value}: {e.result}"
        for e in finding.exams
    )


def _attribution(t: Tested, pid: str, role: str, effect: str) -> AttributionProposition:
    return AttributionProposition(
        id=pid,
        cause=t.hypothesis.taxonomy,
        effect=effect,
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
    propositions: list[ChangeProposition | AttributionProposition] = []

    def add(make: Callable[[str], ChangeProposition | AttributionProposition]) -> str:
        pid = f"p{len(propositions) + 1}"
        propositions.append(make(pid))
        return pid

    changes = {(p.metric, p.subject, p.direction): add(lambda pid: _change(pid, p))}
    add(
        lambda pid: _attribution(primary, pid, "primary", changes[p.metric, p.subject, p.direction])
    )
    for t in secondary:  # a secondary cause points at its own change
        q = t.hypothesis.prediction
        key = (q.metric, q.subject, q.direction)
        if key not in changes:
            changes[key] = add(lambda pid, q=q: _change(pid, q))
        add(lambda pid, t=t, e=changes[key]: _attribution(t, pid, "secondary", e))
    # A corollary a challenger asked for that held is evidence for the primary cause too.
    corroborated = [
        x
        for x in finding.corroborations
        if x.exam.hypothesis_id == primary.hypothesis.hypothesis_id
    ]
    for x in corroborated:
        add(lambda pid, x=x: _change(pid, x.exam.counter_prediction))
    backing = [primary, *secondary]
    measured = {  # one evidence line per tool call
        t.during.tool_call_id: (t.hypothesis.prediction, t.during, t.before) for t in backing
    } | {
        x.during.tool_call_id: (x.exam.counter_prediction, x.during, x.before) for x in corroborated
    }
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
        evidence=[_evidence(*m) for m in measured.values()],
        depends_on=DependsOn(
            evidence_sets=[
                s
                for _, during, before in measured.values()
                for s in (during.evidence_set_id, before.evidence_set_id)
            ],
            data_version=feed.data_version,
        ),
        rejected_alternatives=rejected,
        investigation=Investigation(
            agents=finding.agents,
            preregistered_predictions=len(finding.hypotheses),
            tool_calls=finding.tools.used,
            budget=case.tool_call_budget,
            cross_examination=_cross_examination(finding),
        ),
        provenance=Provenance(trace_id=uuid.uuid4().hex),
    )
    return card.model_copy(update={"claim": narrator.claim(card, feed.meta)})
