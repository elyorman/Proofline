"""The Verifier's deterministic checks (spec §9.2). They read the card, the tool calls its
evidence names and the evidence sets those calls stored, and the feed's events at their
versions; never the agents' reasoning."""

import re
from dataclasses import dataclass
from typing import Any

from agents import narrator
from agents.verifier.rules import MIN_SAMPLE, band
from contracts.card import CheckResult, Evidence, InsightCard
from contracts.prediction import Direction
from contracts.taxonomy import DEFAULT_THRESHOLD_KIND, BaselineScope, Metric, ThresholdKind
from contracts.tool_result import EvidenceSet
from state.subjects import opponent, resolve
from state.tools import Feed, first_half_minutes, read, window_minutes


@dataclass
class Record:
    """What the Verifier may read besides the card: the tool calls and the evidence sets."""

    calls: dict[str, dict[str, Any]]  # tool_call_id -> {"tool", "arguments", "result"}
    evidence: dict[str, EvidenceSet]

    @classmethod
    def of(cls, log: list[dict[str, Any]], evidence: dict[str, EvidenceSet]) -> "Record":
        calls = {e["result"]["tool_call_id"]: e for e in log if "result" in e}
        return cls(calls, evidence)

    def baseline_for(self, ev: Evidence) -> dict[str, Any]:
        """The baseline call behind an evidence item: same metric, subject and scope."""
        return next(
            c["result"]
            for c in self.calls.values()
            if c["tool"] == "baseline"
            and c["arguments"]["name"] == ev.metric
            and c["arguments"]["subject"] == ev.subject
            and c["arguments"]["scope"] == ev.baseline.window
        )


def change(metric: Metric, value: float, baseline: float) -> float:
    if DEFAULT_THRESHOLD_KIND[metric] == ThresholdKind.RELATIVE:
        return (value - baseline) / baseline if baseline else 0.0
    return value - baseline


def _events(feed: Feed, evidence: EvidenceSet) -> list:
    """Exactly the events an evidence set recorded, at their recorded versions."""
    by_ref = {(e.event_id, e.version): e for e in feed.events}
    return [by_ref[r.event_id, r.version] for r in evidence.events]


def recompute(card: InsightCard, record: Record, feed: Feed) -> bool:
    """Every evidence number, re-run over exactly its evidence set, matches exactly."""
    for ev in card.evidence:
        during = record.calls[ev.tool_call_id]["result"]
        events = _events(feed, record.evidence[during["evidence_set_id"]])
        if (
            read(feed.meta, ev.metric, ev.subject, events, window_minutes(ev.window)).value
            != ev.value
        ):
            return False
        before = record.baseline_for(ev)
        events = _events(feed, record.evidence[before["evidence_set_id"]])
        minutes = (
            first_half_minutes(events) if ev.baseline.window == BaselineScope.FIRST_HALF else None
        )
        if minutes is None:
            return False
        if read(feed.meta, ev.metric, ev.subject, events, minutes).value != ev.baseline.value:
            return False
    return True


def baseline_fair(card: InsightCard) -> CheckResult:
    fair = all(ev.baseline.window == BaselineScope.FIRST_HALF for ev in card.evidence)
    return CheckResult.PASSED if fair else CheckResult.FAILED


def sample(ev: Evidence, record: Record) -> int:
    """The sample a number rests on; for a sprint rate, the first half's sprints."""
    if ev.metric == Metric.SPRINT_COUNT:
        return record.baseline_for(ev)["baseline"]["n_events"]
    return ev.n_events


def sample_size(card: InsightCard, record: Record) -> CheckResult:
    enough = all(sample(ev, record) >= MIN_SAMPLE.get(ev.metric, 10**9) for ev in card.evidence)
    return CheckResult.PASSED if enough else CheckResult.FAILED


def level_of(feed: Feed, subject: str) -> str:
    who = resolve(feed.meta, subject)
    return "player" if who.player_id else "unit" if who.unit else "team"


def _related(feed: Feed, metric: Metric, subject: str) -> tuple[Metric, str] | None:
    """The metric a claim's change should show in too: a team's press in its opponent's
    long balls, a subject's sprint count in its sprint speed and back."""
    if metric == Metric.PRESSURE_RATE and resolve(feed.meta, subject).is_team:
        return Metric.LONG_BALL_SHARE, opponent(feed.meta, subject)
    if metric == Metric.SPRINT_COUNT:
        return Metric.SPRINT_SPEED, subject
    if metric == Metric.SPRINT_SPEED:
        return Metric.SPRINT_COUNT, subject
    return None


def contradicted(card: InsightCard, feed: Feed) -> bool:
    """A related metric moving the other way by at least its band contradicts the claim."""
    claim = next(p for p in card.propositions if p.type == "change")
    related = _related(feed, claim.metric, claim.subject)
    if related is None:
        return False
    metric, subject = related
    delivered = [e for e in feed.events if not card.timing.detected_at < e.clock]
    half = first_half_minutes(delivered)
    limit = band(metric, level_of(feed, subject), window_minutes(claim.window))
    if half is None or limit is None:
        return False
    in_window = [e for e in delivered if claim.window.contains(e.clock)]
    during = read(feed.meta, metric, subject, in_window, window_minutes(claim.window))
    before = read(feed.meta, metric, subject, [e for e in delivered if e.clock.period == 1], half)
    if during.value is None or before.value is None:
        return False
    moved = change(metric, during.value, before.value)
    against = moved < 0 if claim.direction == Direction.UP else moved > 0
    return against and abs(moved) >= limit


def numbers_match(card: InsightCard, texts: list[str]) -> bool:
    """Every number in the text is one the evidence or the window states."""
    allowed = {
        str(card.timing.change_window.start.minute),
        str(card.timing.change_window.end.minute),
    }
    for ev in card.evidence:
        for value in (ev.value, ev.baseline.value):
            allowed |= set(re.findall(r"\d+(?:\.\d+)?", narrator.number(ev.metric, value)))
    return all(set(re.findall(r"\d+(?:\.\d+)?", t)) <= allowed for t in texts)
