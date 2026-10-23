"""Build the local web demo, keeping engine metadata out of public assets.

Events are a real simulator export. Insight/cue records are illustrative UI
fixtures validated against the public contracts, NOT outputs of an agent run.
No evaluation results, semantic checks or amendment feed are claimed here.
"""

import argparse
import json
from pathlib import Path

from contracts.card import InsightCard
from contracts.cue import Cue
from contracts.event import Event
from contracts.taxonomy import Metric

WEB = Path(__file__).resolve().parents[1]


def demo_ledger(goal_event: Event) -> tuple[list[InsightCard], list[Cue]]:
    """Small authored records exercising publication, evidence and withdrawal."""
    passing = dict(
        status="passed",
        recompute="match",
        baseline_check="passed",
        sample_size_check="passed",
        contradiction_check="passed",
        number_check="passed",
        semantic_check="passed",
        verifier_model_family="fixture-only-no-model-run",
        support_level="moderate",
    )

    def card(id, at, metric, subject, value, baseline, cause, en, es, **extra):
        return InsightCard.model_validate(
            dict(
                id=id,
                match_id="m01",
                case_id=f"fixture-{id}",
                status="shown",
                case_outcome="explained",
                moment_type="pressure_shift" if metric == "pressure_rate" else "shape_change",
                subject=dict(team=subject),
                timing=dict(
                    change_window="58:00-63:00" if metric == "pressure_rate" else "45:00-55:00",
                    detected_at=at,
                    verified_at=at,
                    published_at=at,
                ),
                propositions=[
                    dict(
                        id="p1",
                        type="change",
                        metric=metric,
                        subject=subject,
                        direction="up",
                        window="58:00-63:00" if metric == "pressure_rate" else "45:00-55:00",
                        baseline="first_half",
                    ),
                    dict(
                        id="p2",
                        type="attribution",
                        cause=cause,
                        effect="p1",
                        role="primary",
                        hypothesis_id=f"fixture-hyp-{id}",
                        agent="tactics",
                    ),
                ],
                claim=en,
                evidence=[
                    dict(
                        metric=metric,
                        subject=subject,
                        window="58:00-63:00" if metric == "pressure_rate" else "45:00-55:00",
                        value=value,
                        baseline=dict(window="first_half", value=baseline),
                        n_events=18 if metric == "pressure_rate" else 64,
                        tool_call_id=f"fixture-tool-{id}",
                    )
                ],
                depends_on=dict(evidence_sets=[f"fixture-evidence-{id}"], data_version="fixture-1"),
                verification=passing,
                variants=dict(casual=dict(en=en, es=es), analyst=dict(en=en, es=es)),
                provenance=dict(trace_id=f"fixture-trace-{id}"),
            )
            | extra
        )

    flank = card(
        "ins-m01-055-01",
        "55:20",
        "channel_share_right",
        "Northvale",
        0.625,
        0.375,
        "tactical.flank_overload",
        "Northvale look to be finding more of their attacks down the right.",
        "El Northvale parece orientar más sus ataques por la derecha.",
    )
    pressure = card(
        "ins-m01-063-01",
        "63:40",
        "pressure_rate",
        "Harbour City",
        0.83,
        0.32,
        "tactical.press_intensity_up",
        "Harbour City have raised their press. Northvale are going long far more often.",
        "El Harbour City presiona más arriba. El Northvale juega en largo mucho más a menudo.",
        investigation=dict(
            agents=["tactics", "physical", "game_state"],
            preregistered_predictions=4,
            tool_calls=11,
            budget=16,
            cross_examination="Illustrative fixture; no investigation has run.",
        ),
        rejected_alternatives=[
            dict(
                hypothesis_id="fixture-fatigue",
                taxonomy="physical.unit_fatigue",
                agent="physical",
                reason="Illustrative alternative; not a measured agent outcome.",
                rejected_by="cross_examination",
                tool_call_id="fixture-control",
            )
        ],
    )
    pressure.evidence.append(
        pressure.evidence[0].model_copy(
            update=dict(
                metric=Metric.LONG_BALL_SHARE,
                subject="Northvale",
                value=0.59,
                baseline=pressure.evidence[0].baseline.model_copy(update=dict(value=0.11)),
                n_events=17,
                tool_call_id="fixture-long-ball",
            )
        )
    )
    pressure.depends_on.evidence_sets.append("fixture-evidence-long-ball")
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
                verifier_model_family="fixture-only-no-model-run",
                rejection_reason="Illustrative withdrawal following a coordinate correction.",
            ),
            revisions=[
                dict(
                    revision=2,
                    at="68:10",
                    reason="Illustrative coordinate correction",
                    amendment_ids=["fixture-a1"],
                )
            ],
            variants=dict(
                casual=dict(
                    en=(
                        "Update: the right-flank explanation has been withdrawn "
                        "after a coordinate correction."
                    ),
                    es=(
                        "Actualización: se ha retirado la explicación de la banda derecha "
                        "tras corregir las coordenadas."
                    ),
                )
            ),
        )
    )
    # A deterministic key-event fixture, not a hard-coded score.
    goal_clock = goal_event.clock
    goal_end = goal_clock.model_copy(
        update=dict(
            second=(goal_clock.second + 1) % 60,
            minute=goal_clock.minute + (goal_clock.second == 59),
        )
    )
    goal_en = f"Goal for {goal_event.team}."
    goal_es = f"Gol del {goal_event.team}."
    goal = InsightCard.model_validate(
        dict(
            id="fixture-goal",
            match_id="m01",
            case_id="fixture-key-event",
            lane="fast",
            status="shown",
            case_outcome="none",
            moment_type="key_event",
            subject=dict(team=goal_event.team),
            timing=dict(
                change_window=f"{goal_clock}-{goal_end}",
                detected_at=goal_clock,
                published_at=goal_clock,
            ),
            propositions=[
                dict(
                    id="p1",
                    type="change",
                    metric="xg",
                    subject=goal_event.team,
                    direction="up",
                    window=f"{goal_clock}-{goal_end}",
                    baseline="match_so_far",
                )
            ],
            claim=goal_en,
            depends_on=dict(evidence_sets=[], data_version="fixture-only"),
            variants=dict(casual=dict(en=goal_en, es=goal_es)),
            provenance=dict(trace_id="fixture-key-event"),
        )
    )
    cues = [
        Cue.model_validate(
            dict(
                cue_id=f"fixture-cue-{c.id}-{c.revision}",
                match_id="m01",
                insight_id=c.id,
                insight_revision=c.revision,
                kind="withdrawal" if c.status == "withdrawn" else "insight",
                template="withdrawal_banner" if c.status == "withdrawn" else "pressure_shift_bar",
                show_at=dict(
                    mode="immediate",
                    not_before=str(c.timing.published_at),
                    not_after="68:55" if c.status == "withdrawn" else "64:25",
                ),
                duration_s=8,
                status="approved",
                decided_by="auto",
                locale="en",
                language_level="measured",
                fields=dict(team=c.subject.team),
            )
        )
        for c in (pressure, withdrawn)
    ]
    # Revalidate the serialized boundary, including nested values changed above.
    return [
        InsightCard.model_validate(c.model_dump()) for c in (goal, flank, pressure, withdrawn)
    ], cues


def export(source_dir: Path) -> None:
    """Prepare public fixtures from CLI output, using only pre-match metadata."""
    raw_meta = json.loads((source_dir / "meta.json").read_text(encoding="utf-8"))
    events = [
        Event.model_validate_json(line)
        for line in (source_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out = WEB / "public/fixtures/m01"
    out.mkdir(parents=True, exist_ok=True)
    # Only the allowlist below reaches the browser; no seed, score or script.
    match = dict(
        match_id=raw_meta["match_id"],
        teams={
            side: dict(
                name=raw_meta["teams"][side]["name"],
                code=raw_meta["teams"][side]["code"],
                formation=raw_meta["teams"][side]["formation"],
                players=[
                    dict(
                        player_id=p["player_id"],
                        name=p["name"],
                        role=p["role"],
                        unit=p["unit"],
                    )
                    for p in raw_meta["teams"][side]["players"]
                ],
            )
            for side in ("home", "away")
        },
    )
    (out / "meta.json").write_text(json.dumps(match) + "\n", encoding="utf-8")
    (out / "events.jsonl").write_text(
        "".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8"
    )
    (out / "match.json").unlink(missing_ok=True)
    cards, cues = demo_ledger(next(e for e in events if e.type == "goal"))
    card_json = json.dumps([c.model_dump(mode="json") for c in cards], indent=2)
    cue_json = json.dumps([c.model_dump(mode="json") for c in cues], indent=2)
    source = (
        "/* Generated by surfaces/web/scripts/export_web_replay.py.\n"
        "   Illustrative UI records, not agent output. */\n"
        "import type { InsightCard } from './types/insight-card';\n"
        "import type { Cue } from './types/cue';\n\n"
        f"export const cards: InsightCard[] = {card_json};\n\n"
        f"export const cues: Cue[] = {cue_json};\n"
    )
    (WEB / "src/fixtures.ts").write_text(source, encoding="utf-8")
    print(f"Exported {len(events)} simulated events and contract-validated illustrative records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="directory of CLI match output")
    export(parser.parse_args().source)
