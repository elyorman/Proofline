"""The question suite: viewer questions written from the sealed truth, and their scoring.

Each planted match gets two questions, asked when its truth window ends: one whose premise is
its planted change (for a press, the other team's long balls, so the answer needs both teams),
and one assuming the opposite of that change. Each decoy gets two whose premises nothing
planted. Questions alternate English and Spanish. Only the questions go to the product
(`questions.jsonl`); the answers are rebuilt here from the truth when scoring. A true
premise whose planted change is flagged not observable in one match is asked but not
scored, as recall leaves that match out.

    python -m eval.questions make --split dev --out runs/q1/questions.jsonl
    python -m eval.questions score --runs runs/q1 --split dev --variant A

Rosters come from the suites' committed scripts, so neither needs a generated match.
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from contracts.clock import MatchClock
from contracts.meta import MatchMeta
from contracts.prediction import Direction
from contracts.question import Answer, PlainAnswer, Question
from contracts.taxonomy import Cause, Metric
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from eval.suites import load_suite

ROOT = Path(__file__).resolve().parents[1]
UP, DOWN = Direction.UP, Direction.DOWN
UNIT = {
    "defence": ("defence", "la defensa"),
    "midfield": ("midfield", "el centro del campo"),
    "attack": ("attack", "la delantera"),
}
TEAM_TEXT = {  # (metric, direction) -> (English, Spanish), for a team
    (Metric.PRESSURE_RATE, UP): (
        "Why are {who} pressing so much harder since {since}'?",
        "¿Por qué {who} presiona mucho más desde el minuto {since}?",
    ),
    (Metric.PRESSURE_RATE, DOWN): (
        "Why have {who} stopped pressing since {since}'?",
        "¿Por qué {who} ha dejado de presionar desde el minuto {since}?",
    ),
    (Metric.LONG_BALL_SHARE, UP): (
        "Why are {who} hitting so many long balls since {since}'?",
        "¿Por qué {who} juega tantos balones largos desde el minuto {since}?",
    ),
    (Metric.LONG_BALL_SHARE, DOWN): (
        "Why have {who} stopped going long since {since}'?",
        "¿Por qué {who} ya no juega en largo desde el minuto {since}?",
    ),
}
UNIT_TEXT = {  # sprints of a team's unit
    DOWN: (
        "Why is {team}'s {unit} slowing down since {since}'?",
        "¿Por qué se está frenando {unit} de {team} desde el minuto {since}?",
    ),
    UP: (
        "Why is {team}'s {unit} sprinting more since {since}'?",
        "¿Por qué {unit} de {team} esprinta más desde el minuto {since}?",
    ),
}
PLAYER_TEXT = {  # sprints of a player
    DOWN: (
        "Why is {who} fading since {since}'?",
        "¿Por qué se está apagando {who} desde el minuto {since}?",
    ),
    UP: (
        "Why is {who} sprinting more since {since}'?",
        "¿Por qué {who} esprinta más desde el minuto {since}?",
    ),
}
DECOY_ASKED, DECOY_SINCE = MatchClock.parse("72:00"), MatchClock.parse("62:00")


@dataclass(frozen=True)
class Key:
    """What a question's right answer is: a cause on a team, or that nothing happened."""

    question: Question
    premise_true: bool
    cause: Cause | None = None
    team: str | None = None
    excluded: bool = False  # its planted change is flagged not observable


def _text(meta: MatchMeta, metric: Metric, subject: str, way: Direction, since: int, es: bool):
    team = next((t for t in meta.teams.values() if subject.startswith(t.name)), None)
    if metric in (Metric.PRESSURE_RATE, Metric.LONG_BALL_SHARE):
        return TEAM_TEXT[metric, way][es].format(who=subject, since=since)
    if team and subject.startswith(f"{team.name}."):
        unit = UNIT[subject.split(".", 1)[1]][es]
        return UNIT_TEXT[way][es].format(team=team.name, unit=unit, since=since)
    player = next(p for t in meta.teams.values() for p in t.players if p.player_id == subject)
    return PLAYER_TEXT[way][es].format(who=player.name, since=since)


def _clock(minute: int) -> MatchClock:
    return MatchClock(period=2, minute=minute, second=0)


def keys(split: str) -> list[Key]:
    """Every question of the split's suite, with its answer, in a fixed order."""
    out: list[Key] = []

    def add(meta, metric, subject, way, since, asked, true, truth=None, excluded=False):
        n = len(out)
        es = n % 2 == 1
        question = Question(
            question_id=f"q{n + 1:03d}",
            match_id=meta.match_id,
            asked_at=asked,
            text=_text(meta, metric, subject, way, since.minute, es),
            locale="es" if es else "en",
        )
        cause, team = (truth.cause, truth.team) if truth and true else (None, None)
        out.append(Key(question, true, cause, team, excluded))

    planted = load_suite(ROOT / "engine/suites", "planted", split)
    unseen = {x.match_id for x in planted.flags.exclusions}
    for t in planted.truth.entries:
        meta = _meta("planted", split, t.match_id)
        since = _clock(t.started.minute)
        asked = _clock(min(90, math.ceil(t.window.end.seconds_in_period / 60 + 45)))
        shown = t.observables[1] if t.cause in _PRESS else t.observables[0]
        add(
            meta,
            shown.metric,
            shown.subject,
            shown.direction,
            since,
            asked,
            True,
            t,
            t.match_id in unseen,
        )
        first = t.observables[0]
        opposite = DOWN if first.direction == UP else UP
        add(meta, first.metric, first.subject, opposite, since, asked, False, t)
    for t in load_suite(ROOT / "engine/suites", "decoys", split).truth.entries:
        meta = _meta("decoys", split, t.match_id)
        home, away = (meta.teams[s].name for s in ("home", "away"))
        add(meta, Metric.PRESSURE_RATE, home, UP, DECOY_SINCE, DECOY_ASKED, False)
        add(meta, Metric.SPRINT_COUNT, f"{away}.midfield", DOWN, DECOY_SINCE, DECOY_ASKED, False)
    return out


_PRESS = (Cause.PRESS_INTENSITY_UP, Cause.PRESS_INTENSITY_DOWN)


def _meta(suite: str, split: str, match_id: str) -> MatchMeta:
    """The match's teams and rosters, from its sealed script: what its meta.json will say,
    without simulating the match."""
    script = load_script(ROOT / "engine/suites" / suite / split / "scripts" / f"{match_id}.yaml")
    return match_meta(MatchSim(script))


def claim(answer: Answer | PlainAnswer) -> tuple[bool, Cause | None, str | None]:
    """(whether the answer publishes a cause, the cause, its team). Proofline publishes one
    on a verified card; the plain agent whenever it says the change happens and names one."""
    if isinstance(answer, PlainAnswer):
        return answer.claims, answer.cause, answer.team
    card = answer.card
    return (True, card.primary_cause.cause, card.subject.team) if card else (False, None, None)


def outcome(answer: Answer | PlainAnswer) -> str:
    if isinstance(answer, PlainAnswer):
        return "claimed" if answer.claims else "no claim"
    return answer.outcome


def score(answers: list[Answer | PlainAnswer], key: list[Key]) -> dict:
    """Right answers on true premises; no claim on false ones; and every false claim. An
    excluded question is listed but counts in none of them."""
    by_id = {a.question.question_id: a for a in answers}
    rows = []
    for k in key:
        a = by_id.get(k.question.question_id)
        claimed, cause, team = claim(a) if a is not None else (False, None, None)
        if k.premise_true:
            right = claimed and cause == k.cause and team == k.team
        else:
            right = a is not None and not claimed
        rows.append(
            {
                "question_id": k.question.question_id,
                "match_id": k.question.match_id,
                "premise_true": k.premise_true,
                "outcome": outcome(a) if a else "missing",
                "right": right,
                "claimed": claimed,
                "false_claim": claimed and not right,
                "excluded": k.excluded,
            }
        )
    scored = [r for r in rows if not r["excluded"]]
    true_rows = [r for r in scored if r["premise_true"]]
    false_rows = [r for r in scored if not r["premise_true"]]
    claims = [r for r in scored if r["claimed"]]
    return {
        "answered_right": f"{sum(r['right'] for r in true_rows)}/{len(true_rows)}",
        "false_premises_rejected": f"{sum(r['right'] for r in false_rows)}/{len(false_rows)}",
        "false_claims": sum(r["false_claim"] for r in scored),
        "claims_right": f"{sum(r['right'] for r in claims)}/{len(claims)}",
        "missing": sum(r["outcome"] == "missing" for r in scored),
        "excluded": [r["question_id"] for r in rows if r["excluded"]],
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.questions", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("make")
    make.add_argument("--split", choices=["dev", "heldout"], required=True)
    make.add_argument("--out", type=Path, required=True)
    scored = sub.add_parser("score")
    scored.add_argument("--runs", type=Path, required=True)
    scored.add_argument("--split", choices=["dev", "heldout"], required=True)
    scored.add_argument("--variant", choices=["A", "B", "P"], required=True)
    args = parser.parse_args(argv)
    key = keys(args.split)
    if args.command == "make":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(k.question.model_dump_json() + "\n" for k in key))
        print(f"{len(key)} questions written to {args.out}")
        return 0
    lines = (args.runs / args.variant / "answers.jsonl").read_text().splitlines()
    model = PlainAnswer if args.variant == "P" else Answer
    answers = [model.model_validate_json(x) for x in lines if '"error"' not in x[:400]]
    result = score(answers, key)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=1))
    for r in result["rows"]:
        mark = "xx " if r["excluded"] else "OK " if r["right"] else "-- "
        print(
            f"  {mark}{r['question_id']} {r['match_id']} premise_true={r['premise_true']} "
            f"{r['outcome']}{' FALSE CLAIM' if r['false_claim'] else ''}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
