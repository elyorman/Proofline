"""Role instructions and the prompts each step sends. The instructions are fixed per role,
so the model provider can cache them; the prompt carries the case."""

import json

from contracts.case import Case
from contracts.meta import MatchMeta
from contracts.taxonomy import DOMAIN_OF_AGENT, AgentRole, Cause

METRICS = """\
- pressure_rate (team): the team's pressures in the opponent's first 60% of the pitch per \
opponent pass, carry or dribble starting there. A first half is often 0.2-0.5. \
min_change in absolute units, e.g. 0.15.
- long_ball_share (team): share of the team's passes longer than 30 m. A first half is often \
0.05-0.2. Absolute units, e.g. 0.10.
- channel_share_left / channel_share_centre / channel_share_right (team): share of the \
team's passes, carries and dribbles starting in that third of the width. Absolute units.
- sprint_count (team, "Team.defence", "Team.midfield", "Team.attack", or a player id): \
sprints per minute of play. min_change is a fraction of the first-half rate, e.g. 0.3 for \
a 30% fall.
- sprint_speed (same subjects): mean sprint speed in km/h. Absolute units, e.g. 1.0."""

RULES = """\
You never compute or estimate a number. You pre-register predictions; code tests each one \
with deterministic tools, comparing the case's window with the first half, and judges it.
Each hypothesis names one cause and one prediction that would hold if that cause were \
present: the metric it moves most, whose metric it is, the direction, and the smallest \
change that would count. Choose a prediction that tells your cause apart from the others: \
a press change moves the pressing team's pressure rate and the opponent's long balls; \
chasing a result or protecting a lead also changes the team's own long-ball share and \
follows the score; fatigue lowers a unit's or a player's sprints. Predicting a change that \
any of several causes would produce proves little. Register nothing for a cause the case \
gives no reason to suspect."""


def _causes(role: AgentRole) -> list[str]:
    plantable = [c for c in Cause if c.domain != "fallback"]
    if role == AgentRole.SINGLE:
        return [c.value for c in plantable]
    return [c.value for c in plantable if c.domain == DOMAIN_OF_AGENT[role]]


def instructions(role: AgentRole, max_hypotheses: int) -> str:
    scope = (
        "You investigate alone, across every domain: tactics, physical and game state."
        if role == AgentRole.SINGLE
        else f"You are the {DOMAIN_OF_AGENT[role].replace('_', ' ')} specialist."
    )
    return (
        "You investigate one detected moment in a football match, from event data.\n"
        f"{scope}\n\n{RULES}\n\nCauses you may register:\n- "
        + "\n- ".join(_causes(role))
        + f"\n\nMeasurable metrics:\n{METRICS}\n\nRegister at most {max_hypotheses} hypotheses."
    )


RANKING = """\
You rank the hypotheses that survived testing for one detected moment in a football match.
Code has already tested each one against deterministic tools; you never compute or change a \
number. The primary cause is the one whose own predicted signature held most clearly; a \
secondary cause is real but explains less. A game-state cause (chasing the result, \
protecting a lead) is primary only if the team's own long-ball share moved as that cause \
predicts; otherwise the score is at most secondary context for a tactical change. If \
nothing survived, the outcome is 'none'. If the effect is real but no surviving cause fits, \
the outcome is 'other'. Otherwise it is 'explained', with a primary."""


def _match(meta: MatchMeta) -> dict:
    return {
        side: {
            "team": team.name,
            "players": [f"{p.player_id} {p.role} ({p.unit})" for p in team.players],
        }
        for side, team in meta.teams.items()
    }


def case_prompt(case: Case, meta: MatchMeta, score: dict[str, float]) -> str:
    moment = {
        "moment": case.moment_type.value,
        "window": str(case.window),
        "detected_at": str(case.window.end),
        "score_at_detection": {
            meta.teams[s].name: int(score[f"{s}_goals"]) for s in ("home", "away")
        },
        "what_the_detector_saw": [
            {
                "metric": t.metric.value,
                "subject": t.subject,
                "first_half": round(t.baseline_value, 3),
                "window": round(t.value, 3),
                "sample": t.n_events,
            }
            for t in case.triggers
        ],
        "match": _match(meta),
    }
    return "Pre-register your hypotheses for this moment.\n" + json.dumps(moment, indent=1)


def ranking_prompt(
    case: Case, survivors: list[dict], score: dict[str, float], meta: MatchMeta
) -> str:
    return "Rank these surviving hypotheses.\n" + json.dumps(
        {
            "moment": case.moment_type.value,
            "window": str(case.window),
            "score_at_detection": {
                meta.teams[s].name: int(score[f"{s}_goals"]) for s in ("home", "away")
            },
            "survivors": survivors,
        },
        indent=1,
    )
