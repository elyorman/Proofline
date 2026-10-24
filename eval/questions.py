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
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from contracts.clock import MatchClock
from contracts.eval_run import (
    QUESTION_METRICS,
    QuestionOutcome,
    QuestionRun,
    Split,
    Suite,
    question_counts,
)
from contracts.meta import MatchMeta
from contracts.prediction import Direction
from contracts.question import Answer, PlainAnswer, Question
from contracts.taxonomy import Cause, Metric
from engine.io import match_meta
from engine.script import load_script
from engine.sim import MatchSim
from eval.metrics import estimate
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


def claim(
    answer: Answer | PlainAnswer, after_follow_up: bool = False
) -> tuple[bool, Cause | None, str | None]:
    """(whether the answer publishes a cause, the cause, its team). Proofline publishes one
    on a verified card; the plain agent whenever it says the change happens and names one.
    `after_follow_up` reads the card as its follow-up left it: an unresolved one names none."""
    if isinstance(answer, PlainAnswer):
        return answer.claims, answer.cause, answer.team
    card = answer.final if after_follow_up and answer.final else answer.card
    if card and card.follow_up and card.follow_up.status == "unresolved":
        return False, None, None
    return (True, card.primary_cause.cause, card.subject.team) if card else (False, None, None)


def outcome(answer: Answer | PlainAnswer) -> str:
    if isinstance(answer, PlainAnswer):
        return "claimed" if answer.claims else "no claim"
    return answer.outcome


def score(
    answers: list[Answer | PlainAnswer], key: list[Key], after_follow_up: bool = False
) -> dict:
    """Right answers on true premises; no claim on false ones; and every false claim. An
    excluded question is listed but counts in none of them."""
    by_id = {a.question.question_id: a for a in answers}
    rows = []
    for k in key:
        a = by_id.get(k.question.question_id)
        claimed, cause, team = claim(a, after_follow_up) if a is not None else (False, None, None)
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


def question_digest(questions: list[Question]) -> str:
    content = [q.model_dump(mode="json") for q in sorted(questions, key=lambda q: q.question_id)]
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def suite_digest(split: str) -> str:
    suites = [load_suite(ROOT / "engine/suites", name, split) for name in ("planted", "decoys")]
    return hashlib.sha256(
        "\n".join(f"{s.truth.suite}:{s.digest}" for s in suites).encode()
    ).hexdigest()


def question_samples(rows: list[QuestionOutcome], metric: str) -> list[tuple[int, int]]:
    if metric not in QUESTION_METRICS:
        raise ValueError(f"unknown question metric {metric}")
    rows = [r for r in rows if not r.excluded]  # unobservable: listed, never counted
    matches = sorted({r.match_id for r in rows})
    return [question_counts([r for r in rows if r.match_id == match])[metric] for match in matches]


def score_run(
    runs: Path,
    split: str,
    variant: str,
    *,
    questions: Path | None = None,
    run_id: str | None = None,
    model_id: str | None = None,
    tool_call_budget: int | None = None,
    seed: int = 0,
    resamples: int = 2000,
    after_follow_up: bool = False,
) -> QuestionRun:
    """A record of one question run; `after_follow_up` scores each card as its follow-up left
    it. A question on an unobservable planted change is listed but counts in no metric."""
    if variant not in ("A", "B", "P"):
        raise ValueError("question variant must be A, B or P")
    started = int(time.time() * 1000)
    question_path = questions or runs / "questions.jsonl"
    asked = [
        Question.model_validate_json(line)
        for line in question_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not asked or len({q.question_id for q in asked}) != len(asked):
        raise ValueError("question set must be nonempty with unique question IDs")
    key = {k.question.question_id: k for k in keys(split)}
    for question in asked:
        if question.question_id not in key or key[question.question_id].question != question:
            raise ValueError(
                f"{question.question_id}: question does not match this split's sealed suite"
            )
    qdigest, sdigest = question_digest(asked), suite_digest(split)
    metadata = question_path.with_suffix(".meta.json")
    origin_verified = metadata.exists()
    if origin_verified:
        original = json.loads(metadata.read_text(encoding="utf-8"))
        if (
            original.get("split"),
            original.get("question_set_digest"),
            original.get("suite_digest"),
        ) != (split, qdigest, sdigest):
            raise ValueError("question set or suite differs from its generation manifest")
    path = runs / variant / "answers.jsonl"
    raw_answers = path.read_bytes()
    by_id = {}
    model = PlainAnswer if variant == "P" else Answer
    asked_by_id = {q.question_id: q for q in asked}
    for line in raw_answers.decode("utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError("answer records must be objects")
        question = Question.model_validate(raw.get("question"))
        if question.question_id not in asked_by_id or asked_by_id[question.question_id] != question:
            raise ValueError("an answer belongs to a different question set")
        if question.question_id in by_id:
            raise ValueError("a question has more than one answer record")
        if "error" in raw:
            if not isinstance(raw["error"], str):
                raise ValueError("question error must be text")
            by_id[question.question_id] = raw
        else:
            answer = model.model_validate(raw)
            if isinstance(answer, Answer):
                if answer.variant != variant:
                    raise ValueError("answer variant differs from its folder")
                if answer.card is not None and (
                    answer.card.status != "verified"
                    or answer.card.verification is None
                    or answer.card.verification.status not in ("passed", "corrected")
                    or answer.card.match_id != question.match_id
                ):
                    raise ValueError("a published question card must be verified for its match")
            by_id[question.question_id] = answer
    rows = []
    for question in sorted(asked, key=lambda q: q.question_id):
        expected = key[question.question_id]
        value = by_id.get(question.question_id)
        answered = isinstance(value, (Answer, PlainAnswer))
        claimed, cause, team = claim(value, after_follow_up) if answered else (False, None, None)
        right = bool(
            answered
            and (
                claimed and (cause, team) == (expected.cause, expected.team)
                if expected.premise_true
                else not claimed
            )
        )
        error = value.get("error") if isinstance(value, dict) else None
        rows.append(
            QuestionOutcome(
                question_id=question.question_id,
                match_id=question.match_id,
                question_text=question.text,
                locale=question.locale,
                premise_true=expected.premise_true,
                expected_cause=expected.cause,
                expected_team=expected.team,
                answered=answered,
                outcome=outcome(value) if answered else "error" if error is not None else "missing",
                claimed=claimed,
                right=right,
                false_claim=claimed and not right,
                cause=cause,
                team=team,
                error=error,
                input_tokens=value.input_tokens if answered else 0,
                output_tokens=value.output_tokens if answered else 0,
                tool_calls=value.tool_calls
                if isinstance(value, PlainAnswer)
                else value.card.investigation.tool_calls
                if isinstance(value, Answer) and value.card and value.card.investigation
                else None,
                usage_known=answered,
                excluded=expected.excluded,
            )
        )
    metrics = [
        estimate(
            name, Suite.QUESTIONS, question_samples(rows, name), seed=seed, resamples=resamples
        )
        for name in QUESTION_METRICS
    ]
    metrics = [m for m in metrics if m is not None]
    adigest = hashlib.sha256(raw_answers).hexdigest()
    identity = hashlib.sha256(
        json.dumps(
            [
                variant,
                split,
                qdigest,
                sdigest,
                adigest,
                model_id,
                tool_call_budget,
                seed,
                resamples,
                after_follow_up,
            ]
        ).encode()
    ).hexdigest()[:16]
    return QuestionRun(
        run_id=run_id
        or f"questions-{split}-{variant}{'-after-follow-up' if after_follow_up else ''}-{identity}",
        after_follow_up=after_follow_up,
        variant=variant,
        split=Split(split),
        question_set_digest=qdigest,
        suite_digest=sdigest,
        answers_digest=adigest,
        suite_origin_verified=origin_verified,
        model_id=model_id,
        tool_call_budget=tool_call_budget,
        input_tokens=sum(r.input_tokens for r in rows),
        output_tokens=sum(r.output_tokens for r in rows),
        token_usage_complete=all(r.usage_known for r in rows),
        started_at_ms=started,
        finished_at_ms=int(time.time() * 1000),
        bootstrap_seed=seed,
        bootstrap_resamples=resamples,
        rows=rows,
        metrics=metrics,
        undefined_metrics=[n for n in QUESTION_METRICS if n not in {m.name for m in metrics}],
    )


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
    scored.add_argument("--questions", type=Path)
    scored.add_argument("--out", type=Path)
    scored.add_argument("--record-dir", type=Path)
    scored.add_argument("--run-id")
    scored.add_argument("--model-id")
    scored.add_argument("--tool-call-budget", type=int)
    scored.add_argument("--seed", type=int, default=0)
    scored.add_argument("--resamples", type=int, default=2000)
    scored.add_argument(
        "--after-follow-up", action="store_true", help="score each card as its follow-up left it"
    )
    args = parser.parse_args(argv)
    key = keys(args.split)
    if args.command == "make":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(k.question.model_dump_json() + "\n" for k in key))
        args.out.with_suffix(".meta.json").write_text(
            json.dumps(
                dict(
                    split=args.split,
                    question_set_digest=question_digest([k.question for k in key]),
                    suite_digest=suite_digest(args.split),
                ),
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        print(f"{len(key)} questions written to {args.out}")
        return 0
    from eval.__main__ import _emit

    try:
        result = score_run(
            args.runs,
            args.split,
            args.variant,
            questions=args.questions,
            run_id=args.run_id,
            model_id=args.model_id,
            tool_call_budget=args.tool_call_budget,
            seed=args.seed,
            resamples=args.resamples,
            after_follow_up=args.after_follow_up,
        )
        _emit(result, args.out, args.record_dir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
