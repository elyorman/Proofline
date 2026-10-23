"""Export contract-validated real cards and explicitly identified UI stand-ins.

The backend's replayed cards are kept unchanged. The flank note, its withdrawal,
key-event card and cues remain stand-ins until their backend producers exist.
"""

import argparse
import json
from pathlib import Path

from contracts.card import InsightCard
from contracts.clock import MatchClock
from contracts.cue import Cue
from contracts.event import Event
from contracts.meta import MatchMeta

WEB = Path(__file__).resolve().parents[1]
DEAD_BALL = {"set_piece", "foul", "goal", "substitution"}


def display_time(card: InsightCard) -> MatchClock:
    return card.timing.published_at or card.timing.detected_at


def later(clock: MatchClock, seconds: int) -> MatchClock:
    total = clock.minute * 60 + clock.second + seconds
    return MatchClock(period=clock.period, minute=total // 60, second=total % 60)


def stand_in_cards(match_id: str, meta: MatchMeta, events: list[Event]) -> list[InsightCard]:
    """Stand-ins only: the 55-minute note, withdrawal and optional first-goal card."""
    team = meta.teams["away"].name
    flank = InsightCard.model_validate(
        dict(
            id=f"ins-{match_id}-055-01",
            match_id=match_id,
            case_id="stand-in-flank",
            status="shown",
            case_outcome="explained",
            moment_type="shape_change",
            subject=dict(team=team),
            timing=dict(
                change_window="45:00-55:00",
                detected_at="55:20",
                verified_at="55:20",
                published_at="55:20",
            ),
            propositions=[
                dict(
                    id="p1",
                    type="change",
                    metric="channel_share_right",
                    subject=team,
                    direction="up",
                    window="45:00-55:00",
                    baseline="first_half",
                ),
                dict(
                    id="p2",
                    type="attribution",
                    cause="tactical.flank_overload",
                    effect="p1",
                    role="primary",
                    hypothesis_id="stand-in-flank",
                    agent="tactics",
                ),
            ],
            claim=f"{team} look to be finding more attacks down the right.",
            evidence=[
                dict(
                    metric="channel_share_right",
                    subject=team,
                    window="45:00-55:00",
                    value=0.625,
                    baseline=dict(window="first_half", value=0.375),
                    n_events=64,
                    tool_call_id="stand-in-flank",
                )
            ],
            depends_on=dict(evidence_sets=["stand-in-flank"], data_version="stand-in"),
            verification=dict(
                status="passed",
                recompute="match",
                baseline_check="passed",
                sample_size_check="passed",
                contradiction_check="passed",
                number_check="passed",
                semantic_check="passed",
                verifier_model_family="stand-in-no-model-run",
                support_level="moderate",
            ),
            variants=dict(
                casual=dict(
                    en=f"{team} look to be finding more attacks down the right.",
                    es=f"El {team} parece orientar más ataques por la derecha.",
                )
            ),
            provenance=dict(trace_id="stand-in-flank"),
        )
    )
    withdrawn = InsightCard.model_validate(
        flank.model_dump()
        | dict(
            revision=2,
            status="withdrawn",
            timing=flank.timing.model_dump() | dict(published_at="68:10", verified_at="68:10"),
            verification=dict(
                status="rejected",
                recompute="mismatch",
                baseline_check="passed",
                sample_size_check="passed",
                contradiction_check="failed",
                number_check="failed",
                semantic_check="skipped",
                verifier_model_family="stand-in-no-model-run",
                rejection_reason="Stand-in: coordinates changed; the explanation no longer holds.",
            ),
            revisions=[
                dict(
                    revision=2,
                    at="68:10",
                    reason="Stand-in coordinate correction",
                    amendment_ids=["stand-in-a1"],
                )
            ],
            variants=dict(
                casual=dict(
                    en=(
                        "The right-flank explanation has been withdrawn "
                        "after a coordinate correction."
                    ),
                    es=(
                        "Se ha retirado la explicación de la banda derecha "
                        "tras corregir las coordenadas."
                    ),
                )
            ),
        )
    )
    out = [flank, withdrawn]
    goal_event = next((e for e in events if e.type == "goal"), None)
    if goal_event is not None:
        at = goal_event.clock
        goal = InsightCard.model_validate(
            dict(
                id=f"stand-in-goal-{match_id}",
                match_id=match_id,
                case_id="stand-in-key-event",
                lane="fast",
                status="shown",
                case_outcome="none",
                moment_type="key_event",
                subject=dict(team=goal_event.team),
                timing=dict(change_window=f"{at}-{later(at, 1)}", detected_at=at, published_at=at),
                propositions=[
                    dict(
                        id="p1",
                        type="change",
                        metric="xg",
                        subject=goal_event.team,
                        direction="up",
                        window=f"{at}-{later(at, 1)}",
                        baseline="match_so_far",
                    )
                ],
                claim=f"Goal for {goal_event.team}.",
                depends_on=dict(evidence_sets=[], data_version="stand-in"),
                variants=dict(
                    casual=dict(en=f"Goal for {goal_event.team}.", es=f"Gol del {goal_event.team}.")
                ),
                provenance=dict(trace_id="stand-in-key-event"),
            )
        )
        out.insert(0, goal)
    return out


def stand_in_cues(cards: list[InsightCard], events: list[Event]) -> list[Cue]:
    """Stand-in schedules; press fields come only from a real card's facts/text."""
    cues = []
    for card in cards:
        at = display_time(card)
        if (
            card.moment_type == "pressure_shift"
            and card.evidence
            and card.verification
            and card.verification.status in {"passed", "corrected"}
            and card.status in {"verified", "scheduled", "shown", "revised"}
        ):
            event = next(
                (
                    e
                    for e in sorted(events, key=lambda e: e.clock.sort_key)
                    if e.type in DEAD_BALL and e.clock > at
                ),
                None,
            )
            if event is None:
                continue
            at = event.clock
            first = card.evidence[0]
            fields = dict(
                team=card.subject.team,
                before=first.baseline.value,
                after=first.value,
                headline=card.variants.get("casual", {}).get("en", ""),
                stat_label=first.metric.value,
                metric=first.metric.value,
            )
            template, kind = "pressure_shift_bar", "insight"
        elif card.status == "withdrawn":
            fields = dict(
                team=card.subject.team,
                headline=card.variants.get("casual", {}).get("en", ""),
                reason=card.revisions[-1].reason if card.revisions else "",
            )
            template, kind = "withdrawal_banner", "withdrawal"
        else:
            continue
        cues.append(
            Cue.model_validate(
                dict(
                    cue_id=f"stand-in-cue-{card.id}-{card.revision}",
                    match_id=card.match_id,
                    insight_id=card.id,
                    insight_revision=card.revision,
                    kind=kind,
                    template=template,
                    show_at=dict(mode="immediate", not_before=at, not_after=later(at, 45)),
                    duration_s=8,
                    status="approved",
                    decided_by="auto",
                    locale="en",
                    language_level=card.verification.language_level if card.verification else None,
                    fields=fields,
                )
            )
        )
    return sorted(cues, key=lambda cue: cue.show_at.not_before.sort_key)


def export(
    source_dir: Path,
    match_id: str,
    output_dir: Path,
    card_paths: list[Path],
    ledger_path: Path = WEB / "src/fixtures/ledger.json",
) -> None:
    raw = json.loads((source_dir / "meta.json").read_text(encoding="utf-8"))
    # This allowlist also strips legacy runtime fields before validating metadata.
    meta = MatchMeta.model_validate(dict(match_id=raw["match_id"], teams=raw["teams"]))
    if meta.match_id != match_id:
        raise ValueError("source metadata belongs to a different match")
    events = [
        Event.model_validate_json(line)
        for line in (source_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(e.match_id != match_id for e in events):
        raise ValueError("source events belong to a different match")
    real = [json.loads(path.read_text(encoding="utf-8")) for path in card_paths]
    validated = [InsightCard.model_validate(card) for card in real]
    if any(card.match_id != match_id for card in validated):
        raise ValueError("card belongs to a different match")
    stand_ins = stand_in_cards(match_id, meta, events)
    cards = [*stand_ins, *validated]
    keys = [(card.id, card.revision) for card in cards]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate card id and revision")
    cues = stand_in_cues(cards, events)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "meta.json").write_text(meta.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (output_dir / "events.jsonl").write_text(
        "".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8"
    )
    (output_dir / "match.json").unlink(missing_ok=True)
    # Real payloads are never rewritten to imitate Director or Narrator output.
    ledger = dict(
        cards=[*[c.model_dump(mode="json") for c in stand_ins], *real],
        cues=[c.model_dump(mode="json") for c in cues],
        stand_ins=dict(
            cards=[f"{c.id}@{c.revision}" for c in stand_ins], cues=[c.cue_id for c in cues]
        ),
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Exported {match_id}: {len(events)} events, {len(real)} real cards, "
        f"{len(stand_ins)} stand-in records and {len(cues)} stand-in cues."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--match", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cards", type=Path, nargs="+", default=[])
    parser.add_argument("--ledger", type=Path, default=WEB / "src/fixtures/ledger.json")
    args = parser.parse_args()
    export(args.source, args.match, args.out, args.cards, args.ledger)
